# -*- coding: utf-8 -*-
"""اختبارات وحدة: مصفوفة الصلاحيات (RBAC)"""
from app.rbac import has_permission, role_label, PERMISSIONS


def test_roles_defined():
    assert set(PERMISSIONS) == {"admin", "accountant", "storekeeper",
                                "production_supervisor", "executive"}


def test_admin_all_permissions():
    assert has_permission("admin", "journal_entry") is True
    assert has_permission("admin", "reports") is True
    assert has_permission("admin", "dashboard") is True
    assert has_permission("admin", "allocation") is True
    assert has_permission("admin", "inventory_view") is True
    assert has_permission("admin", "inventory_edit") is True
    assert has_permission("admin", "inventory_request") is True
    assert has_permission("admin", "workshop_handover") is True
    assert has_permission("admin", "rental_review") is True
    assert has_permission("admin", "approve_rental") is True
    assert has_permission("admin", "budget_propose") is True
    assert has_permission("admin", "approve_budget") is True
    assert has_permission("admin", "approve_exceptional") is True


def test_accountant_permissions():
    assert has_permission("accountant", "journal_entry") is True
    assert has_permission("accountant", "reports") is True
    assert has_permission("accountant", "dashboard") is True
    assert has_permission("accountant", "allocation") is True
    assert has_permission("accountant", "budget_propose") is True
    assert has_permission("accountant", "rental_review") is True
    assert has_permission("accountant", "inventory_view") is True
    # المحاسب يرى الأرصدة لكن لا يعدلها
    assert has_permission("accountant", "inventory_edit") is False
    assert has_permission("accountant", "approve_exceptional") is False
    assert has_permission("accountant", "workshop_handover") is False


def test_storekeeper_permissions():
    # حجب كامل للشاشات المالية
    assert has_permission("storekeeper", "journal_entry") is False
    assert has_permission("storekeeper", "reports") is False
    assert has_permission("storekeeper", "dashboard") is False
    assert has_permission("storekeeper", "allocation") is False
    assert has_permission("storekeeper", "budget_propose") is False
    assert has_permission("storekeeper", "rental_review") is False
    # صلاحية حصرية للمخازن
    assert has_permission("storekeeper", "inventory_edit") is True
    assert has_permission("storekeeper", "inventory_view") is True
    assert has_permission("storekeeper", "inventory_request") is False


def test_production_supervisor_permissions():
    assert has_permission("production_supervisor", "inventory_request") is True
    assert has_permission("production_supervisor", "workshop_handover") is True
    assert has_permission("production_supervisor", "inventory_view") is True
    # بلا تعديل أرصدة ولا شاشات مالية
    assert has_permission("production_supervisor", "inventory_edit") is False
    assert has_permission("production_supervisor", "journal_entry") is False
    assert has_permission("production_supervisor", "reports") is False
    assert has_permission("production_supervisor", "dashboard") is False
    assert has_permission("production_supervisor", "approve_exceptional") is False


def test_executive_permissions():
    assert has_permission("executive", "dashboard") is True
    assert has_permission("executive", "reports") is True
    assert has_permission("executive", "approve_exceptional") is True
    assert has_permission("executive", "approve_rental") is True
    assert has_permission("executive", "approve_budget") is True
    assert has_permission("executive", "allocation") is True
    assert has_permission("executive", "rental_review") is True
    # المدير التنفيذي لا يقيّد ولا يعدّل المخزون مباشرة
    assert has_permission("executive", "journal_entry") is False
    assert has_permission("executive", "inventory_edit") is False
    assert has_permission("executive", "budget_propose") is False


def test_unknown_role_has_no_permissions():
    assert has_permission("hacker", "journal_entry") is False
    assert has_permission("", "dashboard") is False
    assert has_permission(None, "inventory_edit") is False


def test_unknown_permission_returns_false():
    assert has_permission("accountant", "delete_system") is False


def test_role_labels_arabic():
    assert role_label("admin") == "مدير النظام (كامل الصلاحيات)"
    assert role_label("accountant") == "محاسب الجمعية المالي"
    assert role_label("storekeeper") == "أمين المخزن"
    assert role_label("production_supervisor") == "مشرف الوحدة الإنتاجية"
    assert role_label("executive") == "المدير التنفيذي / الإدارة"
    assert role_label("unknown_role") == "unknown_role"