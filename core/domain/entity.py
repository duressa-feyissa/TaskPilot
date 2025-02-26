from datetime import date
from typing import Optional

from pydantic import BaseModel


class User(BaseModel):
    id: Optional[int] = None
    email: str
    access_token: str
    refresh_token: str
    token_uri: str
    id_token: str
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    picture: Optional[str] = None

    class Config:
        from_attributes = True
