# -*- coding: utf-8 -*-
"""Fixtures: قاعدة بيانات SQLite عزل كامل (في الذاكرة) لكل اختبار"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Account, CostCenter, InventoryItem


def _seed(session):
    """مخطط مصغر لدليل الحسابات ومراكز التكلفة والأصناف"""
    mini_coa = [
        # 1. الأصول
        ("1", "الأصول", "Assets", 1),
        ("11", "الأصول المتداولة", "Assets", 2),
        ("111", "النقدية وما يعادلها", "Assets", 3),
        ("1111", "حسابات الصناديق والخزائن", "Assets", 4),
        ("111101", "خزينة المؤسسة الرئيسية العامة", "Assets", 5),
        ("111102", "خزينة الوحدة الإنتاجية", "Assets", 5),
        # 2. الالتزامات
        ("2", "الالتزامات", "Liabilities", 1),
        ("21", "الالتزامات المتداولة", "Liabilities", 2),
        ("211101", "إيرادات منح مؤجلة", "Liabilities", 5),
        # 3. صافي الأصول
        ("3", "صافي الأصول والاحتياطيات", "NetAssets", 1),
        ("31", "أموال المؤسسة الحرة والمقيدة", "NetAssets", 2),
        ("311101", "صافي أصول غير مقيدة", "NetAssets", 5),
        # 4. الإيرادات
        ("4", "الإيرادات", "Revenues", 1),
        ("41", "إيرادات الأنشطة والمنح التنموية", "Revenues", 2),
        ("411101", "منح تمويل مشاريع خارجية", "Revenues", 5),
        ("412101", "رسوم اشتراك تدريبات القاعات", "Revenues", 5),
        # 5. المصروفات
        ("5", "المصروفات", "Expenses", 1),
        ("51", "مصروفات المشاريع والأنشطة التنموية", "Expenses", 2),
        ("511101", "أجور مدربين ومستشارين خارجيين", "Expenses", 5),
        ("511102", "خامات وأدوات تدريبية وضيافة", "Expenses", 5),
        ("52", "تكاليف الوحدة الإنتاجية والورش", "Expenses", 2),
        ("522102", "استهلاك وإهلاك آلات ومعدات الورشة", "Expenses", 5),
        ("53", "المصروفات الإدارية والعمومية", "Expenses", 2),
        ("531103", "فواتير الكهرباء والمياه والإنترنت", "Expenses", 5),
    ]
    for code, name, acc_type, level in mini_coa:
        session.add(Account(account_code=code, account_name=name, account_type=acc_type,
                            account_level=level, is_selectable=(level == 5)))

    for code, name, ctype in [
        ("101", "مشروع أ - الممول خارجياً", "NGO_PROJECT"),
        ("103", "برنامج التدريبات بالقاعات", "WORKSHOP"),
        ("201", "خط إنتاج الحلي", "WORKSHOP"),
        ("300", "المصروفات الإدارية والعمومية", "ADMIN"),
    ]:
        session.add(CostCenter(center_code=code, center_name=name, center_type=ctype))

    session.add(InventoryItem(id=1, item_code="RAW-001", item_name="جلود طبيعية خام",
                              category="RAW_MATERIAL", unit="متر",
                              quantity=50.0, unit_cost=150.0, reorder_level=20.0))
    session.add(InventoryItem(id=2, item_code="RAW-002", item_name="أحجار كريمة فاخرة",
                              category="RAW_MATERIAL", unit="قطعة",
                              quantity=0.0, unit_cost=250.0, reorder_level=10.0))
    session.commit()


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    _seed(session)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()