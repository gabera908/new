# -*- coding: utf-8 -*-
"""اختبارات وحدة: الخدمة المالية ومحرك القيود وقواعد الحوكمة"""
from datetime import date

import pytest

from app.models import Account, CostCenter
from app.services.accounting_service import AccountingService


def post_pair(db, debit_code, credit_code, amount, cc=None):
    """قيد متوازن بسيط: مدين + دائن بنفس المبلغ"""
    lines = [
        {"account_code": debit_code, "debit": amount, "credit": 0.0},
        {"account_code": credit_code, "debit": 0.0, "credit": amount},
    ]
    if cc:
        for ld in lines:
            ld["cost_center_code"] = cc
    return AccountingService.post_entry(db, date(2026, 3, 1), "قيد اختبار", lines, user_id=1)


def test_balanced_entry_posted_and_balances_updated(db):
    ok, msg = post_pair(db, "111101", "411101", 1000.0, cc="101")
    assert ok is True
    assert db.get(Account, "111101").balance == pytest.approx(1000.0)
    # الإيرادات: زيادة بالأرصدة الدائنة
    assert db.get(Account, "411101").balance == pytest.approx(1000.0)
    # مركز التكلفة يتراكم كلا السطرين (1000 مدين + 1000 دائن)
    assert db.get(CostCenter, "101").balance == pytest.approx(2000.0)


def test_unbalanced_entry_rejected(db):
    ok, msg = AccountingService.post_entry(db, date(2026, 3, 1), "قيد غير متوازن", [
        {"account_code": "111101", "debit": 500.0, "credit": 0.0},
        {"account_code": "411101", "debit": 0.0, "credit": 100.0},
    ])
    assert ok is False
    assert "توازن" in msg


def test_level4_parent_account_rejected_governance_rule1(db):
    ok, msg = AccountingService.post_entry(db, date(2026, 3, 1), "قيد على حساب أب", [
        {"account_code": "1111", "debit": 100.0, "credit": 0.0},
        {"account_code": "411101", "debit": 0.0, "credit": 100.0},
    ])
    assert ok is False
    assert "قاعدة حوكمة رقم 1" in msg


def test_missing_account_rejected(db):
    ok, msg = AccountingService.post_entry(db, date(2026, 3, 1), "قيد بحساب غير موجود", [
        {"account_code": "999999", "debit": 100.0, "credit": 0.0},
        {"account_code": "411101", "debit": 0.0, "credit": 100.0},
    ])
    assert ok is False
    assert "غير موجود" in msg


def test_missing_cost_center_rejected(db):
    ok, msg = AccountingService.post_entry(db, date(2026, 3, 1), "قيد بمركز تكلفة وهمي", [
        {"account_code": "111101", "debit": 100.0, "credit": 0.0,
         "cost_center_code": "999"},
        {"account_code": "411101", "debit": 0.0, "credit": 100.0},
    ])
    assert ok is False
    assert "مركز التكلفة" in msg


def test_expense_account_balance_increases_with_debit(db):
    post_pair(db, "511101", "111101", 300.0, cc="101")
    assert db.get(Account, "511101").balance == pytest.approx(300.0)
    # الخزينة التي سُحبت منها القيمة تُقيّد دائنة فينخفض أصلها
    assert db.get(Account, "111101").balance == pytest.approx(-300.0)


def test_liability_balance_rises_on_credit(db):
    # قيد: مدين 111101 (أصل) دائن 211101 (التزام) - كإثبات منحة مؤجلة
    post_pair(db, "111101", "211101", 700.0, cc="101")
    # الالتزام يُقيّد دائناً فيرتفع (عكس الأصول)
    assert db.get(Account, "211101").balance == pytest.approx(700.0)
    assert db.get(Account, "111101").balance == pytest.approx(700.0)


def test_parent_rollup_equals_sum_of_children(db):
    post_pair(db, "111101", "411101", 200.0, cc="101")
    post_pair(db, "111102", "412101", 300.0, cc="103")
    assert db.get(Account, "111").balance == pytest.approx(500.0)
    assert db.get(Account, "11").balance == pytest.approx(500.0)
    assert db.get(Account, "1").balance == pytest.approx(500.0)


def test_joint_cost_allocation_50_30_20(db):
    ok, msg = AccountingService.execute_joint_cost_allocation(db, 1000.0)
    assert ok is True
    assert db.get(Account, "522102").balance == pytest.approx(500.0)
    assert db.get(Account, "511102").balance == pytest.approx(300.0)
    assert db.get(Account, "531103").balance == pytest.approx(200.0)
    assert db.get(Account, "111101").balance == pytest.approx(-1000.0)
    # مراكز التكلفة: الورشة 50%، التدريب 30%، الإدارة 20%
    assert db.get(CostCenter, "201").balance == pytest.approx(500.0)
    assert db.get(CostCenter, "103").balance == pytest.approx(300.0)
    assert db.get(CostCenter, "300").balance == pytest.approx(200.0)


def test_donor_report_variance(db):
    post_pair(db, "511101", "111101", 400.0, cc="101")
    rows, total_budget, total_actual, variance = AccountingService.generate_donor_report(
        db, "101", {"511101": 1000.0}
    )
    assert len(rows) == 1
    assert rows[0]["actual"] == pytest.approx(400.0)
    assert rows[0]["budget"] == pytest.approx(1000.0)
    assert rows[0]["variance"] == pytest.approx(600.0)
    assert total_budget == pytest.approx(1000.0)
    assert total_actual == pytest.approx(400.0)
    assert variance == pytest.approx(600.0)


def test_get_balances_surplus(db):
    # إيراد 1000 - مصروف 300 = فائض 700
    post_pair(db, "111101", "411101", 1000.0, cc="101")
    post_pair(db, "511101", "111101", 300.0, cc="101")
    b = AccountingService.get_balances(db)
    assert b["revenues"] == pytest.approx(1000.0)
    assert b["expenses"] == pytest.approx(300.0)
    assert b["surplus"] == pytest.approx(700.0)
    assert b["assets"] == pytest.approx(700.0)  # 1000 دخل - 300 خرج