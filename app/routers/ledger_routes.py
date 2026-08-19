# -*- coding: utf-8 -*-
"""شاشات مدير النظام: شجرة الحسابات واليومية الأمريكية والأستاذ العام مع التصدير"""
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..auth import require_login
from ..database import get_db
from ..models import Account, BudgetProposal, JournalEntry, JournalEntryLine
from ..rbac import role_label
from ..services import export_service
from ..services.accounting_service import AccountingService
from ..services.audit_service import log_security_event

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

ACCOUNT_TYPES = ["Assets", "Liabilities", "NetAssets", "Revenues", "Expenses"]
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _require_admin(request: Request, db: Session):
    """مدير النظام فقط"""
    user, redirect = require_login(request, db)
    if redirect:
        return user, redirect
    if user.role != "admin":
        return user, RedirectResponse("/forbidden", status_code=303)
    return user, None


def _require_reports(request: Request, db: Session):
    """صلاحية التقارير: مدير النظام، المحاسب، والمدير التنفيذي"""
    return require_login(request, db, "reports")


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


def _chart_accounts(db: Session):
    """قائمة الحسابات المسطحة الكاملة للشاشة والتصدير"""
    accounts = []
    for a in db.query(Account).order_by(Account.account_code).all():
        accounts.append({
            "code": a.account_code, "name": a.account_name,
            "type": a.account_type, "level": a.account_level,
            "balance": a.balance, "selectable": a.is_selectable,
        })
    return accounts


def _chart_response(request: Request, db: Session, user, success=None, error=None):
    accounts = _chart_accounts(db)
    return templates.TemplateResponse(request, "chart.html", {
        "user": user, "role_label": role_label(user.role),
        "tree": _build_tree(accounts), "flat": accounts,
        "account_types": ACCOUNT_TYPES,
        "success": success, "error": error,
    })


def _next_account_code(db: Session, parent: Account | None) -> str:
    """توليد الكود التالي للحساب الجديد ضمن شجرة المستويات الخمسة"""
    if parent is None:
        existing = {a.account_code for a in
                    db.query(Account).filter(Account.account_level == 1).all()}
        n = 1
        while str(n) in existing:
            n += 1
        return str(n)

    prefix = parent.account_code
    if parent.account_level + 1 == 5:
        width = 6 - len(prefix)
    else:
        width = 1
    existing = {a.account_code for a in db.query(Account).all()}
    n = 1
    while True:
        code = prefix + str(n).zfill(width)
        if code not in existing:
            return code


def _american_rows(db: Session):
    """سطور اليومية الأمريكية للعرض والتصدير"""
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
    return rows


def _parse_date(value: str):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


# --------------------------------------------------------------------------
# شجرة الحسابات
# --------------------------------------------------------------------------
@router.get("/chart")
def chart_page(request: Request, db: Session = Depends(get_db)):
    user, redirect = _require_admin(request, db)
    if redirect:
        return redirect
    return _chart_response(
        request, db, user,
        success=request.query_params.get("msg"),
        error=request.query_params.get("err"),
    )


@router.post("/chart/add")
def chart_add(request: Request,
              account_name: str = Form(...),
              account_type: str = Form(...),
              parent_code: str = Form(default=""),
              db: Session = Depends(get_db)):
    user, redirect = _require_admin(request, db)
    if redirect:
        return redirect

    parent = db.get(Account, parent_code) if parent_code else None
    if parent and parent.account_level >= 5:
        return _chart_response(request, db, user, error="لا يمكن إضافة فرع تحت حساب ورقي (مستوى 5).")

    if parent:
        level = parent.account_level + 1
        account_type = parent.account_type
    else:
        level = 1
        if account_type not in ACCOUNT_TYPES:
            return _chart_response(request, db, user, error="نوع الحساب غير صالح.")

    code = _next_account_code(db, parent)
    acc = Account(
        account_code=code,
        account_name=account_name.strip(),
        account_type=account_type,
        account_level=level,
        is_selectable=(level == 5),
        parent_code=parent.account_code if parent else None,
    )
    db.add(acc)
    db.commit()
    AccountingService.update_balances(db)
    log_security_event(db, user.id, user.username, "CHART",
                       f"إضافة حساب {code} - {account_name.strip()} (مستوى {level})")
    return RedirectResponse("/chart?msg=" + quote(f"تمت إضافة الحساب {code} بنجاح."),
                            status_code=303)


@router.post("/chart/edit")
def chart_edit(request: Request,
               account_code: str = Form(...),
               account_name: str = Form(...),
               account_type: str = Form(...),
               is_selectable: str = Form(default=""),
               db: Session = Depends(get_db)):
    user, redirect = _require_admin(request, db)
    if redirect:
        return redirect

    acc = db.get(Account, account_code)
    if not acc:
        return _chart_response(request, db, user, error="الحساب غير موجود.")
    if acc.account_type != account_type:
        if account_type not in ACCOUNT_TYPES:
            return _chart_response(request, db, user, error="نوع الحساب غير صالح.")
        acc.account_type = account_type
    acc.account_name = account_name.strip()
    if acc.account_level == 5:
        acc.is_selectable = bool(is_selectable)

    db.commit()
    AccountingService.update_balances(db)
    log_security_event(db, user.id, user.username, "CHART",
                       f"تعديل حساب {acc.account_code} - {acc.account_name}")
    return RedirectResponse("/chart?msg=" + quote(f"تم تعديل الحساب {acc.account_code} بنجاح."),
                            status_code=303)


@router.post("/chart/delete")
def chart_delete(request: Request,
                 account_code: str = Form(...),
                 db: Session = Depends(get_db)):
    user, redirect = _require_admin(request, db)
    if redirect:
        return redirect

    acc = db.get(Account, account_code)
    if not acc:
        return _chart_response(request, db, user, error="الحساب غير موجود.")

    children = db.query(Account).filter(
        Account.account_code.like(f"{account_code}%"),
        Account.account_code != account_code,
    ).count()
    if children:
        return _chart_response(request, db, user,
                               error=f"لا يمكن حذف الحساب {account_code} لوجود حسابات فرعية تابعة له.")

    used_lines = db.query(JournalEntryLine).filter(
        JournalEntryLine.account_code == account_code).count()
    if used_lines:
        return _chart_response(request, db, user,
                               error=f"لا يمكن حذف الحساب {account_code} لوجود قيود يومية مسجلة عليه.")

    used_budget = db.query(BudgetProposal).filter(
        BudgetProposal.account_code == account_code).count()
    if used_budget:
        return _chart_response(request, db, user,
                               error=f"لا يمكن حذف الحساب {account_code} لوجود بنود موازنة مرتبطة به.")

    db.delete(acc)
    db.commit()
    AccountingService.update_balances(db)
    log_security_event(db, user.id, user.username, "CHART",
                       f"حذف حساب {account_code} - {acc.account_name}")
    return RedirectResponse("/chart?msg=" + quote(f"تم حذف الحساب {account_code} بنجاح."),
                            status_code=303)


@router.get("/chart/export")
def chart_export(request: Request, format: str = "pdf",
                 db: Session = Depends(get_db)):
    user, redirect = _require_admin(request, db)
    if redirect:
        return redirect
    accounts = _chart_accounts(db)
    if format == "xlsx":
        return Response(content=export_service.chart_excel(accounts),
                        media_type=_XLSX_MIME,
                        headers={"Content-Disposition": "attachment; filename=chart_of_accounts.xlsx"})
    return Response(content=export_service.chart_pdf(accounts),
                    media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=chart_of_accounts.pdf"})


# --------------------------------------------------------------------------
# اليومية الأمريكية
# --------------------------------------------------------------------------
@router.get("/journal-american")
def american_journal_page(request: Request, db: Session = Depends(get_db)):
    user, redirect = _require_admin(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(request, "american_journal.html", {
        "user": user, "role_label": role_label(user.role),
        "rows": _american_rows(db),
    })


@router.get("/journal-american/export")
def journal_export(request: Request, format: str = "pdf",
                   db: Session = Depends(get_db)):
    user, redirect = _require_admin(request, db)
    if redirect:
        return redirect
    rows = _american_rows(db)
    if format == "xlsx":
        return Response(content=export_service.journal_excel(rows),
                        media_type=_XLSX_MIME,
                        headers={"Content-Disposition": "attachment; filename=american_journal.xlsx"})
    return Response(content=export_service.journal_pdf(rows),
                    media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=american_journal.pdf"})


# --------------------------------------------------------------------------
# الأستاذ العام
# --------------------------------------------------------------------------
@router.get("/ledger")
def ledger_page(request: Request, account_code: str = "",
                from_date: str = "", to_date: str = "",
                db: Session = Depends(get_db)):
    user, redirect = _require_reports(request, db)
    if redirect:
        return redirect

    blocks = AccountingService.generate_ledger(
        db, account_code or None, _parse_date(from_date), _parse_date(to_date))
    selectable = db.query(Account).filter(Account.account_level == 5) \
        .order_by(Account.account_code).all()
    return templates.TemplateResponse(request, "ledger.html", {
        "user": user, "role_label": role_label(user.role),
        "blocks": blocks, "accounts": selectable,
        "account_code": account_code, "from_date": from_date, "to_date": to_date,
    })


@router.get("/ledger/export")
def ledger_export(request: Request, account_code: str = "",
                  from_date: str = "", to_date: str = "", format: str = "pdf",
                  db: Session = Depends(get_db)):
    user, redirect = _require_reports(request, db)
    if redirect:
        return redirect
    blocks = AccountingService.generate_ledger(
        db, account_code or None, _parse_date(from_date), _parse_date(to_date))
    if format == "xlsx":
        return Response(content=export_service.ledger_excel(blocks),
                        media_type=_XLSX_MIME,
                        headers={"Content-Disposition": "attachment; filename=general_ledger.xlsx"})
    return Response(content=export_service.ledger_pdf(blocks),
                    media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=general_ledger.pdf"})