import datetime
from typing import Optional

from pydantic import BaseModel


class UserInfo(BaseModel):
    email: str


class Token(BaseModel):
    access_token: str
    token_type: str


class Profile(BaseModel):
    id: Optional[int] = None
    email: str
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    picture: Optional[str] = None


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


class Email(BaseModel):
    id: Optional[int] = None
    user_id: int
    sender_email: str
    sender_name: str
    receiver_email: str
    history_id: str
    date: datetime.date
    title: str
    summary: str
    priority: str
    read: bool = False

    class Config:
        from_attributes = True
