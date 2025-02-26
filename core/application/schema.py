from typing import Dict, List

from pydantic import BaseModel, Field


class EmailData(BaseModel):
    id: str
    threadId: str
    labelIds: List[str] = Field(default_factory=list)
    snippet: str
    headers: Dict[str, str] = Field(default_factory=dict)
    body: str = ""
