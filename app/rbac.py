# -*- coding: utf-8 -*-
"""مصفوفة الصلاحيات (RBAC) حسب خطة التصميم"""

# دور المستخدم: accountant, storekeeper, production_supervisor, executive, admin
PERMISSIONS = {
    # مدير النظام: جميع الصلاحيات
    "admin": {
        "journal_entry": True,
        "reports": True,
        "inventory_view": True,
        "inventory_edit": True,
        "inventory_request": True,
        "workshop_handover": True,
        "rental_review": True,
        "approve_rental": True,
        "budget_propose": True,
        "approve_budget": True,
        "approve_exceptional": True,
        "dashboard": True,
        "allocation": True,
    },
    # المحاسب المالي: قيود + تقارير + استعراض أرصدة المخازن (بدون تعديل)
    "accountant": {
        "journal_entry": True,
        "reports": True,
        "inventory_view": True,
        "inventory_edit": False,
        "rental_review": True,
        "budget_propose": True,
        "dashboard": True,
        "allocation": True,
    },
    # أمين المخزن: حجب كامل للشاشات المالية + صلاحية حصرية للمخازن
    "storekeeper": {
        "journal_entry": False,
        "reports": False,
        "inventory_view": True,
        "inventory_edit": True,
        "rental_review": False,
        "budget_propose": False,
        "dashboard": False,
        "allocation": False,
    },
    # مشرف الوحدة الإنتاجية: طلب صرف خامات + إذن تسليم الورشة (بلا تعديل أرصدة)
    "production_supervisor": {
        "journal_entry": False,
        "reports": False,
        "inventory_view": True,
        "inventory_edit": False,
        "inventory_request": True,
        "workshop_handover": True,
        "rental_review": False,
        "budget_propose": False,
        "dashboard": False,
        "allocation": False,
    },
    # المدير التنفيذي: لوحة القيادة + اعتماد الموازنات والتأجير + الصرف الاستثنائي
    "executive": {
        "journal_entry": False,
        "reports": True,
        "inventory_view": True,
        "inventory_edit": False,
        "approve_exceptional": True,
        "rental_review": True,
        "budget_propose": False,
        "dashboard": True,
        "allocation": True,
        "approve_rental": True,
        "approve_budget": True,
    },
}


def has_permission(role: str, permission: str) -> bool:
    return role in PERMISSIONS and PERMISSIONS[role].get(permission, False)


def role_label(role: str) -> str:
    labels = {
        "admin": "مدير النظام (كامل الصلاحيات)",
        "accountant": "محاسب الجمعية المالي",
        "storekeeper": "أمين المخزن",
        "production_supervisor": "مشرف الوحدة الإنتاجية",
        "executive": "المدير التنفيذي / الإدارة",
    }
    return labels.get(role, role)