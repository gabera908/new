# -*- coding: utf-8 -*-
"""اختبارات وحدة: الخدمات المخزنية (أذونات الاستلام والصرف وطلبات الصرف)"""
import pytest

from app.models import InventoryItem, InventoryTransaction, MaterialRequest, AuditLog
from app.services.inventory_service import InventoryService


def test_receipt_increases_quantity_and_logs(db):
    ok, msg = InventoryService.record_transaction(
        db, "RCT-TEST-1", "RECEIPT", 1, 20.0, "WO-001", user_id=2, username="storekeeper")
    assert ok is True
    assert db.get(InventoryItem, 1).quantity == pytest.approx(70.0)
    tx = db.query(InventoryTransaction).order_by(InventoryTransaction.id.desc()).first()
    assert tx.trans_type == "RECEIPT"
    assert tx.quantity == pytest.approx(20.0)
    log = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    assert log.action_type == "INVENTORY"


def test_issue_decreases_quantity(db):
    ok, msg = InventoryService.record_transaction(
        db, "ISS-TEST-1", "ISSUE", 1, 10.0, "WO-002", user_id=2, username="storekeeper")
    assert ok is True
    assert db.get(InventoryItem, 1).quantity == pytest.approx(40.0)


def test_issue_over_stock_rejected(db):
    ok, msg = InventoryService.record_transaction(
        db, "ISS-TEST-2", "ISSUE", 1, 999.0, "WO-003", user_id=2, username="storekeeper")
    assert ok is False
    assert "رصيد غير كافٍ" in msg
    assert db.get(InventoryItem, 1).quantity == pytest.approx(50.0)


def test_transaction_missing_item_rejected(db):
    ok, msg = InventoryService.record_transaction(
        db, "RCT-TEST-2", "RECEIPT", 999, 5.0, "WO-004", user_id=2, username="storekeeper")
    assert ok is False
    assert "غير موجود" in msg


def test_material_request_created_pending_and_does_not_touch_balance(db):
    ok, msg = InventoryService.create_material_request(
        db, 1, 15.0, "أمر تشغيل الحلي", user_id=3, username="supervisor")
    assert ok is True
    assert db.get(InventoryItem, 1).quantity == pytest.approx(50.0)  # لا يتحكم في الأرصدة
    req = db.query(MaterialRequest).order_by(MaterialRequest.id.desc()).first()
    assert req.status == "PENDING"
    assert req.exceptional is False
    log = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    assert log.action_type == "INVENTORY_REQUEST"


def test_exceptional_material_request_flagged(db):
    ok, msg = InventoryService.create_material_request(
        db, 2, 3.0, "أحجار كريمة فاخرة لقطع خاصة", user_id=3, username="supervisor",
        exceptional=True)
    assert ok is True
    req = db.query(MaterialRequest).order_by(MaterialRequest.id.desc()).first()
    assert req.exceptional is True
    assert "استثنائي" in msg


def test_material_request_zero_or_negative_quantity_rejected(db):
    ok, msg = InventoryService.create_material_request(
        db, 1, 0.0, "بدون سبب", user_id=3, username="supervisor")
    assert ok is False
    assert "أكبر من صفر" in msg
    ok2, _ = InventoryService.create_material_request(
        db, 1, -5.0, "بدون سبب", user_id=3, username="supervisor")
    assert ok2 is False


def test_approve_request_issues_stock(db):
    InventoryService.create_material_request(
        db, 1, 20.0, "أمر تشغيل معتمد", user_id=3, username="supervisor")
    req = db.query(MaterialRequest).order_by(MaterialRequest.id.desc()).first()
    ok, msg = InventoryService.approve_material_request(
        db, req.id, approve=True, user_id=2, username="storekeeper")
    assert ok is True
    assert db.get(MaterialRequest, req.id).status == "APPROVED"
    assert db.get(InventoryItem, 1).quantity == pytest.approx(30.0)  # 50 - 20
    tx = db.query(InventoryTransaction).order_by(InventoryTransaction.id.desc()).first()
    assert tx.trans_type == "ISSUE"
    assert tx.quantity == pytest.approx(20.0)


def test_reject_request_leaves_stock_untouched(db):
    InventoryService.create_material_request(
        db, 1, 20.0, "أمر تشغيل", user_id=3, username="supervisor")
    req = db.query(MaterialRequest).order_by(MaterialRequest.id.desc()).first()
    ok, msg = InventoryService.approve_material_request(
        db, req.id, approve=False, user_id=2, username="storekeeper")
    assert ok is True
    assert db.get(MaterialRequest, req.id).status == "REJECTED"
    assert db.get(InventoryItem, 1).quantity == pytest.approx(50.0)


def test_approve_request_insufficient_stock_rejected(db):
    InventoryService.create_material_request(
        db, 1, 500.0, "أمر تشغيل", user_id=3, username="supervisor")
    req = db.query(MaterialRequest).order_by(MaterialRequest.id.desc()).first()
    ok, msg = InventoryService.approve_material_request(
        db, req.id, approve=True, user_id=2, username="storekeeper")
    assert ok is False
    assert "رصيد غير كافٍ" in msg
    assert db.get(MaterialRequest, req.id).status == "PENDING"


def test_approve_already_processed_request_rejected(db):
    InventoryService.create_material_request(
        db, 1, 10.0, "أمر تشغيل", user_id=3, username="supervisor")
    req = db.query(MaterialRequest).order_by(MaterialRequest.id.desc()).first()
    InventoryService.approve_material_request(db, req.id, approve=True,
                                              user_id=2, username="storekeeper")
    ok, msg = InventoryService.approve_material_request(
        db, req.id, approve=True, user_id=2, username="storekeeper")
    assert ok is False
    assert "سبق معالجته" in msg