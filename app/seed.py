# -*- coding: utf-8 -*-
"""تهيئة النظام: دليل الحسابات، مراكز التكلفة، المستخدمون، والبيانات التجريبية"""
from datetime import date

from .database import SessionLocal, init_db
from .models import Account, CostCenter, User, InventoryItem
from .auth import hash_password
from .services.accounting_service import AccountingService

COA = [
    # 1. الأصول
    ("1", "الأصول", "Assets", 1),
    ("11", "الأصول المتداولة", "Assets", 2),
    ("111", "النقدية وما يعادلها", "Assets", 3),
    ("1111", "حسابات الصناديق والخزائن", "Assets", 4),
    ("111101", "خزينة المؤسسة الرئيسية العامة", "Assets", 5),
    ("111102", "خزينة الوحدة الإنتاجية (الورشة)", "Assets", 5),
    ("1112", "حسابات البنوك", "Assets", 4),
    ("111201", "بنك مصر - الحساب الجاري العام", "Assets", 5),
    ("111202", "البنك الأهلي - حساب مشروع المانح الخارجي أ", "Assets", 5),
    ("112", "المخزون السلعي للوحدة الإنتاجية", "Assets", 3),
    ("112101", "مخزن المواد الخام (جلود طبيعية وأحجار)", "Assets", 5),
    ("112102", "مخزن إنتاج تحت التشغيل", "Assets", 5),
    ("112103", "مخزن إنتاج تام الصنع (حلي وحقائب جاهزة)", "Assets", 5),
    ("113", "مدينون وأرصدة مدينة أخرى", "Assets", 3),
    ("113103", "أرصدة مدينة - إيجار قاعات ومقرات مقدم", "Assets", 5),

    # 2. الالتزامات
    ("2", "الالتزامات", "Liabilities", 1),
    ("21", "الالتزامات المتداولة", "Liabilities", 2),
    ("211", "مخصصات وأرصدة دائنة أخرى", "Liabilities", 3),
    ("211101", "إيرادات منح مؤجلة (مشاريع ممولة لم تنفذ)", "Liabilities", 5),
    ("211103", "تأمينات مستردة للغير (تأمينات مستأجري الورشة)", "Liabilities", 5),

    # 3. صافي الأصول
    ("3", "صافي الأصول والاحتياطيات", "NetAssets", 1),
    ("31", "أموال المؤسسة الحرة والمقيدة", "NetAssets", 2),
    ("311101", "صافي أصول غير مقيدة (الفائض المتراكم)", "NetAssets", 5),
    ("311102", "صافي أصول مقيدة (أموال مخصصة لغرض محدد)", "NetAssets", 5),

    # 4. الإيرادات
    ("4", "الإيرادات", "Revenues", 1),
    ("41", "إيرادات الأنشطة والمنح التنموية", "Revenues", 2),
    ("411", "إيرادات التمويل الخارجي", "Revenues", 3),
    ("411101", "منح تمويل مشاريع خارجية", "Revenues", 5),
    ("412", "إيرادات التدريبات والخدمات", "Revenues", 3),
    ("412101", "رسوم اشتراك تدريبات القاعات", "Revenues", 5),
    ("42", "إيرادات النشاط الإنتاجي والاستثماري المستدام", "Revenues", 2),
    ("421", "مبيعات الوحدة الإنتاجية للجمهور", "Revenues", 3),
    ("421101", "مبيعات مشغولات الحلي الفنية", "Revenues", 5),
    ("421102", "مبيعات منتجات الجلد الطبيعي", "Revenues", 5),
    ("422", "إيرادات التشغيل للغير والتأجير", "Revenues", 3),
    ("422101", "إيرادات تأجير الورشة والأجهزة للجمعيات الأخرى", "Revenues", 5),

    # 5. المصروفات
    ("5", "المصروفات", "Expenses", 1),
    ("51", "مصروفات المشاريع والأنشطة التنموية", "Expenses", 2),
    ("511", "تكاليف برامج التدريب والمشاريع", "Expenses", 3),
    ("511101", "أجور مدربين ومستشارين خارجيين", "Expenses", 5),
    ("511102", "خامات وأدوات تدريبية وضيافة", "Expenses", 5),
    ("511103", "تكلفة إيجار القاعات والمقرات الخاصة بالمشاريع", "Expenses", 5),
    ("52", "تكاليف الوحدة الإنتاجية والورش", "Expenses", 2),
    ("521", "تكلفة الإنتاج والمبيعات (المواد المباشرة)", "Expenses", 3),
    ("521101", "تكلفة الجلود الطبيعية المستهلكة", "Expenses", 5),
    ("521102", "تكلفة معادن وإكسسوارات الحلي المستهلكة", "Expenses", 5),
    ("522", "مصروفات تشغيل وصيانة الورشة", "Expenses", 3),
    ("522101", "أجور وصيانة عمال وفنيي الورشة", "Expenses", 5),
    ("522102", "استهلاك وإهلاك آلات ومعدات الورشة", "Expenses", 5),
    ("53", "المصروفات الإدارية والعمومية (المقر الرئيسي)", "Expenses", 2),
    ("531101", "إيجار المقر الرئيسي والورشة المشترك", "Expenses", 5),
    ("531102", "رواتب الإدارة العامة والتنفيذية", "Expenses", 5),
    ("531103", "فواتير الكهرباء والمياه والإنترنت العامة", "Expenses", 5),
]

COST_CENTERS = [
    ("101", "مشروع أ - الممول من الجهة الخارجية X", "NGO_PROJECT"),
    ("102", "مشروع ب - الممول من الجهة الخارجية Y", "NGO_PROJECT"),
    ("103", "برنامج التدريبات والورش التعليمية بالقاعات", "WORKSHOP"),
    ("201", "خط إنتاج الحلي والمشغولات", "WORKSHOP"),
    ("202", "خط إنتاج المنتجات الجلدية الطبيعية", "WORKSHOP"),
    ("203", "نشاط تأجير الورشة للغير وللجمعيات الشريكة", "WORKSHOP"),
    ("300", "المصروفات الإدارية والعمومية للمركز الرئيسي", "ADMIN"),
]

USERS = [
    ("admin", "admin", "مدير النظام (كامل الصلاحيات)", "admin"),
    ("accountant", "accountant", "محاسب الجمعية المالي", "accountant"),
    ("storekeeper", "storekeeper", "أمين المخزن", "storekeeper"),
    ("supervisor", "supervisor", "مشرف الوحدة الإنتاجية", "production_supervisor"),
    ("executive", "executive", "المدير التنفيذي", "executive"),
]

ITEMS = [
    ("RAW-001", "جلود طبيعية خام", "RAW_MATERIAL", "متر", 0.0, 150.0, 20.0),
    ("RAW-002", "أحجار كريمة فاخرة", "RAW_MATERIAL", "قطعة", 0.0, 250.0, 10.0),
    ("RAW-003", "معادن وإكسسوارات الحلي", "RAW_MATERIAL", "كجم", 0.0, 80.0, 15.0),
    ("WIP-001", "إنتاج تحت التشغيل (حلي)", "WIP", "قطعة", 0.0, 120.0, 5.0),
    ("FIN-001", "حلي فنية جاهزة", "FINISHED_GOODS", "قطعة", 0.0, 400.0, 8.0),
    ("FIN-002", "حقائب جلدية جاهزة", "FINISHED_GOODS", "قطعة", 0.0, 600.0, 8.0),
]


def ensure_users(db):
    """إنشاء المستخدمين الناقصين (idempotent) - يضمن وجود admin دائماً"""
    for username, pwd, full_name, role in USERS:
        if not db.query(User).filter(User.username == username).first():
            db.add(User(username=username, full_name=full_name,
                        password_hash=hash_password(pwd), role=role))
    db.commit()


def seed_if_empty():
    db = SessionLocal()
    try:
        # إنشاء المستخدمين الناقصين دائماً (حتى لو كانت القاعدة مهيأة مسبقاً)
        ensure_users(db)

        if db.query(Account).count() > 0:
            return

        # دليل الحسابات
        for code, name, acc_type, level in COA:
            db.add(Account(account_code=code, account_name=name, account_type=acc_type,
                           account_level=level, is_selectable=(level == 5)))
        # مراكز التكلفة
        for code, name, ctype in COST_CENTERS:
            db.add(CostCenter(center_code=code, center_name=name, center_type=ctype))
        # الأصناف المخزنية
        for code, name, cat, unit, qty, cost, reorder in ITEMS:
            db.add(InventoryItem(item_code=code, item_name=name, category=cat,
                                 unit=unit, quantity=qty, unit_cost=cost, reorder_level=reorder))
        db.commit()

        # بيانات تجريبية: تمويل منحة خارجية وقيد تشغيلي
        AccountingService.post_entry(db, date(2026, 1, 15),
            "إثبات استلام تمويل المنحة الخارجية للمشروع أ نقداً بالبنك الأهلي", [
                {"account_code": "111202", "debit": 15000.0, "credit": 0.0,
                 "cost_center_code": "101", "notes": "تمويل الدفعة الأولى المعتمدة"},
                {"account_code": "411101", "debit": 0.0, "credit": 15000.0,
                 "cost_center_code": "101", "notes": "إثبات إيراد المنحة عند الاستلام"},
            ])
        AccountingService.post_entry(db, date(2026, 1, 20),
            "صرف أجر مدرب ومستشار خارجي للمشروع التنموي أ", [
                {"account_code": "511101", "debit": 4800.0, "credit": 0.0,
                 "cost_center_code": "101", "notes": "دورة تمكين الحرف اليدوية"},
                {"account_code": "111202", "debit": 0.0, "credit": 4800.0,
                 "cost_center_code": "101", "notes": "شيك مسحوب للمدرب"},
            ])
        AccountingService.execute_joint_cost_allocation(db, 500.0)
    finally:
        db.close()