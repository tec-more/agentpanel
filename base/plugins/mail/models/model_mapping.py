"""
事件→消息映射模型 - 配置哪些业务模型的 CRUD 事件自动产生消息
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class MessageModelMapping(BaseModel, TimestampMixin):
    """事件→消息映射（订阅 audit 的 model.* 事件时，按此表配置自动产生系统消息）"""
    model = fields.CharField(max_length=100, description="业务表名", index=True)
    # 动作：create / update / delete
    action = fields.CharField(max_length=20, description="动作(create/update/delete)", index=True)
    # 关联子类型ID（软关联 MessageSubtype）
    subtype_id = fields.IntField(description="关联子类型ID", index=True)
    # 触发条件字段（仅 update 时校验该字段在 changed_fields 内）
    condition_field = fields.CharField(
        max_length=100, null=True, description="触发条件字段名", index=True
    )
    # 进一步要求 after_data[condition_field] == condition_value（用于审批 status=approved 等分支）
    condition_value = fields.CharField(
        max_length=255, null=True, description="触发条件字段值"
    )
    # 消息主题模板（支持 {record_id} / {field_name} 占位符）
    name_template = fields.CharField(max_length=500, null=True, description="主题模板")
    body_template = fields.TextField(null=True, description="正文模板")
    is_active = fields.BooleanField(default=True, description="是否启用", index=True)
    notify_followers = fields.BooleanField(default=True, description="是否通知关注者")
    notify_creator = fields.BooleanField(default=False, description="是否通知记录创建者")

    class Meta:
        table = "mail_model_mapping"
        # 同一 model+action+condition_field+condition_value 仅一条映射
        unique_together = (("model", "action", "condition_field", "condition_value"),)
        ordering = ["model", "action"]

    async def to_dict(self, include_subtype: bool = False):
        data = {
            "id": self.id,
            "model": self.model,
            "action": self.action,
            "subtype_id": self.subtype_id,
            "condition_field": self.condition_field,
            "condition_value": self.condition_value,
            "name_template": self.name_template,
            "body_template": self.body_template,
            "is_active": self.is_active,
            "notify_followers": self.notify_followers,
            "notify_creator": self.notify_creator,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }
        if include_subtype:
            try:
                from base.plugins.mail.models.message_subtype import MessageSubtype
                subtype = await MessageSubtype.get_or_none(id=self.subtype_id)
                data["subtype"] = await subtype.to_dict() if subtype else None
            except Exception:
                data["subtype"] = None
        return data
