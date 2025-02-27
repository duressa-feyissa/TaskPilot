from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EmailPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EmailData(BaseModel):
    id: str
    threadId: str
    body: Optional[str] = None
    senderName: Optional[str] = None
    senderEmail: str
    priority: EmailPriority = EmailPriority.LOW


class EmailHistoryRequest(BaseModel):
    email: str
    history_id: str
