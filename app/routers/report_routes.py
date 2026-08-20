# -*- coding: utf-8 -*-
"""لوحة قيادة مجلس الإدارة والتقارير"""
from datetime import date

from fastapi import APIRouter, Depends, Request, Form
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CostCenter, Account, InventoryItem, AuditLog, BudgetProposal
from ..services.accounting_service import AccountingService
from ..auth import require_login
from ..rbac import role_label

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _dashboard_context(db: Session):
    """كل بيانات لوحة القيادة تُجلب طازجة من قاعدة البيانات عند كل فتح/تحديث"""
    balances = AccountingService.get_balances(db)
    centers = db.query(CostCenter).all()
    center_data = [{"code": c.center_code, "name": c.center_name, "balance": c.balance} for c in centers]

    # موازنة المانحين من بنود الموازنة المعتمدة في قاعدة البيانات (سنة مالية الحالية)
    budget_dict = {
        p.account_code: p.proposed_amount
        for p in db.query(BudgetProposal).filter(
            BudgetProposal.status == "APPROVED",
            BudgetProposal.fiscal_year == str(date.today().year),
        ).all()
    }
    donor_rows, donor_budget, donor_actual, donor_variance = AccountingService.generate_donor_report(
        db, "101", budget_dict
    )

    items = db.query(InventoryItem).all()
    low_stock = [i for i in items if i.quantity <= i.reorder_level]
    recent_audit = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(10).all()

    return {
        "balances": balances, "currency": "ج.م",
        "center_data": center_data,
        "donor_rows": donor_rows, "donor_budget": donor_budget,
        "donor_actual": donor_actual, "donor_variance": donor_variance,
        "low_stock": low_stock, "audit_logs": recent_audit,
    }


@router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db)):
    user, redirect = require_login(request, db, "dashboard")
    if redirect:
        return redirect
    return templates.TemplateResponse(request, "dashboard.html", {
        "user": user, "role_label": role_label(user.role), **_dashboard_context(db),
    })


@router.get("/reports")
def reports(request: Request, db: Session = Depends(get_db)):
    user, redirect = require_login(request, db, "reports")
    if redirect:
        return redirect

    centers = db.query(CostCenter).all()
    accounts = db.query(Account).filter(Account.account_level == 5).all()
    return templates.TemplateResponse(request, "reports.html", {
        "user": user, "role_label": role_label(user.role),
        "centers": centers, "accounts": accounts,
    })


@router.post("/reports")
def reports_post(request: Request,
                 center_code: str = Form(...),
                 acc_codes: list[str] = Form(...),
                 budgets: list[float] = Form(...),
                 db: Session = Depends(get_db)):
    user, redirect = require_login(request, db, "reports")
    if redirect:
        return redirect

    budget_dict = {}
    for code, val in zip(acc_codes, budgets):
        budget_dict[code] = val

    rows, total_budget, total_actual, total_variance = AccountingService.generate_donor_report(
        db, center_code, budget_dict)
    center = db.get(CostCenter, center_code)

    centers = db.query(CostCenter).all()
    accounts = db.query(Account).filter(Account.account_level == 5).all()
    return templates.TemplateResponse(request, "reports.html", {
        "user": user, "role_label": role_label(user.role),
        "centers": centers, "accounts": accounts,
        "result": rows, "total_budget": total_budget, "total_actual": total_actual,
        "total_variance": total_variance, "center": center,
    })


@router.post("/allocation")
def allocation_post(request: Request, amount: float = Form(...),
                    db: Session = Depends(get_db)):
    user, redirect = require_login(request, db, "allocation")
    if redirect:
        return redirect
    ok, msg = AccountingService.execute_joint_cost_allocation(db, amount, user.id)
    return templates.TemplateResponse(request, "dashboard.html", {
        "user": user, "role_label": role_label(user.role),
        **_dashboard_context(db),
        "success": msg if ok else None, "error": msg if not ok else None,
    })