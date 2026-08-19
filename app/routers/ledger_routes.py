# -*- coding: utf-8 -*-
"""شاشات مدير النظام: شجرة الحسابات واليومية الأمريكية"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Account, JournalEntry
from ..auth import require_login
from ..rbac import role_label

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _require_admin(request: Request, db: Session):
    """مدير النظام فقط"""
    user, redirect = require_login(request, db)
    if redirect:
        return user, redirect
    if user.role != "admin":
        return user, RedirectResponse("/forbidden", status_code=303)
    return user, None


def _build_tree(accounts):
    """بناء شجرة دليل الحسابات من قائمة الحسابات المسطحة (كود البادئة = الأب)"""
    by_code = {a["code"]: dict(a, children=[]) for a in accounts}
    roots = []
    for code, node in by_code.items():
        parent = next((c for c in by_code if code.startswith(c) and c != code and len(c) < len(code)), None)
        if parent:
            by_code[parent]["children"].append(node)
        else:
            roots.append(node)
    for node in by_code.values():
        node["children"].sort(key=lambda x: x["code"])
    roots.sort(key=lambda x: x["code"])
    return roots


@router.get("/chart")
def chart_page(request: Request, db: Session = Depends(get_db)):
    user, redirect = _require_admin(request, db)
    if redirect:
        return redirect

    accounts = []
    for a in db.query(Account).order_by(Account.account_code).all():
        accounts.append({
            "code": a.account_code, "name": a.account_name,
            "type": a.account_type, "level": a.account_level,
            "balance": a.balance, "selectable": a.is_selectable,
        })
    tree = _build_tree(accounts)
    return templates.TemplateResponse(request, "chart.html", {
        "user": user, "role_label": role_label(user.role), "tree": tree,
    })


@router.get("/journal-american")
def american_journal_page(request: Request, db: Session = Depends(get_db)):
    user, redirect = _require_admin(request, db)
    if redirect:
        return redirect

    entries = db.query(JournalEntry).order_by(JournalEntry.entry_date, JournalEntry.id).all()
    rows = []
    for e in entries:
        for line in sorted(e.lines, key=lambda x: x.id):
            rows.append({
                "date": e.entry_date, "entry_id": e.id, "description": e.description,
                "account_code": line.account_code,
                "account_name": line.account.account_name if line.account else line.account_code,
                "debit": float(line.debit or 0.0), "credit": float(line.credit or 0.0),
            })
    return templates.TemplateResponse(request, "american_journal.html", {
        "user": user, "role_label": role_label(user.role), "rows": rows,
    })