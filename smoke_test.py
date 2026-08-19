# -*- coding: utf-8 -*-
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Force a clean local SQLite for the test
os.environ["DATABASE_URL"] = "sqlite:///./test_ngo.db"

from fastapi.testclient import TestClient

# Remove stale test db first
if os.path.exists("test_ngo.db"):
    os.remove("test_ngo.db")

from app.main import app

results = []

# Use context manager so startup event (init_db + seed) fires
client = TestClient(app)
with TestClient(app) as c:
    client = c


def check(name, cond, extra=""):
    results.append((name, cond, extra))
    print(("PASS" if cond else "FAIL"), "-", name, ("| " + str(extra)) if extra else "")


# --- Login / RBAC -----------------------------------------------------------
r = client.get("/login")
check("login page serves 200", r.status_code == 200)

r = client.post("/login", data={"username": "accountant", "password": "wrong"})
check("bad password rejected", r.status_code == 401)

r = client.post("/login", data={"username": "accountant", "password": "accountant"}, follow_redirects=False)
check("accountant login redirects", r.status_code == 303, r.headers.get("location"))

r = client.get("/")
check("dashboard serves 200 for accountant", r.status_code == 200)
check("dashboard shows ج.م", "ج.م" in r.text)

# Storekeeper cannot access journal
client.post("/login", data={"username": "storekeeper", "password": "storekeeper"}, follow_redirects=False)
r = client.get("/journal", follow_redirects=False)
check("storekeeper blocked from journal (RBAC)", r.status_code == 303, r.headers.get("location"))
r = client.get("/forbidden")
check("forbidden page renders", r.status_code == 200)

# Accountant can access journal
client.post("/login", data={"username": "accountant", "password": "accountant"}, follow_redirects=False)
r = client.get("/journal")
check("accountant journal page 200", r.status_code == 200)
check("journal lists level-5 accounts", "خزينة المؤسسة الرئيسية العامة" in r.text)

# --- Journal entry posting --------------------------------------------------
# Balanced entry on level-5 accounts
r = client.post("/journal", data={
    "entry_date": "2026-02-01",
    "description": "قيد اختبار متوازن - شراء خامات نقدا",
    "account_codes": ["112101", "111101"],
    "cost_centers": ["201", ""],
    "debits": ["1000", "0"],
    "credits": ["0", "1000"],
    "notes_list": ["خامات للورشة", "سداد نقدي"],
}, follow_redirects=True)
check("balanced journal entry accepted", "تم ترحيل القيد رقم" in r.text)

# Unbalanced entry must be rejected
r = client.post("/journal", data={
    "entry_date": "2026-02-02",
    "description": "قيد غير متوازن يجب رفضه",
    "account_codes": ["111101", "531103"],
    "cost_centers": ["", "300"],
    "debits": ["500", "0"],
    "credits": ["0", "100"],
    "notes_list": ["", ""],
})
check("unbalanced entry rejected", "خطأ توازن" in r.text)

# Level-1 account (not selectable) must be rejected by governance rule 1
r = client.post("/journal", data={
    "entry_date": "2026-02-03",
    "description": "قيد على مستوى 1 يجب رفضه",
    "account_codes": ["1", "111101"],
    "cost_centers": ["", ""],
    "debits": ["200", "0"],
    "credits": ["0", "200"],
    "notes_list": ["", ""],
})
check("governance rule 1 (level 5 only) enforced", "قاعدة حوكمة رقم 1" in r.text)

# --- Joint cost allocation --------------------------------------------------
r = client.post("/allocation", data={"amount": "1000"}, follow_redirects=True)
check("allocation executed", "تم ترحيل القيد رقم" in r.text)
check("allocation split shown (workshop)", "خط إنتاج الحلي والمشغولات" in r.text)

# --- Inventory --------------------------------------------------------------
r = client.get("/inventory")
check("inventory page 200 for accountant (view only)", r.status_code == 200)

# Storekeeper can edit inventory
client.post("/login", data={"username": "storekeeper", "password": "storekeeper"}, follow_redirects=False)
r = client.get("/inventory")
check("storekeeper inventory page 200", r.status_code == 200)
check("storekeeper sees receipt/issue form", "إذن استلام / صرف" in r.text)

r = client.post("/inventory/transaction", data={
    "trans_type": "RECEIPT", "item_id": "1", "quantity": "50", "reference_work_order": "WO-TEST-001",
}, follow_redirects=True)
check("storekeeper receipt recorded", "تم تسجيل الحركة المخزنية بنجاح" in r.text)

# Over-issue must be rejected
r = client.post("/inventory/transaction", data={
    "trans_type": "ISSUE", "item_id": "1", "quantity": "999999", "reference_work_order": "WO-TEST-002",
}, follow_redirects=True)
check("over-issue rejected", "رصيد غير كافٍ" in r.text)

# Accountant cannot record inventory movements
client.post("/login", data={"username": "accountant", "password": "accountant"}, follow_redirects=False)
r = client.post("/inventory/transaction", data={
    "trans_type": "RECEIPT", "item_id": "1", "quantity": "5", "reference_work_order": "WO-TEST-003",
}, follow_redirects=False)
check("accountant blocked from inventory edit (RBAC)", r.status_code == 303)

# --- Material issue request (production supervisor) ------------------------
# Supervisor cannot record inventory movements directly
client.post("/login", data={"username": "supervisor", "password": "supervisor"}, follow_redirects=False)
r = client.post("/inventory/transaction", data={
    "trans_type": "ISSUE", "item_id": "1", "quantity": "10", "reference_work_order": "WO-TEST-004",
}, follow_redirects=False)
check("supervisor blocked from direct inventory edit (RBAC)", r.status_code == 303)

# Supervisor can submit a material request
r = client.get("/inventory")
check("supervisor sees request form", "طلب صرف خامات" in r.text)

r = client.post("/inventory/request", data={
    "item_id": "1", "quantity": "10", "reason": "أمر تشغيل WO-TEST-004",
}, follow_redirects=True)
check("supervisor material request submitted", "بانتظار الاعتماد" in r.text)

# Request does not change balances yet
import sqlite3
conn = sqlite3.connect("test_ngo.db")
qty_before = conn.execute("SELECT quantity FROM inventory_items WHERE id=1").fetchone()[0]
conn.close()
check("material request does not touch balances", abs(qty_before - 50.0) < 1e-9, qty_before)

# Storekeeper approves the request -> balance decreases via ISSUE
client.post("/login", data={"username": "storekeeper", "password": "storekeeper"}, follow_redirects=False)
req_id = None
conn = sqlite3.connect("test_ngo.db")
row = conn.execute("SELECT id, status FROM material_requests ORDER BY id DESC LIMIT 1").fetchone()
conn.close()
if row:
    req_id, st = row
    check("material request stored as PENDING", st == "PENDING", st)

r = client.post("/inventory/request/decide", data={"request_id": str(req_id), "approve": "yes"}, follow_redirects=True)
check("storekeeper approves material request", "تم اعتماد الطلب" in r.text)

conn = sqlite3.connect("test_ngo.db")
qty_after = conn.execute("SELECT quantity FROM inventory_items WHERE id=1").fetchone()[0]
conn.close()
check("approval issues stock (50 -> 40)", abs(qty_after - 40.0) < 1e-9, qty_after)

# Reject path (submit as supervisor, reject as storekeeper)
client.post("/login", data={"username": "supervisor", "password": "supervisor"}, follow_redirects=False)
r = client.post("/inventory/request", data={
    "item_id": "1", "quantity": "3", "reason": "أمر تشغيل WO-TEST-005",
}, follow_redirects=True)
conn = sqlite3.connect("test_ngo.db")
req2 = conn.execute("SELECT id FROM material_requests ORDER BY id DESC LIMIT 1").fetchone()[0]
conn.close()
client.post("/login", data={"username": "storekeeper", "password": "storekeeper"}, follow_redirects=False)
r = client.post("/inventory/request/decide", data={"request_id": str(req2), "approve": "no"}, follow_redirects=True)
check("storekeeper rejects material request", "تم رفض الطلب" in r.text)

# Donor reports
client.post("/login", data={"username": "executive", "password": "executive"}, follow_redirects=False)
r = client.get("/reports")
check("executive reports page 200", r.status_code == 200)

r = client.post("/reports", data={
    "center_code": "101",
    "acc_codes": ["511101", "511102"],
    "budgets": ["5000", "3000"],
}, follow_redirects=True)
check("donor report generated", "الإجمالي" in r.text)
check("donor report shows variance", "4,800.00" in r.text or "4800.00" in r.text)

# Executive blocked from journal
r = client.get("/journal", follow_redirects=False)
check("executive blocked from journal (RBAC)", r.status_code == 303)

# --- Governance: annual budget approval ------------------------------------
# Accountant proposes a budget line
client.post("/login", data={"username": "accountant", "password": "accountant"}, follow_redirects=False)
r = client.get("/budget")
check("accountant budget page 200", r.status_code == 200)
r = client.post("/budget", data={
    "fiscal_year": "2026",
    "account_code": "511101",
    "proposed_amount": "6000",
}, follow_redirects=True)
check("accountant proposes budget line", "تم إدراج البند بالموازنة السنوية" in r.text)

# Accountant cannot decide a budget (approve_budget is executive-only)
r = client.post("/budget/decide", data={"proposal_id": "1", "approve": "yes"}, follow_redirects=False)
check("accountant blocked from budget decision (RBAC)", r.status_code == 303)

# Storekeeper blocked entirely from budget
client.post("/login", data={"username": "storekeeper", "password": "storekeeper"}, follow_redirects=False)
r = client.get("/budget", follow_redirects=False)
check("storekeeper blocked from budget (RBAC)", r.status_code == 303)

# Executive approves the proposal
client.post("/login", data={"username": "executive", "password": "executive"}, follow_redirects=False)
r = client.get("/budget")
check("executive budget page 200", r.status_code == 200)
r = client.post("/budget/decide", data={"proposal_id": "1", "approve": "yes"}, follow_redirects=True)
check("executive approves budget line", "تم اعتماد بند الموازنة" in r.text)

# --- Governance: rental contract review & approval -------------------------
# Accountant registers a rental contract
client.post("/login", data={"username": "accountant", "password": "accountant"}, follow_redirects=False)
r = client.get("/rentals")
check("accountant rentals page 200", r.status_code == 200)
r = client.post("/rentals", data={
    "contract_no": "RC-2026-001",
    "tenant_name": "جمعية النور الشريكة",
    "description": "تأجير الورشة للتدريب",
    "monthly_rent": "1500",
    "start_date": "2026-03-01",
    "end_date": "2027-02-28",
}, follow_redirects=True)
check("accountant registers rental contract", "تم تسجيل عقد التأجير للمراجعة والاعتماد" in r.text)

# Accountant reviews the contract
r = client.post("/rentals/review", data={"contract_id": "1"}, follow_redirects=True)
check("accountant reviews rental contract", "تمت مراجعة العقد وجاهز للاعتماد" in r.text)

# Accountant cannot finally approve a rental (executive-only)
r = client.post("/rentals/decide", data={"contract_id": "1", "approve": "yes"}, follow_redirects=False)
check("accountant blocked from rental decision (RBAC)", r.status_code == 303)

# Storekeeper blocked from rentals
client.post("/login", data={"username": "storekeeper", "password": "storekeeper"}, follow_redirects=False)
r = client.get("/rentals", follow_redirects=False)
check("storekeeper blocked from rentals (RBAC)", r.status_code == 303)

# Executive approves the reviewed contract
client.post("/login", data={"username": "executive", "password": "executive"}, follow_redirects=False)
r = client.get("/rentals")
check("executive rentals page 200", r.status_code == 200)
r = client.post("/rentals/decide", data={"contract_id": "1", "approve": "yes"}, follow_redirects=True)
check("executive approves rental contract", "تم اعتماد عقد التأجير" in r.text)

# Storekeeper blocked from dashboard
client.post("/login", data={"username": "storekeeper", "password": "storekeeper"}, follow_redirects=False)
r = client.get("/", follow_redirects=False)
check("storekeeper blocked from dashboard (RBAC)", r.status_code == 303)

# --- Governance: workshop handover (supervisor) ------------------------------
# Storekeeper blocked from handover
r = client.get("/handover", follow_redirects=False)
check("storekeeper blocked from handover (RBAC)", r.status_code == 303, r.headers.get("location"))

# Supervisor issues handover permission for the approved contract
client.post("/login", data={"username": "supervisor", "password": "supervisor"}, follow_redirects=False)
r = client.get("/handover")
check("supervisor handover page 200", r.status_code == 200)
check("handover form rendered", "إذن تسليم الورشة المستأجرة" in r.text)
r = client.post("/handover", data={
    "contract_id": "1",
    "equipment_status": "تم فحص الآلات والمعدات وسلامتها وجاهزية الورشة للتسليم",
    "notes": "استلام الورشة وتسليمها للمستأجر بعد الفحص",
}, follow_redirects=True)
check("supervisor issues workshop handover", "تم إصدار إذن التسليم رقم" in r.text)

# Accountant blocked from handover (RBAC)
client.post("/login", data={"username": "accountant", "password": "accountant"}, follow_redirects=False)
r = client.get("/handover", follow_redirects=False)
check("accountant blocked from handover (RBAC)", r.status_code == 303, r.headers.get("location"))

# --- Governance: exceptional disbursement (executive) ------------------------
# Storekeeper receives precious-stone stock so approval can succeed
client.post("/login", data={"username": "storekeeper", "password": "storekeeper"}, follow_redirects=False)
r = client.post("/inventory/transaction", data={
    "trans_type": "RECEIPT", "item_id": "2", "quantity": "20",
    "reference_work_order": "WO-RECEIPT-EXC-001",
}, follow_redirects=True)
check("storekeeper receives precious stones stock", "تم تسجيل الحركة المخزنية بنجاح" in r.text)

# Supervisor submits an EXCEPTIONAL request (precious stones)
client.post("/login", data={"username": "supervisor", "password": "supervisor"}, follow_redirects=False)
r = client.post("/inventory/request", data={
    "item_id": "2",
    "quantity": "5",
    "reason": "طلب صرف استثنائي أحجار كريمة فاخرة - عملية إنتاج خاصة",
    "exceptional": "yes",
}, follow_redirects=True)
check("supervisor exceptional request submitted", "بانتظار الاعتماد" in r.text)
check("exceptional badge shown", "استثنائي" in r.text)
r = client.get("/inventory")
check("supervisor sees exceptional badge on list", "استثنائي" in r.text)

# Storekeeper cannot decide an exceptional request (executive-only)
conn = sqlite3.connect("test_ngo.db")
exc_id = conn.execute("SELECT id FROM material_requests WHERE exceptional=1 ORDER BY id DESC LIMIT 1").fetchone()[0]
conn.close()
client.post("/login", data={"username": "storekeeper", "password": "storekeeper"}, follow_redirects=False)
r = client.post("/inventory/request/decide", data={"request_id": str(exc_id), "approve": "yes"}, follow_redirects=False)
check("storekeeper blocked from exceptional decision (RBAC)", r.status_code == 303, r.headers.get("location"))
r = client.get("/forbidden")
check("forbidden page renders (exceptional)", r.status_code == 200)

# Executive approves the exceptional request
client.post("/login", data={"username": "executive", "password": "executive"}, follow_redirects=False)
r = client.get("/inventory")
check("executive inventory page 200", r.status_code == 200)
check("executive sees exceptional badge on list", "استثنائي" in r.text)
r = client.post("/inventory/request/decide", data={"request_id": str(exc_id), "approve": "yes"}, follow_redirects=True)
check("executive approves exceptional request", "تم اعتماد الطلب" in r.text)

# Executive cannot decide a NORMAL request (storekeeper-only)
client.post("/login", data={"username": "supervisor", "password": "supervisor"}, follow_redirects=False)
r = client.post("/inventory/request", data={
    "item_id": "1",
    "quantity": "3",
    "reason": "طلب صرف عادي لتغذية الورشة",
}, follow_redirects=True)
check("supervisor normal request submitted", "بانتظار الاعتماد" in r.text)
conn = sqlite3.connect("test_ngo.db")
norm_id = conn.execute("SELECT id FROM material_requests WHERE exceptional=0 ORDER BY id DESC LIMIT 1").fetchone()[0]
conn.close()
client.post("/login", data={"username": "executive", "password": "executive"}, follow_redirects=False)
r = client.post("/inventory/request/decide", data={"request_id": str(norm_id), "approve": "yes"}, follow_redirects=False)
check("executive blocked from normal request decision (RBAC)", r.status_code == 303, r.headers.get("location"))

# --- Audit trail ------------------------------------------------------------
client.post("/login", data={"username": "executive", "password": "executive"}, follow_redirects=False)
r = client.get("/")
check("audit trail visible on dashboard", "LOGIN" in r.text or "JOURNAL" in r.text or "INVENTORY" in r.text)

# --- Interactive charts (design plan 3.3) ------------------------------------
check("dashboard has surplus chart", "surplusChart" in r.text)
check("dashboard has donor chart", "donorChart" in r.text)
check("dashboard loads chart.js locally", "/static/chart.umd.min.js" in r.text)
r = client.get("/static/chart.umd.min.js")
check("chart.js static file serves 200", r.status_code == 200)

# --- Financial figures ------------------------------------------------------
# Re-login as executive (storekeeper was last logged in, and is blocked from dashboard)
client.post("/login", data={"username": "executive", "password": "executive"}, follow_redirects=False)
r = client.get("/")
for expected in ["15,000.00", "4,800.00", "750.00"]:
    check(f"dashboard contains {expected}", expected in r.text)

print("\n=== SUMMARY ===")
passed = sum(1 for _, c, _ in results if c)
failed = sum(1 for _, c, _ in results if not c)
print(f"Total: {len(results)} | Passed: {passed} | Failed: {failed}")

# Close all engine connections so the SQLite file can be removed (Windows locks it)
from app.database import engine
engine.dispose()
if os.path.exists("test_ngo.db"):
    os.remove("test_ngo.db")
sys.exit(1 if failed else 0)