# -*- coding: utf-8 -*-
"""شاشة إدخال القيود اليومية وسجل القيود"""
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Account, CostCenter, JournalEntry
from ..services.accounting_service import AccountingService
from ..services.audit_service import log_security_event
from ..auth import require_login
from ..rbac import role_label

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _require_admin(request: Request, db: Session):
    """مدير النظام فقط لتعديل/حذف القيود"""
    user, redirect = require_login(request, db)
    if redirect:
        return user, redirect
    if user.role != "admin":
        return user, RedirectResponse("/forbidden", status_code=303)
    return user, None


def _journal_form_context(db: Session, today=None, success=None, error=None):
    selectable = db.query(Account).filter(Account.is_selectable == True).order_by(Account.account_code).all()  # noqa: E712
    centers = db.query(CostCenter).all()
    entries = db.query(JournalEntry).order_by(JournalEntry.created_at.desc()).limit(20).all()
    return {
        "accounts": selectable, "centers": centers, "entries": entries,
        "today": today or date.today().isoformat(),
        "success": success, "error": error,
    }


@router.get("/journal")
def journal_page(request: Request, db: Session = Depends(get_db)):
    user, redirect = require_login(request, db, "journal_entry")
    if redirect:
        return redirect
    ctx = _journal_form_context(db,
                                success=request.query_params.get("msg"),
                                error=request.query_params.get("err"))
    return templates.TemplateResponse(request, "journal_entry.html", {
        "user": user, "role_label": role_label(user.role), **ctx,
    })


@router.post("/journal")
def journal_post(request: Request,
                 entry_date: str = Form(...),
                 description: str = Form(...),
                 account_codes: list[str] = Form(...),
                 cost_centers: list[str] = Form(default=[]),
                 debits: list[str] = Form(...),
                 credits: list[str] = Form(...),
                 notes_list: list[str] = Form(default=[]),
                 db: Session = Depends(get_db)):
    user, redirect = require_login(request, db, "journal_entry")
    if redirect:
        return redirect

    def to_float(val: str) -> float:
        try:
            return float(val) if val != "" else 0.0
        except (ValueError, TypeError):
            return 0.0

    debits_f = [to_float(d) for d in debits]
    credits_f = [to_float(c) for c in credits]

    lines = []
    for i, acc in enumerate(account_codes):
        cc = cost_centers[i] if i < len(cost_centers) and cost_centers[i] else None
        note = notes_list[i] if i < len(notes_list) else ""
        lines.append({"account_code": acc, "cost_center_code": cc,
                      "debit": debits_f[i], "credit": credits_f[i], "notes": note})

    try:
        entry_dt = date.fromisoformat(entry_date)
    except ValueError:
        entry_dt = date.today()

    ok, msg = AccountingService.post_entry(db, entry_dt, description, lines, user.id)
    log_security_event(db, user.id, user.username, "JOURNAL",
                       f"{'نجاح' if ok else 'رفض'} ترحيل قيد: {description} - {msg}")

    if ok:
        return RedirectResponse("/journal?msg=" + quote(msg), status_code=303)

    ctx = _journal_form_context(db, today=entry_date, success=None, error=msg)
    return templates.TemplateResponse(request, "journal_entry.html", {
        "user": user, "role_label": role_label(user.role), **ctx,
    })


@router.get("/journal/edit/{entry_id}")
def journal_edit_page(request: Request, entry_id: int,
                      db: Session = Depends(get_db)):
    user, redirect = _require_admin(request, db)
    if redirect:
        return redirect

    entry = db.get(JournalEntry, entry_id)
    if not entry:
        return RedirectResponse("/journal?err=" + quote("القيد غير موجود."), status_code=303)

    selectable = db.query(Account).filter(Account.is_selectable == True).order_by(Account.account_code).all()  # noqa: E712
    centers = db.query(CostCenter).all()
    return templates.TemplateResponse(request, "journal_edit.html", {
        "user": user, "role_label": role_label(user.role),
        "accounts": selectable, "centers": centers, "entry": entry,
        "error": request.query_params.get("err"),
    })


@router.post("/journal/edit/{entry_id}")
def journal_edit_post(request: Request, entry_id: int,
                      entry_date: str = Form(...),
                      description: str = Form(...),
                      account_codes: list[str] = Form(...),
                      cost_centers: list[str] = Form(default=[]),
                      debits: list[str] = Form(...),
                      credits: list[str] = Form(...),
                      notes_list: list[str] = Form(default=[]),
                      db: Session = Depends(get_db)):
    user, redirect = _require_admin(request, db)
    if redirect:
        return redirect

    def to_float(val: str) -> float:
        try:
            return float(val) if val != "" else 0.0
        except (ValueError, TypeError):
            return 0.0

    debits_f = [to_float(d) for d in debits]
    credits_f = [to_float(c) for c in credits]

    lines = []
    for i, acc in enumerate(account_codes):
        cc = cost_centers[i] if i < len(cost_centers) and cost_centers[i] else None
        note = notes_list[i] if i < len(notes_list) else ""
        lines.append({"account_code": acc, "cost_center_code": cc,
                      "debit": debits_f[i], "credit": credits_f[i], "notes": note})

    try:
        entry_dt = date.fromisoformat(entry_date)
    except ValueError:
        entry_dt = date.today()

    ok, msg = AccountingService.update_entry(db, entry_id, entry_dt, description, lines, user.id)
    log_security_event(db, user.id, user.username, "JOURNAL",
                       f"{'نجاح' if ok else 'رفض'} تعديل قيد #{entry_id}: {description} - {msg}")

    if ok:
        return RedirectResponse("/journal?msg=" + quote(msg), status_code=303)

    entry = db.get(JournalEntry, entry_id)
    selectable = db.query(Account).filter(Account.is_selectable == True).order_by(Account.account_code).all()  # noqa: E712
    centers = db.query(CostCenter).all()
    return templates.TemplateResponse(request, "journal_edit.html", {
        "user": user, "role_label": role_label(user.role),
        "accounts": selectable, "centers": centers, "entry": entry, "error": msg,
    })


@router.post("/journal/delete/{entry_id}")
def journal_delete_post(request: Request, entry_id: int,
                        db: Session = Depends(get_db)):
    user, redirect = _require_admin(request, db)
    if redirect:
        return redirect

    entry = db.get(JournalEntry, entry_id)
    if not entry:
        return RedirectResponse("/journal?err=" + quote("القيد غير موجود."), status_code=303)

    ok, msg = AccountingService.delete_entry(db, entry_id, user.id)
    log_security_event(db, user.id, user.username, "JOURNAL",
                       f"{'نجاح' if ok else 'رفض'} حذف قيد #{entry_id}: {msg}")

    q = "msg" if ok else "err"
    return RedirectResponse(f"/journal?{q}=" + quote(msg), status_code=303)