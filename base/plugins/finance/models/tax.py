from datetime import datetime
from enum import Enum
from tortoise import fields, models
from base.common.model import BaseModel, TimestampMixin


class InvoiceType(str, Enum):
    VAT_SPECIAL = "vat_special"
    VAT_NORMAL = "vat_normal"
    INVOICE = "invoice"


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    VERIFIED = "verified"
    CANCELLED = "cancelled"


class TaxInvoice(BaseModel, TimestampMixin):
    invoice_no = fields.CharField(max_length=64, unique=True, description="发票号码")
    invoice_code = fields.CharField(max_length=64, description="发票代码")
    invoice_type = fields.CharEnumField(InvoiceType, max_length=32, description="发票类型")
    amount = fields.DecimalField(max_digits=18, decimal_places=2, description="发票金额")
    tax_amount = fields.DecimalField(max_digits=18, decimal_places=2, description="税额")
    total_amount = fields.DecimalField(max_digits=18, decimal_places=2, description="价税合计")
    tax_rate = fields.DecimalField(max_digits=6, decimal_places=2, description="税率")
    invoice_date = fields.DateField(description="开票日期")
    status = fields.CharEnumField(InvoiceStatus, max_length=20, default=InvoiceStatus.DRAFT, description="状态")
    customer = fields.ForeignKeyField("models.Customer", related_name="invoices", on_delete=fields.SET_NULL, null=True, description="客户")
    customer_name = fields.CharField(max_length=128, description="客户名称")
    customer_tax_id = fields.CharField(max_length=64, null=True, description="客户税号")
    supplier = fields.ForeignKeyField("models.Supplier", related_name="invoices", on_delete=fields.SET_NULL, null=True, description="供应商")
    supplier_name = fields.CharField(max_length=128, null=True, description="供应商名称")
    supplier_tax_id = fields.CharField(max_length=64, null=True, description="供应商税号")
    is_input = fields.BooleanField(default=False, description="是否进项发票")
    related_order_id = fields.IntField(null=True, description="关联订单ID")
    description = fields.TextField(null=True, description="备注")
    created_by = fields.CharField(max_length=64, description="操作人")
    
    class Meta:
        table = "finance_tax_invoices"


class TaxDeclaration(BaseModel, TimestampMixin):
    declaration_no = fields.CharField(max_length=64, unique=True, description="申报编号")
    period = fields.CharField(max_length=10, description="申报期间")
    declaration_date = fields.DateField(default=datetime.now, description="申报日期")
    status = fields.CharField(max_length=20, default="draft", description="状态")
    total_output_tax = fields.DecimalField(max_digits=18, decimal_places=2, description="销项税额")
    total_input_tax = fields.DecimalField(max_digits=18, decimal_places=2, description="进项税额")
    payable_tax = fields.DecimalField(max_digits=18, decimal_places=2, description="应纳税额")
    paid_tax = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="已缴税额")
    description = fields.TextField(null=True, description="备注")
    created_by = fields.CharField(max_length=64, description="申报人")
    
    class Meta:
        table = "finance_tax_declarations"


class TaxSummary(BaseModel, TimestampMixin):
    period = fields.CharField(max_length=10, unique=True, description="会计期间")
    output_tax = fields.DecimalField(max_digits=18, decimal_places=2, description="销项税额")
    input_tax = fields.DecimalField(max_digits=18, decimal_places=2, description="进项税额")
    payable_tax = fields.DecimalField(max_digits=18, decimal_places=2, description="应纳税额")
    paid_tax = fields.DecimalField(max_digits=18, decimal_places=2, description="已缴税额")
    balance_tax = fields.DecimalField(max_digits=18, decimal_places=2, description="期末余额")
    
    class Meta:
        table = "finance_tax_summaries"