# -*- coding: utf-8 -*-
"""تطبيق FastAPI الرئيسي"""
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import SECRET_KEY, APP_NAME, VERSION
from .database import init_db
from .routers import auth_routes, journal_routes, inventory_routes, report_routes, governance_routes

app = FastAPI(title=APP_NAME, version=VERSION)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


def money_filter(value):
    """تنسيق المبالغ المالية بفواصل الآلاف ومنزلتين عشريتين (مثال: 15,000.00)"""
    try:
        return f"{float(value or 0):,.2f}"
    except (TypeError, ValueError):
        return "0.00"


# سجّل فلتر money على كل بيئات قوالب Jinja2 في التطبيق
from starlette.templating import Jinja2Templates

for _t in [auth_routes.templates, journal_routes.templates,
           inventory_routes.templates, report_routes.templates,
           governance_routes.templates]:
    _t.env.filters["money"] = money_filter

app.include_router(auth_routes.router)
app.include_router(journal_routes.router)
app.include_router(inventory_routes.router)
app.include_router(report_routes.router)
app.include_router(governance_routes.router)


@app.on_event("startup")
def on_startup():
    init_db()
    from .seed import seed_if_empty
    seed_if_empty()