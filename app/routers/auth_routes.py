# -*- coding: utf-8 -*-
"""شاشات تسجيل الدخول والصلاحيات"""
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..auth import verify_password, login_user, logout_user, get_current_user
from ..services.audit_service import log_security_event
from ..rbac import role_label

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {})


@router.post("/login")
def login_submit(request: Request, username: str = Form(...), password: str = Form(...),
                 db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash) or not user.is_active:
        return templates.TemplateResponse(
            request, "login.html",
            {"error": "اسم المستخدم أو كلمة المرور غير صحيحة."}, status_code=401)
    login_user(request, user)
    log_security_event(db, user.id, user.username, "LOGIN", "تسجيل دخول ناجح")
    return RedirectResponse("/", status_code=303)


@router.get("/logout")
def logout(request: Request):
    logout_user(request)
    return RedirectResponse("/login", status_code=303)


@router.get("/forbidden")
def forbidden(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse(
        request, "forbidden.html",
        {"user": user, "role_label": role_label(user.role) if user else ""})