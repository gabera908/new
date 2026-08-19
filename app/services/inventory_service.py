# -*- coding: utf-8 -*-
"""الخدمات المخزنية: أذونات الاستلام والصرف بموجب أوامر الشغل المعتمدة"""
from datetime import datetime

from sqlalchemy.orm import Session

from .. import models
from .audit_service import log_security_event


class InventoryService:

    @staticmethod
    def record_transaction(db: Session, doc_number, trans_type, item_id,
                           quantity, reference_work_order, user_id, username):
        item = db.get(models.InventoryItem, item_id)
        if not item:
            return False, "الصنف غير موجود بالمخزن."

        # لا يسمح بالصرف يتجاوز الكمية المتاحة
        if trans_type == "ISSUE" and quantity > item.quantity:
            return False, f"رصيد غير كافٍ: المتاح {item.quantity:,.2f} {item.unit} والمطلوب {quantity:,.2f}."

        tx = models.InventoryTransaction(
            doc_number=doc_number, trans_type=trans_type, item_id=item_id,
            quantity=quantity, reference_work_order=reference_work_order,
            created_by=user_id,
        )
        db.add(tx)
        if trans_type == "RECEIPT":
            item.quantity += quantity
        else:
            item.quantity -= quantity
        db.commit()

        log_security_event(db, user_id, username, "INVENTORY",
                           f"{trans_type} {quantity} من {item.item_name} بأمر الشغل {reference_work_order}")

        return True, f"تم تسجيل الحركة المخزنية بنجاح. الرصيد الحالي: {item.quantity:,.2f} {item.unit}."

    @staticmethod
    def create_material_request(db: Session, item_id, quantity, reason, user_id, username,
                                exceptional=False):
        """طلب صرف خامات من مشرف الوحدة الإنتاجية (بلا تعديل أرصدة)
        exceptional=True لصرف الأحجار الكريمة الفاخرة (يعتمده المدير التنفيذي)"""
        item = db.get(models.InventoryItem, item_id)
        if not item:
            return False, "الصنف غير موجود بالمخزن."
        if quantity <= 0:
            return False, "الكمية المطلوبة يجب أن تكون أكبر من صفر."

        req = models.MaterialRequest(
            request_no=f"MRQ-{datetime.now().strftime('%Y%m%d%H%M%S')}-{user_id}",
            item_id=item_id, quantity=quantity, reason=reason or "بدون سبب",
            exceptional=exceptional, requested_by=user_id,
        )
        db.add(req)
        db.commit()

        label = "طلب صرف استثنائي" if exceptional else "طلب صرف"
        log_security_event(db, user_id, username, "INVENTORY_REQUEST",
                           f"{label} {quantity} من {item.item_name} (الرصيد الحالي {item.quantity:,.2f}) - بانتظار الاعتماد")
        return True, f"تم تسجيل {label} الخامات رقم {req.request_no} بانتظار الاعتماد."

    @staticmethod
    def approve_material_request(db: Session, request_id, approve, user_id, username):
        """اعتماد أو رفض طلب صرف خامات (لأمين المخزن)"""
        req = db.get(models.MaterialRequest, request_id)
        if not req:
            return False, "الطلب غير موجود."
        if req.status != "PENDING":
            return False, f"الطلب سبق معالجته (الحالة: {req.status})."

        item = db.get(models.InventoryItem, req.item_id)
        if approve:
            if req.quantity > item.quantity:
                return False, f"رصيد غير كافٍ لاعتماد الطلب: المتاح {item.quantity:,.2f} {item.unit}."
            req.status = "APPROVED"
            tx = models.InventoryTransaction(
                doc_number=f"ISSUE-{req.request_no}", trans_type="ISSUE",
                item_id=item.id, quantity=req.quantity,
                reference_work_order=req.reason or "طلب صرف معتمد",
                created_by=user_id,
            )
            db.add(tx)
            item.quantity -= req.quantity
            log_security_event(db, user_id, username, "INVENTORY",
                               f"صرف {req.quantity} من {item.item_name} بموجب طلب معتمد {req.request_no}")
        else:
            req.status = "REJECTED"
            log_security_event(db, user_id, username, "INVENTORY_REQUEST",
                               f"رفض طلب صرف {req.quantity} من {item.item_name} ({req.request_no})")
        req.approved_by = user_id
        req.approved_at = datetime.utcnow()
        db.commit()
        return True, "تم اعتماد الطلب." if approve else "تم رفض الطلب."