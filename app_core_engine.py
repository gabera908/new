import os
import sys
from datetime import datetime

# Technical architecture components for the NGO ERP Platform

class Config:
    """System configurations and localization settings"""
    APP_NAME = "نظام الحوكمة المالي والمخزني المتكامل للمؤسسات الأهلية والوحدات الإنتاجية"
    VERSION = "2026.1.0"
    DEFAULT_CURRENCY = "ج.م"

class Account:
    def __init__(self, code, name, account_type, level):
        self.code = code
        self.name = name
        self.account_type = account_type  # Assets, Liabilities, Net Assets, Revenues, Expenses
        self.level = level
        self.balance = 0.0

class ChartOfAccounts:
    def __init__(self):
        self.accounts = {}
        self._initialize_coa()
        
    def _initialize_coa(self):
        # Professional standard COA for complex hybrid NGO
        raw_coa = [
            # 1. Assets
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
            
            # 2. Liabilities
            ("2", "الالتزامات", "Liabilities", 1),
            ("21", "الالتزامات المتداولة", "Liabilities", 2),
            ("211", "مخصصات وأرصدة دائنة أخرى", "Liabilities", 3),
            ("211101", "إيرادات منح مؤجلة (مشاريع ممولة لم تنفذ)", "Liabilities", 5),
            ("211103", "تأمينات مستردة للغير (تأمينات مستأجري الورشة)", "Liabilities", 5),
            
            # 3. Net Assets (Alternative to Owner Equity)
            ("3", "صافي الأصول والاحتياطيات", "NetAssets", 1),
            ("31", "أموال المؤسسة الحرة والمقيدة", "NetAssets", 2),
            ("311101", "صافي أصول غير مقيدة (الفائض المتراكم)", "NetAssets", 5),
            ("311102", "صافي أصول مقيدة (أموال مخصصة لغرض محدد)", "NetAssets", 5),
            
            # 4. Revenues
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
            
            # 5. Expenses
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
        for code, name, acc_type, level in raw_coa:
            self.accounts[code] = Account(code, name, acc_type, level)

class CostCenter:
    def __init__(self, code, name):
        self.code = code
        self.name = name
        self.balance = 0.0

class JournalEntryLine:
    def __init__(self, account_code, debit, credit, cost_center_code=None, notes=""):
        self.account_code = account_code
        self.debit = float(debit)
        self.credit = float(credit)
        self.cost_center_code = cost_center_code
        self.notes = notes

class JournalEntry:
    def __init__(self, entry_id, date, description):
        self.entry_id = entry_id
        self.date = date
        self.description = description
        self.lines = []
        
    def add_line(self, line):
        self.lines.append(line)
        
    def is_balanced(self):
        total_debit = sum(l.debit for l in self.lines)
        total_credit = sum(l.credit for l in self.lines)
        return abs(total_debit - total_credit) < 0.001

class FinancialEngine:
    def __init__(self):
        self.coa = ChartOfAccounts()
        self.cost_centers = {
            "101": CostCenter("101", "مشروع أ - الممول من الجهة الخارجية X"),
            "102": CostCenter("102", "مشروع ب - الممول من الجهة الخارجية Y"),
            "103": CostCenter("103", "برنامج التدريبات والورش التعليمية بالقاعات"),
            "201": CostCenter("201", "خط إنتاج الحلي والمشغولات"),
            "202": CostCenter("202", "خط إنتاج المنتجات الجلدية الطبيعية"),
            "203": CostCenter("203", "نشاط تأجير الورشة للغير وللجمعيات الشريكة"),
            "300": CostCenter("300", "المصروفات الإدارية والعمومية للمركز الرئيسي")
        }
        self.journal_entries = []
        self.next_entry_id = 1
        
    def post_entry(self, date, description, lines_data):
        entry = JournalEntry(self.next_entry_id, date, description)
        for ld in lines_data:
            line = JournalEntryLine(
                account_code=ld['account_code'],
                debit=ld.get('debit', 0.0),
                credit=ld.get('credit', 0.0),
                cost_center_code=ld.get('cost_center_code', None),
                notes=ld.get('notes', "")
            )
            # Validation Rule: Enforcement of Leaf Node (Level 5 only for transactional postings)
            acc = self.coa.accounts.get(line.account_code)
            if not acc:
                return False, f"خطأ حوكمة: كود الحساب {line.account_code} غير موجود بالنظام."
            if acc.level != 5:
                return False, f"قاعدة حوكمة رقم 1: الحساب {acc.name} ليس في المستوى 5. يمنع النظام القيد على حسابات المراقبة أو الحسابات الأب."
            entry.add_line(line)
            
        if not entry.is_balanced():
            return False, "خطأ توازن: إجمالي الحركات المدينة لا يساوي إجمالي الحركات الدائنة بقيد اليومية."
            
        # Execute ledger updates and clear calculations
        for line in entry.lines:
            acc = self.coa.accounts[line.account_code]
            # Mathematical balances update rules based on double-entry rules
            if acc.account_type in ["Assets", "Expenses"]:
                acc.balance += (line.debit - line.credit)
            else:
                acc.balance += (line.credit - line.debit)
                
            if line.cost_center_code and line.cost_center_code in self.cost_centers:
                cc = self.cost_centers[line.cost_center_code]
                if acc.account_type in ["Assets", "Expenses"]:
                    cc.balance += (line.debit - line.credit)
                else:
                    cc.balance += (line.credit - line.debit)
                    
        self.journal_entries.append(entry)
        self.next_entry_id += 1
        self._rollup_balances()
        return True, f"تم ترحيل القيد رقم {entry.entry_id} بنجاح وتحديث الحسابات ومراكز التكلفة المرتبطة."

    def _rollup_balances(self):
        """Roll-up (T-Account upward consolidation engine from Level 5 to Level 1)"""
        # Reset parent nodes
        for code, acc in self.coa.accounts.items():
            if acc.level < 5:
                acc.balance = 0.0
        # Re-accumulate based on dynamic key prefix matching
        for leaf_code, leaf_acc in self.coa.accounts.items():
            if leaf_acc.level == 5:
                for parent_code, parent_acc in self.coa.accounts.items():
                    if parent_acc.level < 5 and leaf_code.startswith(parent_code):
                        parent_acc.balance += leaf_acc.balance

    def execute_joint_cost_allocation(self, total_invoice_amount):
        """Equation-Driven Joint Cost Allocation Rule (Electricity & Water Distribution Formula)"""
        # Allocation ratios: الورشة (50%), التدريب بالقاعات (30%), الإدارة العامة (20%)
        workshop_share = total_invoice_amount * 0.50
        training_share = total_invoice_amount * 0.30
        admin_share = total_invoice_amount * 0.20
        
        lines = [
            {'account_code': '522102', 'debit': workshop_share, 'credit': 0.0, 'cost_center_code': '201', 'notes': 'توزيع مبرمج تلقائي - نصيب تشغيل الورشة 50%'},
            {'account_code': '511102', 'debit': training_share, 'credit': 0.0, 'cost_center_code': '103', 'notes': 'توزيع مبرمج تلقائي - نصيب قاعات التدريب 30%'},
            {'account_code': '531103', 'debit': admin_share, 'credit': 0.0, 'cost_center_code': '300', 'notes': 'توزيع مبرمج تلقائي - نصيب الإدارة العامة 20%'},
            {'account_code': '111101', 'debit': 0.0, 'credit': total_invoice_amount, 'cost_center_code': None, 'notes': 'السداد الفعلي المشترك من الخزينة الرئيسية'}
        ]
        return self.post_entry(datetime.now().strftime("%Y-%m-%d"), "قيد توزيع مصاريف الطاقة والمياه المشتركة آلياً بحسب معايير المساحة والمعدات", lines)

    def generate_donor_report(self, cost_center_code, budget_dict):
        """Automated Grant & Foreign Donor Report Variance Analysis Output Generator"""
        report = []
        report.append("="*90)
        report.append(f"تقرير المقارنة المالي والتحليل الانحرافي للمانح الخارجي - مركز تكلفة: {cost_center_code}")
        report.append("="*90)
        report.append(f"{'بند المصروف المعتمد':<35} | {'كود الحساب':<10} | {'الموازنة (ج.م)':<12} | {'المنصرف الفعلي (ج.م)':<18} | {'الانحراف المتبقي (ج.م)':<15}")
        report.append("-"*90)
        
        total_budget = 0.0
        total_actual = 0.0
        
        for acc_code, budget_val in budget_dict.items():
            acc = self.coa.accounts.get(acc_code)
            actual_val = 0.0
            # Aggregate line transactions for this specific cost center
            for entry in self.journal_entries:
                for line in entry.lines:
                    if line.account_code == acc_code and line.cost_center_code == cost_center_code:
                        actual_val += (line.debit - line.credit) if acc.account_type == "Expenses" else (line.credit - line.debit)
            
            variance = budget_val - actual_val
            report.append(f"{acc.name:<35} | {acc_code:<10} | {budget_val:<12,.2f} | {actual_val:<18,.2f} | {variance:<15,.2f}")
            total_budget += budget_val
            total_actual += actual_val
            
        total_variance = total_budget - total_actual
        report.append("-"*90)
        report.append(f"{'إجمالي تكاليف ونشاط المشروع الممول':<35} | {'-':<10} | {total_budget:<12,.2f} | {total_actual:<18,.2f} | {total_variance:<15,.2f}")
        report.append("="*90)
        return "\n".join(report)

# Instantiate the full test engine execution environment to demonstrate industrial readiness
engine = FinancialEngine()

# Populate system with safe verification transactions
# 1. Posting initial receipt of external funding from donor X
engine.post_entry("2026-01-15", "إثبات استلام تمويل المنحة الخارجية للمشروع أ نقداً بالبنك الأهلي", [
    {'account_code': '111202', 'debit': 15000.0, 'credit': 0.0, 'cost_center_code': '101', 'notes': 'تمويل الدفعة الأولى المعتمدة'},
    {'account_code': '211101', 'debit': 0.0, 'credit': 15000.0, 'cost_center_code': '101', 'notes': 'التزام إيرادات منح مؤجلة قيد التنفيذ'}
])

# 2. Posting specific operational expenses against the grant to check variance engine
engine.post_entry("2026-01-20", "صرف أجر مدرب ومستشار خارجي للمشروع التنموي أ", [
    {'account_code': '511101', 'debit': 4800.0, 'credit': 0.0, 'cost_center_code': '101', 'notes': 'دورة تمكين الحرف اليدوية'},
    {'account_code': '111202', 'debit': 0.0, 'credit': 4800.0, 'cost_center_code': '101', 'notes': 'شيك مسحوب للمدرب'}
])

# 3. Post a sample joint energy utility cost distribution
engine.execute_joint_cost_allocation(500.0)

# Generate structural output report definitions to verify calculation integrity
donor_budget_framework = {
    '511101': 5000.0,
    '511102': 3000.0,
    '511103': 2000.0
}
donor_output_report = engine.generate_donor_report("101", donor_budget_framework)

# Output summary validation report file
with open("generated/accounting_system_spec.txt", "w", encoding="utf-8") as f:
    f.write("=== مخرجات فحص ومطابقة محرك النظام المحاسبي المتطور للمؤسسات الأهلية ===\n\n")
    f.write(f"حالة حساب الأصول الكلي بعد الترحيل: {engine.coa.accounts['1'].balance} {Config.DEFAULT_CURRENCY}\n")
    f.write(f"حالة حساب المصروفات التراكمي (مستوى 1): {engine.coa.accounts['5'].balance} {Config.DEFAULT_CURRENCY}\n")
    f.write(f"رصيد خزينة الورشة الفرعية بعد التوزيع الآلي للطاقة: {engine.coa.accounts['522102'].balance} {Config.DEFAULT_CURRENCY}\n\n")
    f.write(donor_output_report)

print("Accounting Spec Architecture and dynamic script verification written successfully.")
