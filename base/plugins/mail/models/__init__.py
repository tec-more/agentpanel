# 消息模块 - 模型包
from base.plugins.mail.models.message import Message
from base.plugins.mail.models.message_subtype import MessageSubtype
from base.plugins.mail.models.follower import Follower
from base.plugins.mail.models.notification import Notification
from base.plugins.mail.models.model_mapping import MessageModelMapping

__all__ = ["Message", "MessageSubtype", "Follower", "Notification", "MessageModelMapping"]
