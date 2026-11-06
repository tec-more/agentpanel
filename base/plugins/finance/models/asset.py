from datetime import datetime
from enum import Enum
from tortoise import fields, models
from base.common.model import BaseModel, TimestampMixin


class AssetStatus(str, Enum):
    NEW = "new"
    IN_USE = "in_use"
    IDLE = "idle"
    DISPOSED = "disposed"


class AssetDepreciationMethod(str, Enum):
    STRAIGHT_LINE = "straight_line"
    DOUBLE_DECLINING = "double_declining"
    UNITS_OF_PRODUCTION = "units_of_production"


class Asset(BaseModel, TimestampMixin):
    asset_code = fields.CharField(max_length=64, unique=True, description="资产编码")
    asset_name = fields.CharField(max_length=128, description="资产名称")
    asset_category = fields.CharField(max_length=64, description="资产类别")
    model = fields.CharField(max_length=128, null=True, description="型号")
    brand = fields.CharField(max_length=64, null=True, description="品牌")
    purchase_date = fields.DateField(description="购入日期")
    purchase_cost = fields.DecimalField(max_digits=18, decimal_places=2, description="购入成本")
    salvage_value = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="残值")
    useful_life = fields.IntField(description="使用年限(月)")
    depreciation_method = fields.CharEnumField(AssetDepreciationMethod, max_length=32, default=AssetDepreciationMethod.STRAIGHT_LINE, description="折旧方法")
    monthly_depreciation = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="月折旧额")
    accumulated_depreciation = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="累计折旧")
    net_value = fields.DecimalField(max_digits=18, decimal_places=2, description="净值")
    location = fields.CharField(max_length=128, null=True, description="存放地点")
    department = fields.ForeignKeyField("models.Department", related_name="assets", on_delete=fields.SET_NULL, null=True, description="使用部门")
    responsible_person = fields.ForeignKeyField("models.User", related_name="assets", on_delete=fields.SET_NULL, null=True, description="责任人")
    status = fields.CharEnumField(AssetStatus, max_length=20, default=AssetStatus.IN_USE, description="资产状态")
    account = fields.ForeignKeyField("models.Account", related_name="assets", on_delete=fields.SET_NULL, null=True, description="会计科目")
    description = fields.TextField(null=True, description="备注")
    
    class Meta:
        table = "finance_assets"
    
    def calculate_monthly_depreciation(self):
        if self.depreciation_method == AssetDepreciationMethod.STRAIGHT_LINE:
            depreciable_amount = float(self.purchase_cost) - float(self.salvage_value)
            return round(depreciable_amount / self.useful_life, 2)
        return 0


class AssetChangeType(str, Enum):
    TRANSFER = "transfer"
    APPRAISAL = "appraisal"
    REPAIR = "repair"
    OTHER = "other"


class AssetChange(BaseModel, TimestampMixin):
    asset = fields.ForeignKeyField("models.Asset", related_name="changes", on_delete=fields.CASCADE, description="资产")
    change_type = fields.CharEnumField(AssetChangeType, max_length=32, description="变动类型")
    change_date = fields.DateField(default=datetime.now, description="变动日期")
    old_value = fields.DecimalField(max_digits=18, decimal_places=2, description="变动前金额")
    new_value = fields.DecimalField(max_digits=18, decimal_places=2, description="变动后金额")
    description = fields.TextField(description="变动原因")
    created_by = fields.CharField(max_length=64, description="操作人")
    
    class Meta:
        table = "finance_asset_changes"


class AssetDisposal(BaseModel, TimestampMixin):
    asset = fields.ForeignKeyField("models.Asset", related_name="disposals", on_delete=fields.CASCADE, description="资产")
    disposal_date = fields.DateField(default=datetime.now, description="清理日期")
    disposal_method = fields.CharField(max_length=32, description="清理方式")
    disposal_amount = fields.DecimalField(max_digits=18, decimal_places=2, description="清理收入")
    net_disposal_value = fields.DecimalField(max_digits=18, decimal_places=2, description="净损益")
    description = fields.TextField(description="清理原因")
    created_by = fields.CharField(max_length=64, description="操作人")
    
    class Meta:
        table = "finance_asset_disposals"


class DepreciationRecord(BaseModel, TimestampMixin):
    asset = fields.ForeignKeyField("models.Asset", related_name="depreciation_records", on_delete=fields.CASCADE, description="资产")
    period = fields.CharField(max_length=10, description="会计期间")
    depreciation_amount = fields.DecimalField(max_digits=18, decimal_places=2, description="折旧金额")
    accumulated_depreciation = fields.DecimalField(max_digits=18, decimal_places=2, description="累计折旧")
    journal_entry = fields.ForeignKeyField("models.JournalEntry", related_name="depreciation_records", on_delete=fields.SET_NULL, null=True, description="关联凭证")
    created_by = fields.CharField(max_length=64, description="操作人")
    
    class Meta:
        table = "finance_depreciation_records"