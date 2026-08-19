# -*- coding: utf-8 -*-
"""تسجيل المسار التفتيشي الأمني (Audit Trail)"""
from sqlalchemy.orm import Session

from .. import models


def log_security_event(db: Session, user_id, username, action_type, description, ip_address="Intranet_IP"):
    """تسجيل أي حركة برمجية حساسة في سجل أمني غير قابل للحذف أو التعديل"""
    log = models.AuditLog(
        user_id=user_id,
        username=username,
        action_type=action_type,
        description=description,
        ip_address=ip_address,
    )
    db.add(log)
    db.commit()