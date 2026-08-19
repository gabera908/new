# -*- coding: utf-8 -*-
"""نموذج البيانات (ORM) وفق مخطط قاعدة البيانات في خطة التصميم"""
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, ForeignKey,
    DateTime, Text, Date, Numeric, UniqueConstraint, CheckConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


class Account(Base):
    """دليل الحسابات الشجري ذو المستويات الخمسة"""
    __tablename__ = "chart_of_accounts"

    account_code = Column(String(20), primary_key=True)
    account_name = Column(String(150), nullable=False)
    account_type = Column(String(30), nullable=False)  # Assets, Liabilities, NetAssets, Revenues, Expenses
    account_level = Column(Integer, nullable=False)    # 1 .. 5
    is_selectable = Column(Boolean, default=False)     # True فقط للمستوى 5
    parent_code = Column(String(20), ForeignKey("chart_of_accounts.account_code"), nullable=True)
    balance = Column(Float, default=0.0)

    parent = relationship("Account", remote_side=[account_code], backref="children")


class CostCenter(Base):
    """مراكز التكلفة والأبعاد التمويلية"""
    __tablename__ = "cost_centers"

    center_code = Column(String(10), primary_key=True)
    center_name = Column(String(100), nullable=False)
    center_type = Column(String(50), nullable=False)  # NGO_PROJECT, WORKSHOP, ADMIN
    balance = Column(Float, default=0.0)


class JournalEntry(Base):
    """رؤوس القيود اليومية (تاريخية ودائمة)"""
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True)
    entry_date = Column(Date, nullable=False, default=datetime.utcnow)
    description = Column(Text, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    lines = relationship("JournalEntryLine", back_populates="entry",
                         cascade="all, delete-orphan")


class JournalEntryLine(Base):
    """تفاصيل سطور القيود اليومية"""
    __tablename__ = "journal_entry_lines"
    __table_args__ = (CheckConstraint("debit >= 0 AND credit >= 0",
                                      name="check_balanced_line"),)

    id = Column(Integer, primary_key=True)
    entry_id = Column(Integer, ForeignKey("journal_entries.id", ondelete="CASCADE"))
    account_code = Column(String(20), ForeignKey("chart_of_accounts.account_code"))
    cost_center_code = Column(String(10), ForeignKey("cost_centers.center_code"), nullable=True)
    debit = Column(Numeric(15, 2, asdecimal=False), default=0.00)
    credit = Column(Numeric(15, 2, asdecimal=False), default=0.00)
    notes = Column(Text, default="")

    entry = relationship("JournalEntry", back_populates="lines")
    account = relationship("Account")


class User(Base):
    """مستخدمو النظام"""
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("username", name="uq_username"),)

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    password_hash = Column(String(200), nullable=False)
    role = Column(String(30), nullable=False)  # accountant, storekeeper, production_supervisor, executive
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """المسار التفتيشي الأمني - سجل غير قابل للحذف أو التعديل"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=True)
    username = Column(String(50), nullable=True)
    action_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    ip_address = Column(String(50), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)


class InventoryItem(Base):
    """كروت أصناف المخزن (الخامات والإنتاج)"""
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True)
    item_code = Column(String(20), unique=True, nullable=False)
    item_name = Column(String(150), nullable=False)
    category = Column(String(50), nullable=False)  # RAW_MATERIAL, WIP, FINISHED_GOODS
    unit = Column(String(20), default="قطعة")
    quantity = Column(Float, default=0.0)
    unit_cost = Column(Float, default=0.0)
    reorder_level = Column(Float, default=0.0)


class InventoryTransaction(Base):
    """أذونات الاستلام والصرف للمخزن (حركة مخزنية)"""
    __tablename__ = "inventory_transactions"

    id = Column(Integer, primary_key=True)
    doc_number = Column(String(30), nullable=False)
    trans_type = Column(String(20), nullable=False)  # RECEIPT, ISSUE
    item_id = Column(Integer, ForeignKey("inventory_items.id"))
    quantity = Column(Float, nullable=False)
    reference_work_order = Column(String(30), nullable=True)  # أمر الشغل المعتمد
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    item = relationship("InventoryItem")


class MaterialRequest(Base):
    """طلب صرف خامات من مشرف الوحدة الإنتاجية (لا يتحكم في الأرصدة)"""
    __tablename__ = "material_requests"

    id = Column(Integer, primary_key=True)
    request_no = Column(String(30), nullable=False)
    item_id = Column(Integer, ForeignKey("inventory_items.id"))
    quantity = Column(Float, nullable=False)
    reason = Column(Text, default="")                      # سبب الطلب (أمر تشغيل/إنتاج)
    status = Column(String(20), default="PENDING")         # PENDING, APPROVED, REJECTED
    exceptional = Column(Boolean, default=False)            # صرف استثنائي للأحجار الكريمة الفاخرة
    requested_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    requested_at = Column(DateTime, default=datetime.utcnow)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    item = relationship("InventoryItem")


class WorkshopHandover(Base):
    """إذن تسليم الورشة المستأجرة مع إثبات سلامة الآلات (مشرف الوحدة الإنتاجية)"""
    __tablename__ = "workshop_handovers"

    id = Column(Integer, primary_key=True)
    handover_no = Column(String(30), nullable=False)
    contract_id = Column(Integer, ForeignKey("rental_contracts.id"), nullable=True)
    equipment_status = Column(Text, default="")              # إثبات سلامة الآلات والمعدات
    notes = Column(Text, default="")
    issued_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    issued_at = Column(DateTime, default=datetime.utcnow)

    contract = relationship("RentalContract")


class BudgetProposal(Base):
    """بند موازنة سنوية يقترحه المحاسب ويعتمده المدير التنفيذي"""
    __tablename__ = "budget_proposals"

    id = Column(Integer, primary_key=True)
    fiscal_year = Column(String(10), nullable=False)          # مثل 2026
    account_code = Column(String(20), ForeignKey("chart_of_accounts.account_code"))
    proposed_amount = Column(Float, nullable=False)
    status = Column(String(20), default="PENDING")            # PENDING, APPROVED, REJECTED
    proposed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    proposed_at = Column(DateTime, default=datetime.utcnow)
    decided_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    decided_at = Column(DateTime, nullable=True)

    account = relationship("Account")


class RentalContract(Base):
    """عقد تأجير الورشة للغير/للجمعيات: يراجع المحاسب ويعتمد المدير التنفيذي"""
    __tablename__ = "rental_contracts"

    id = Column(Integer, primary_key=True)
    contract_no = Column(String(30), nullable=False)
    tenant_name = Column(String(150), nullable=False)
    description = Column(Text, default="")                    # موضوع التعاقد وصفة المقر
    monthly_rent = Column(Float, nullable=False)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    status = Column(String(20), default="PENDING")            # PENDING, REVIEWED, APPROVED, REJECTED
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    decided_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    decided_at = Column(DateTime, nullable=True)

    creator = relationship("User", foreign_keys=[created_by])