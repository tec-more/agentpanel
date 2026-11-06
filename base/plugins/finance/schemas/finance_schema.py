from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field, computed_field
from decimal import Decimal


class AccountCreate(BaseModel):
    code: str = Field(..., description="科目编码")
    name: str = Field(..., description="科目名称")
    account_type: str = Field(..., description="科目类型(asset/liability/equity/income/expense)")
    parent_id: Optional[int] = Field(None, description="上级科目ID")
    description: Optional[str] = Field(None, description="科目描述")
    tax_code: Optional[str] = Field(None, description="税务代码")
    currency_code: Optional[str] = Field("CNY", description="币种代码")
    reconcile: Optional[bool] = Field(False, description="是否需要对账")
    active: Optional[bool] = Field(True, description="是否启用")


class AccountUpdate(BaseModel):
    name: Optional[str] = Field(None, description="科目名称")
    account_type: Optional[str] = Field(None, description="科目类型")
    parent_id: Optional[int] = Field(None, description="上级科目ID")
    description: Optional[str] = Field(None, description="科目描述")
    tax_code: Optional[str] = Field(None, description="税务代码")
    currency_code: Optional[str] = Field(None, description="币种代码")
    reconcile: Optional[bool] = Field(None, description="是否需要对账")
    active: Optional[bool] = Field(None, description="是否启用")


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    account_type: str
    account_type_label: str
    account_type_color: str
    parent_id: Optional[int] = None
    parent: Optional[Dict[str, Any]] = None
    level: int
    is_leaf: bool
    debit_balance: float
    credit_balance: float
    balance: float
    description: Optional[str] = None
    tax_code: Optional[str] = None
    currency_code: str
    reconcile: bool
    active: bool
    children_count: int
    children: List[Dict[str, Any]] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class AccountListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    data: List[AccountOut]


class JournalLineCreate(BaseModel):
    sequence: int = Field(1, description="行号")
    account_id: int = Field(..., description="会计科目ID")
    description: Optional[str] = Field(None, description="摘要")
    debit: Decimal = Field(0, description="借方金额")
    credit: Decimal = Field(0, description="贷方金额")
    tax_amount: Decimal = Field(0, description="税额")
    tax_code: Optional[str] = Field(None, description="税码")
    currency_code: Optional[str] = Field("CNY", description="币种")
    exchange_rate: Decimal = Field(1, description="汇率")
    original_amount: Decimal = Field(0, description="原币金额")
    partner_id: Optional[int] = Field(None, description="往来单位ID")
    partner_type: Optional[str] = Field(None, description="往来单位类型")
    analytic_account_id: Optional[int] = Field(None, description="分析科目ID")
    remark: Optional[str] = Field(None, description="备注")


class JournalLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    journal_entry_id: int
    sequence: int
    account_id: int
    account_code: Optional[str] = None
    account_name: Optional[str] = None
    account_type: Optional[str] = None
    description: Optional[str] = None
    debit: float
    credit: float
    tax_amount: float
    tax_code: Optional[str] = None
    currency_code: str
    exchange_rate: float
    original_amount: float
    partner_id: Optional[int] = None
    partner_type: Optional[str] = None
    analytic_account_id: Optional[int] = None
    remark: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class JournalEntryCreate(BaseModel):
    journal_date: Optional[str] = Field(None, description="凭证日期")
    journal_type: Optional[str] = Field("general", description="凭证类型")
    period: Optional[str] = Field(None, description="会计期间")
    reference: Optional[str] = Field(None, description="关联单据号")
    description: Optional[str] = Field(None, description="摘要")
    lines: List[JournalLineCreate] = Field(..., description="凭证行")
    created_by: Optional[str] = Field(None, description="制单人")
    remark: Optional[str] = Field(None, description="备注")


class JournalEntryUpdate(BaseModel):
    journal_date: Optional[str] = Field(None, description="凭证日期")
    journal_type: Optional[str] = Field(None, description="凭证类型")
    period: Optional[str] = Field(None, description="会计期间")
    reference: Optional[str] = Field(None, description="关联单据号")
    description: Optional[str] = Field(None, description="摘要")
    remark: Optional[str] = Field(None, description="备注")


class JournalEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    journal_no: str
    journal_date: Optional[str] = None
    journal_type: str
    journal_type_label: str
    status: str
    status_label: str
    status_color: str
    period: str
    reference: Optional[str] = None
    description: Optional[str] = None
    total_debit: float
    total_credit: float
    is_balanced: bool
    created_by: Optional[str] = None
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[str] = None
    posted_by: Optional[str] = None
    posted_at: Optional[str] = None
    cancelled_by: Optional[str] = None
    cancelled_at: Optional[str] = None
    remark: Optional[str] = None
    lines: List[JournalLineOut] = []
    line_count: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class JournalEntryListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    data: List[JournalEntryOut]


class DailyJournalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    journal_date: Optional[str] = None
    period: str
    account_id: int
    account_code: Optional[str] = None
    account_name: Optional[str] = None
    description: Optional[str] = None
    reference: Optional[str] = None
    debit: float
    credit: float
    balance: float
    balance_type: str
    journal_entry_id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DailyJournalListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    data: List[DailyJournalOut]


class GeneralLedgerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    period: str
    year: int
    month: int
    account_id: int
    account_code: Optional[str] = None
    account_name: Optional[str] = None
    account_type: Optional[str] = None
    beginning_debit: float
    beginning_credit: float
    beginning_balance: float
    beginning_balance_type: str
    debit_amount: float
    credit_amount: float
    ending_debit: float
    ending_credit: float
    ending_balance: float
    ending_balance_type: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class GeneralLedgerListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    data: List[GeneralLedgerOut]


class TrialBalanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    period: str
    year: int
    month: int
    account_id: int
    account_code: Optional[str] = None
    account_name: Optional[str] = None
    account_type: Optional[str] = None
    account_type_label: Optional[str] = None
    beginning_debit: float
    beginning_credit: float
    beginning_balance: float
    beginning_balance_type: str
    debit_amount: float
    credit_amount: float
    ending_debit: float
    ending_credit: float
    ending_balance: float
    ending_balance_type: str
    is_leaf: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TrialBalanceListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    data: List[TrialBalanceOut]


class ProfitLossReportOut(BaseModel):
    period: str
    year: int
    month: int
    revenue: float = Field(0, description="营业收入")
    cost_of_sales: float = Field(0, description="营业成本")
    gross_profit: float = Field(0, description="毛利润")
    operating_expense: float = Field(0, description="营业费用")
    operating_profit: float = Field(0, description="营业利润")
    non_operating_income: float = Field(0, description="营业外收入")
    non_operating_expense: float = Field(0, description="营业外支出")
    total_profit: float = Field(0, description="利润总额")
    income_tax: float = Field(0, description="所得税")
    net_profit: float = Field(0, description="净利润")
    report_date: Optional[str] = None


class BalanceSheetReportOut(BaseModel):
    period: str
    year: int
    month: int
    assets: Dict[str, Any] = Field(default_factory=dict, description="资产")
    liabilities: Dict[str, Any] = Field(default_factory=dict, description="负债")
    equity: Dict[str, Any] = Field(default_factory=dict, description="权益")
    total_assets: float = Field(0, description="总资产")
    total_liabilities: float = Field(0, description="总负债")
    total_equity: float = Field(0, description="总权益")
    report_date: Optional[str] = None


class CashFlowItem(BaseModel):
    name: str = Field(..., description="项目名称")
    type: str = Field(..., description="流入/流出")
    amount: float = Field(0, description="金额")


class CashFlowSection(BaseModel):
    cash_inflow: float = Field(0, description="现金流入")
    cash_outflow: float = Field(0, description="现金流出")
    net_cash_flow: float = Field(0, description="净现金流")
    items: List[CashFlowItem] = Field(default_factory=list, description="明细项目")


class CashFlowReportOut(BaseModel):
    period: str
    year: int
    month: int
    cash_beginning_balance: float = Field(0, description="期初现金余额")
    cash_ending_balance: float = Field(0, description="期末现金余额")
    net_cash_flow: float = Field(0, description="现金净流量")
    operating: CashFlowSection = Field(default_factory=CashFlowSection, description="经营活动")
    investing: CashFlowSection = Field(default_factory=CashFlowSection, description="投资活动")
    financing: CashFlowSection = Field(default_factory=CashFlowSection, description="筹资活动")
    report_date: Optional[str] = None