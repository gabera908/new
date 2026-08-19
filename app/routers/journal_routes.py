# -*- coding: utf-8 -*-
"""شاشة إدخال القيود اليومية وسجل القيود"""
from datetime import date

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


@router.get("/journal")
def journal_page(request: Request, db: Session = Depends(get_db)):
    user, redirect = require_login(request, db, "journal_entry")
    if redirect:
        return redirect
    selectable = db.query(Account).filter(Account.is_selectable == True).order_by(Account.account_code).all()  # noqa: E712
    centers = db.query(CostCenter).all()
    entries = db.query(JournalEntry).order_by(JournalEntry.created_at.desc()).limit(20).all()
    return templates.TemplateResponse(request, "journal_entry.html", {
        "user": user, "role_label": role_label(user.role),
        "accounts": selectable, "centers": centers, "entries": entries,
        "today": date.today().isoformat(),
    })


@router.post("/journal")
def journal_post(request: Request,
                 entry_date: str = Form(...),
                 description: str = Form(...),
                 account_codes: list[str] = Form(...),
                 cost_centers: list[str] = Form(default=[]),
                 debits: list[float] = Form(...),
                 credits: list[float] = Form(...),
                 notes_list: list[str] = Form(default=[]),
                 db: Session = Depends(get_db)):
    user, redirect = require_login(request, db, "journal_entry")
    if redirect:
        return redirect

    lines = []
    for i, acc in enumerate(account_codes):
        cc = cost_centers[i] if i < len(cost_centers) and cost_centers[i] else None
        note = notes_list[i] if i < len(notes_list) else ""
        lines.append({"account_code": acc, "cost_center_code": cc,
                      "debit": debits[i], "credit": credits[i], "notes": note})

    try:
        entry_dt = date.fromisoformat(entry_date)
    except ValueError:
        entry_dt = date.today()

    ok, msg = AccountingService.post_entry(db, entry_dt, description, lines, user.id)
    log_security_event(db, user.id, user.username, "JOURNAL",
                       f"{'نجاح' if ok else 'رفض'} ترحيل قيد: {description} - {msg}")

    selectable = db.query(Account).filter(Account.is_selectable == True).order_by(Account.account_code).all()  # noqa: E712
    centers = db.query(CostCenter).all()
    entries = db.query(JournalEntry).order_by(JournalEntry.created_at.desc()).limit(20).all()
    return templates.TemplateResponse(request, "journal_entry.html", {
        "user": user, "role_label": role_label(user.role),
        "accounts": selectable, "centers": centers, "entries": entries,
        "today": entry_date, "success": msg if ok else None, "error": msg if not ok else None,
    })