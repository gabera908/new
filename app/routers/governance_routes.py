# -*- coding: utf-8 -*-
"""شاشات الحوكمة: اعتماد الموازنات السنوية وعقود تأجير الورشة"""
from datetime import date, datetime

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import BudgetProposal, RentalContract, Account, WorkshopHandover
from ..services.audit_service import log_security_event
from ..auth import require_login
from ..rbac import role_label, has_permission

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/budget")
def budget_page(request: Request, db: Session = Depends(get_db)):
    user, redirect = require_login(request, db)
    if redirect:
        return redirect
    if not (has_permission(user.role, "budget_propose") or has_permission(user.role, "approve_budget")):
        return RedirectResponse("/forbidden", status_code=303)
    return _render_budget(request, db, user)


@router.post("/budget")
def budget_post(request: Request,
                fiscal_year: str = Form(...),
                account_code: str = Form(...),
                proposed_amount: float = Form(...),
                db: Session = Depends(get_db)):
    user, redirect = require_login(request, db, "budget_propose")
    if redirect:
        return redirect

    ok = True
    msg = "تم إدراج البند بالموازنة السنوية بنجاح"
    if proposed_amount <= 0:
        ok, msg = False, "قيمة الموازنة يجب أن تكون أكبر من صفر"
    elif not account_code:
        ok, msg = False, "يجب اختيار بند المصروف المعتمد"
    else:
        prop = BudgetProposal(
            fiscal_year=fiscal_year.strip() or date.today().year,
            account_code=account_code,
            proposed_amount=proposed_amount,
            proposed_by=user.id,
        )
        db.add(prop)
        db.commit()
        log_security_event(db, user.id, user.username, "BUDGET_PROPOSE",
                           f"اقتراح بند موازنة {account_code} بسنة {fiscal_year} - {msg}")

    return _render_budget(request, db, user, success=msg if ok else None,
                          error=msg if not ok else None)


@router.post("/budget/decide")
def budget_decide(request: Request,
                  proposal_id: int = Form(...),
                  approve: str = Form("no"),
                  db: Session = Depends(get_db)):
    user, redirect = require_login(request, db, "approve_budget")
    if redirect:
        return redirect

    prop = db.get(BudgetProposal, proposal_id)
    if not prop:
        return _render_budget(request, db, user, error="بند الموازنة غير موجود")
    if prop.status != "PENDING":
        return _render_budget(request, db, user,
                              error="تم البت في هذا البند من قبل (غير قابل للتعديل)")

    prop.status = "APPROVED" if approve == "yes" else "REJECTED"
    prop.decided_by = user.id
    prop.decided_at = datetime.utcnow()
    db.commit()
    log_security_event(db, user.id, user.username, "BUDGET_DECIDE",
                       f"{'اعتماد' if approve == 'yes' else 'رفض'} بند موازنة {prop.account_code}")

    return _render_budget(request, db, user,
                          success="تم اعتماد بند الموازنة" if approve == "yes" else "تم رفض بند الموازنة")


@router.get("/rentals")
def rentals_page(request: Request, db: Session = Depends(get_db)):
    user, redirect = require_login(request, db)
    if redirect:
        return redirect
    if not (has_permission(user.role, "rental_review") or has_permission(user.role, "approve_rental")):
        return RedirectResponse("/forbidden", status_code=303)
    return _render_rentals(request, db, user)


@router.post("/rentals")
def rentals_post(request: Request,
                 contract_no: str = Form(...),
                 tenant_name: str = Form(...),
                 description: str = Form(""),
                 monthly_rent: float = Form(...),
                 start_date: str = Form(""),
                 end_date: str = Form(""),
                 db: Session = Depends(get_db)):
    user, redirect = require_login(request, db, "rental_review")
    if redirect:
        return redirect

    ok = True
    msg = "تم تسجيل عقد التأجير للمراجعة والاعتماد"
    if not contract_no or not tenant_name:
        ok, msg = False, "رقم العقد واسم المستأجر مطلوبان"
    elif monthly_rent <= 0:
        ok, msg = False, "قيمة الإيجار الشهري يجب أن تكون أكبر من صفر"
    else:
        try:
            sd = date.fromisoformat(start_date) if start_date else None
            ed = date.fromisoformat(end_date) if end_date else None
        except ValueError:
            sd = ed = None
        contract = RentalContract(
            contract_no=contract_no.strip(),
            tenant_name=tenant_name.strip(),
            description=description,
            monthly_rent=monthly_rent,
            start_date=sd,
            end_date=ed,
            created_by=user.id,
        )
        db.add(contract)
        db.commit()
        log_security_event(db, user.id, user.username, "RENTAL_CREATE",
                           f"تسجيل عقد تأجير {contract_no} للمستأجر {tenant_name} - {msg}")

    return _render_rentals(request, db, user, success=msg if ok else None,
                           error=msg if not ok else None)


@router.post("/rentals/review")
def rentals_review(request: Request,
                   contract_id: int = Form(...),
                   db: Session = Depends(get_db)):
    user, redirect = require_login(request, db, "rental_review")
    if redirect:
        return redirect

    contract = db.get(RentalContract, contract_id)
    if not contract:
        return _render_rentals(request, db, user, error="العقد غير موجود")
    if contract.status == "PENDING":
        contract.status = "REVIEWED"
        contract.reviewed_by = user.id
        contract.reviewed_at = datetime.utcnow()
        db.commit()
        log_security_event(db, user.id, user.username, "RENTAL_REVIEW",
                           f"مراجعة عقد تأجير {contract.contract_no}")
        return _render_rentals(request, db, user, success="تمت مراجعة العقد وجاهز للاعتماد")

    return _render_rentals(request, db, user,
                           error="لا يمكن مراجعة عقد في الحالة " + contract.status)


@router.post("/rentals/decide")
def rentals_decide(request: Request,
                   contract_id: int = Form(...),
                   approve: str = Form("no"),
                   db: Session = Depends(get_db)):
    user, redirect = require_login(request, db, "approve_rental")
    if redirect:
        return redirect

    contract = db.get(RentalContract, contract_id)
    if not contract:
        return _render_rentals(request, db, user, error="العقد غير موجود")
    if contract.status in ("APPROVED", "REJECTED"):
        return _render_rentals(request, db, user,
                               error="تم البت في هذا العقد من قبل (غير قابل للتعديل)")

    contract.status = "APPROVED" if approve == "yes" else "REJECTED"
    contract.decided_by = user.id
    contract.decided_at = datetime.utcnow()
    db.commit()
    log_security_event(db, user.id, user.username, "RENTAL_DECIDE",
                       f"{'اعتماد' if approve == 'yes' else 'رفض'} عقد تأجير {contract.contract_no}")

    return _render_rentals(request, db, user,
                           success="تم اعتماد عقد التأجير" if approve == "yes" else "تم رفض عقد التأجير")


def _render_budget(request, db, user, success=None, error=None):
    proposals = db.query(BudgetProposal).order_by(BudgetProposal.proposed_at.desc()).limit(30).all()
    accounts = (db.query(Account)
                .filter(Account.is_selectable == True, Account.account_type == "Expenses")  # noqa: E712
                .order_by(Account.account_code).all())
    return templates.TemplateResponse(request, "budget.html", {
        "user": user, "role_label": role_label(user.role),
        "proposals": proposals, "accounts": accounts,
        "today": date.today().isoformat(),
        "can_propose": has_permission(user.role, "budget_propose"),
        "can_decide": has_permission(user.role, "approve_budget"),
        "success": success, "error": error,
    })


def _render_rentals(request, db, user, success=None, error=None):
    contracts = db.query(RentalContract).order_by(RentalContract.created_at.desc()).limit(30).all()
    return templates.TemplateResponse(request, "rentals.html", {
        "user": user, "role_label": role_label(user.role),
        "contracts": contracts,
        "can_review": has_permission(user.role, "rental_review"),
        "can_decide": has_permission(user.role, "approve_rental"),
        "today": date.today().isoformat(),
        "success": success, "error": error,
    })


@router.get("/handover")
def handover_page(request: Request, db: Session = Depends(get_db)):
    user, redirect = require_login(request, db, "workshop_handover")
    if redirect:
        return redirect
    return _render_handover(request, db, user)


@router.post("/handover")
def handover_post(request: Request,
                  contract_id: int = Form(...),
                  equipment_status: str = Form(...),
                  notes: str = Form(""),
                  db: Session = Depends(get_db)):
    user, redirect = require_login(request, db, "workshop_handover")
    if redirect:
        return redirect

    contract = db.get(RentalContract, contract_id)
    if not contract:
        return _render_handover(request, db, user, error="العقد غير موجود")

    handover = WorkshopHandover(
        handover_no=f"HOV-{datetime.now().strftime('%Y%m%d%H%M%S')}-{user.id}",
        contract_id=contract.id,
        equipment_status=equipment_status.strip() or "تم فحص الآلات والمعدات وسلامتها",
        notes=notes,
        issued_by=user.id,
    )
    db.add(handover)
    db.commit()
    log_security_event(db, user.id, user.username, "WORKSHOP_HANDOVER",
                       f"إصدار إذن تسليم الورشة للعقد {contract.contract_no} - سلامة الآلات مؤكدة")

    return _render_handover(request, db, user, success=f"تم إصدار إذن التسليم رقم {handover.handover_no}")


def _render_handover(request, db, user, success=None, error=None):
    contracts = db.query(RentalContract).order_by(RentalContract.created_at.desc()).all()
    handovers = db.query(WorkshopHandover).order_by(WorkshopHandover.issued_at.desc()).limit(20).all()
    return templates.TemplateResponse(request, "handover.html", {
        "user": user, "role_label": role_label(user.role),
        "contracts": contracts, "handovers": handovers,
        "today": date.today().isoformat(),
        "success": success, "error": error,
    })