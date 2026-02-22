"""Package init – import all models so Base.metadata knows about them."""

from app.models.user import User
from app.models.message import Message
from app.models.task import Task
from app.models.alert import Alert
from app.models.custom_domain import CustomDomain
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.models.channel import Channel
from app.models.message_task_map import MessageTaskMap
from app.models.ai_event import AIEvent

__all__ = [
    "User", "Message", "Task", "Alert", "CustomDomain",
    "Workspace", "WorkspaceMember", "Channel", "MessageTaskMap", "AIEvent",
]
