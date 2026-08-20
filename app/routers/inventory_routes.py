# -*- coding: utf-8 -*-
"""شاشة الحركات المخزنية لأمين المخزن"""
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import InventoryItem, InventoryTransaction, MaterialRequest
from ..services.inventory_service import InventoryService
from ..auth import require_login
from ..rbac import role_label, has_permission

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/inventory")
def inventory_page(request: Request, db: Session = Depends(get_db)):
    user, redirect = require_login(request, db, "inventory_view")
    if redirect:
        return redirect
    items = db.query(InventoryItem).all()
    txs = db.query(InventoryTransaction).order_by(InventoryTransaction.created_at.desc()).limit(20).all()
    reqs = db.query(MaterialRequest).order_by(MaterialRequest.requested_at.desc()).limit(20).all()
    can_edit = has_permission(user.role, "inventory_edit")
    can_request = has_permission(user.role, "inventory_request")
    can_approve = has_permission(user.role, "inventory_edit")
    can_approve_exceptional = has_permission(user.role, "approve_exceptional")
    return templates.TemplateResponse(request, "inventory.html", {
        "user": user, "role_label": role_label(user.role),
        "items": items, "transactions": txs, "requests": reqs,
        "can_edit": can_edit, "can_request": can_request, "can_approve": can_approve,
        "can_approve_exceptional": can_approve_exceptional,
    })


@router.post("/inventory/request")
def inventory_request(request: Request,
                      item_id: int = Form(...),
                      quantity: float = Form(...),
                      reason: str = Form(""),
                      exceptional: str = Form("no"),
                      db: Session = Depends(get_db)):
    user, redirect = require_login(request, db, "inventory_request")
    if redirect:
        return redirect
    ok, msg = InventoryService.create_material_request(
        db, item_id, quantity, reason, user.id, user.username,
        exceptional=(exceptional == "yes"))
    return _render_inventory(request, db, user, success=msg if ok else None,
                             error=msg if not ok else None)


@router.post("/inventory/request/decide")
def inventory_request_decide(request: Request,
                             request_id: int = Form(...),
                             approve: str = Form("no"),
                             db: Session = Depends(get_db)):
    req = db.get(MaterialRequest, request_id)
    if not req:
        user, redirect = require_login(request, db, "inventory_edit")
        if redirect:
            return redirect
        return _render_inventory(request, db, user, error="الطلب غير موجود")

    # الصرف الاستثنائي للأحجار الكريمة الفاخرة يعتمده المدير التنفيذي
    permission = "approve_exceptional" if req.exceptional else "inventory_edit"
    user, redirect = require_login(request, db, permission)
    if redirect:
        return redirect
    ok, msg = InventoryService.approve_material_request(
        db, request_id, approve == "yes", user.id, user.username)
    return _render_inventory(request, db, user, success=msg if ok else None,
                             error=msg if not ok else None)


def _render_inventory(request, db, user, success=None, error=None):
    items = db.query(InventoryItem).all()
    txs = db.query(InventoryTransaction).order_by(InventoryTransaction.created_at.desc()).limit(20).all()
    reqs = db.query(MaterialRequest).order_by(MaterialRequest.requested_at.desc()).limit(20).all()
    return templates.TemplateResponse(request, "inventory.html", {
        "user": user, "role_label": role_label(user.role),
        "items": items, "transactions": txs, "requests": reqs,
        "can_edit": has_permission(user.role, "inventory_edit"),
        "can_request": has_permission(user.role, "inventory_request"),
        "can_approve": has_permission(user.role, "inventory_edit"),
        "can_approve_exceptional": has_permission(user.role, "approve_exceptional"),
        "success": success, "error": error,
    })


@router.post("/inventory/transaction")
def inventory_post(request: Request,
                   trans_type: str = Form(...),
                   item_id: int = Form(...),
                   quantity: float = Form(...),
                   reference_work_order: str = Form(""),
                   db: Session = Depends(get_db)):
    user, redirect = require_login(request, db, "inventory_edit")
    if redirect:
        return redirect

    doc_number = f"{'RCPT' if trans_type == 'RECEIPT' else 'ISSUE'}-{user.id}-{quantity}"
    ok, msg = InventoryService.record_transaction(
        db, doc_number, trans_type, item_id, quantity,
        reference_work_order or "بدون أمر شغل", user.id, user.username)

    return _render_inventory(request, db, user, success=msg if ok else None,
                             error=msg if not ok else None)