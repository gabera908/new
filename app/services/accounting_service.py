# -*- coding: utf-8 -*-
"""الخدمات المالية والمحاسبية"""
from datetime import datetime

from sqlalchemy.orm import Session

from .. import models


class AccountingService:
    """محرك القيود اليومية وقواعد الحوكمة"""

    @staticmethod
    def post_entry(db: Session, date, description, lines_data, user_id=None):
        """ترحيل قيد يومية مع قواعد الحوكمة الإلزامية"""
        # قاعدة الحوكمة 1: جميع الحسابات يجب أن تكون في المستوى الخامس (أوراق شجرة)
        for ld in lines_data:
            acc = db.get(models.Account, ld["account_code"])
            if not acc:
                return False, f"خطأ حوكمة: كود الحساب {ld['account_code']} غير موجود بالنظام."
            if not acc.is_selectable or acc.account_level != 5:
                return False, f"قاعدة حوكمة رقم 1: الحساب {acc.account_name} ليس في المستوى 5. يمنع النظام القيد على حسابات المراقبة أو الحسابات الأب."

            if ld.get("cost_center_code"):
                cc = db.get(models.CostCenter, ld["cost_center_code"])
                if not cc:
                    return False, f"مركز التكلفة {ld['cost_center_code']} غير موجود."

        # قاعدة التوازن الإجباري (Double-Entry Validation)
        total_debit = sum(ld.get("debit", 0.0) or 0.0 for ld in lines_data)
        total_credit = sum(ld.get("credit", 0.0) or 0.0 for ld in lines_data)
        if abs(total_debit - total_credit) >= 0.001:
            return False, f"خطأ توازن: إجمالي المدين ({total_debit:,.2f}) لا يساوي إجمالي الدائن ({total_credit:,.2f})."

        # إنشاء القيد وسطوره
        entry = models.JournalEntry(
            entry_date=date, description=description, created_by=user_id
        )
        db.add(entry)
        db.flush()

        for ld in lines_data:
            line = models.JournalEntryLine(
                entry_id=entry.id,
                account_code=ld["account_code"],
                cost_center_code=ld.get("cost_center_code"),
                debit=ld.get("debit", 0.0) or 0.0,
                credit=ld.get("credit", 0.0) or 0.0,
                notes=ld.get("notes", ""),
            )
            db.add(line)

        db.commit()
        AccountingService.update_balances(db)
        return True, f"تم ترحيل القيد رقم {entry.id} بنجاح وتحديث الحسابات ومراكز التكلفة المرتبطة."

    @staticmethod
    def update_balances(db: Session):
        """إعادة حساب أرصدة الحسابات ومراكز التكلفة (Roll-up من المستوى 5 إلى 1)"""
        for acc in db.query(models.Account).all():
            acc.balance = 0.0
        for cc in db.query(models.CostCenter).all():
            cc.balance = 0.0

        for line in db.query(models.JournalEntryLine).all():
            acc = db.get(models.Account, line.account_code)
            delta = line.debit - line.credit
            if acc.account_type in ("Assets", "Expenses"):
                acc.balance += delta
            else:
                acc.balance += (line.credit - line.debit)

            if line.cost_center_code:
                cc = db.get(models.CostCenter, line.cost_center_code)
                if acc.account_type in ("Assets", "Expenses"):
                    cc.balance += delta
                else:
                    cc.balance += (line.credit - line.debit)

        # تجميع الحسابات الأب (مستوى أقل من 5) من الأبناء
        for parent in db.query(models.Account).filter(models.Account.account_level < 5).all():
            children = db.query(models.Account).filter(
                models.Account.account_code.like(f"{parent.account_code}%"),
                models.Account.account_code != parent.account_code,
                models.Account.account_level == 5,
            ).all()
            parent.balance = sum(c.balance for c in children)

        db.commit()

    @staticmethod
    def execute_joint_cost_allocation(db: Session, total_amount: float, user_id=None):
        """محرك المعادلات الآلي لتوزيع التكاليف المشتركة (الطاقة والماء)
        نسب التوزيع: الورشة 50%، التدريب بالقاعات 30%، الإدارة العامة 20%"""
        workshop = total_amount * 0.50
        training = total_amount * 0.30
        admin = total_amount * 0.20
        lines = [
            {"account_code": "522102", "debit": workshop, "credit": 0.0,
             "cost_center_code": "201", "notes": "توزيع مبرمج تلقائي - نصيب تشغيل الورشة 50%"},
            {"account_code": "511102", "debit": training, "credit": 0.0,
             "cost_center_code": "103", "notes": "توزيع مبرمج تلقائي - نصيب قاعات التدريب 30%"},
            {"account_code": "531103", "debit": admin, "credit": 0.0,
             "cost_center_code": "300", "notes": "توزيع مبرمج تلقائي - نصيب الإدارة العامة 20%"},
            {"account_code": "111101", "debit": 0.0, "credit": total_amount,
             "cost_center_code": None, "notes": "السداد الفعلي المشترك من الخزينة الرئيسية"},
        ]
        return AccountingService.post_entry(
            db, datetime.now().date(),
            "قيد توزيع مصاريف الطاقة والمياه المشتركة آلياً بحسب معايير المساحة والمعدات",
            lines, user_id,
        )

    @staticmethod
    def generate_donor_report(db: Session, cost_center_code: str, budget_dict: dict):
        """تقرير المقارنة المالي والتحليل الانحرافي للمانح الخارجي"""
        rows = []
        total_budget = 0.0
        total_actual = 0.0
        for acc_code, budget_val in budget_dict.items():
            acc = db.get(models.Account, acc_code)
            actual = 0.0
            for line in db.query(models.JournalEntryLine).filter_by(
                account_code=acc_code, cost_center_code=cost_center_code
            ).all():
                if acc.account_type == "Expenses":
                    actual += line.debit - line.credit
                else:
                    actual += line.credit - line.debit
            rows.append({
                "name": acc.account_name if acc else acc_code,
                "code": acc_code,
                "budget": budget_val,
                "actual": actual,
                "variance": budget_val - actual,
            })
            total_budget += budget_val
            total_actual += actual
        return rows, total_budget, total_actual, total_budget - total_actual

    @staticmethod
    def get_balances(db: Session):
        """أرصدة الحسابات من المستوى الأول للوحة القيادة"""
        level1 = {a.account_code: a.balance for a in
                  db.query(models.Account).filter(models.Account.account_level == 1).all()}
        assets = level1.get("1", 0.0)
        expenses = level1.get("5", 0.0)
        revenues = level1.get("4", 0.0)
        surplus = revenues - expenses
        return {"assets": assets, "expenses": expenses, "revenues": revenues, "surplus": surplus}