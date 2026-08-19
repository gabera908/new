# -*- coding: utf-8 -*-
"""مصادقة المستخدمين وإدارة الجلسات (Session-based)"""
import bcrypt
from fastapi import Request
from starlette.responses import RedirectResponse

from .config import SESSION_COOKIE
from .models import User


def hash_password(password: str) -> str:
    # bcrypt يفرض حد أقصى 72 بايت
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], password_hash.encode("utf-8"))
    except Exception:
        return False


def login_user(request: Request, user: User) -> None:
    request.session[SESSION_COOKIE] = {"user_id": user.id, "username": user.username, "role": user.role}


def logout_user(request: Request) -> None:
    request.session.pop(SESSION_COOKIE, None)


def get_current_user(request: Request) -> User | None:
    data = request.session.get(SESSION_COOKIE)
    if not data:
        return None
    from .database import SessionLocal
    db = SessionLocal()
    try:
        return db.get(User, data.get("user_id"))
    finally:
        db.close()


def require_login(request: Request, db, permission: str = None):
    """حارس الصلاحيات: يعيد المستخدم أو يعيد التوجيه لصفحة الدخول/الممنوع"""
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse("/login", status_code=303)
    if permission:
        from .rbac import has_permission
        if not has_permission(user.role, permission):
            return user, RedirectResponse("/forbidden", status_code=303)
    return user, None