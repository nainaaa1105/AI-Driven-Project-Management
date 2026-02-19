"""Package init – import all models so Base.metadata knows about them."""

from app.models.user import User
from app.models.message import Message
from app.models.task import Task
from app.models.alert import Alert
from app.models.custom_domain import CustomDomain

__all__ = ["User", "Message", "Task", "Alert", "CustomDomain"]
