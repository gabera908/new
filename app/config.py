# -*- coding: utf-8 -*-
"""إعدادات النظام وإدارة المتغيرات البيئية"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# قاعدة البيانات: PostgreSQL في الإنتاج (Docker)، SQLite للتشغيل المحلي الافتراضي
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{BASE_DIR / 'ngo_accounting.db'}",
)

APP_NAME = "نظام الحوكمة المالي والمخزني المتكامل للمؤسسات الأهلية والوحدات الإنتاجية"
VERSION = "2026.1.0"
DEFAULT_CURRENCY = "ج.م"
SECRET_KEY = os.getenv("SECRET_KEY", "ngo-secret-key-2026-change-in-production")
SESSION_COOKIE = "ngo_session"