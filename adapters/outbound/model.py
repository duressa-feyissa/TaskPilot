from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base

from core.domain.entity import Email, User

Base = declarative_base()


class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    token_uri = Column(String, nullable=False)
    id_token = Column(String, nullable=False)
    name = Column(String, nullable=True)
    given_name = Column(String, nullable=True)
    family_name = Column(String, nullable=True)
    picture = Column(String, nullable=True)
    locale = Column(String, nullable=True)

    def to_domain(self) -> User:
        return User(
            id=self.id,
            email=self.email,
            access_token=self.access_token,
            refresh_token=self.refresh_token,
            token_uri=self.token_uri,
            id_token=self.id_token,
            name=self.name,
            given_name=self.given_name,
            family_name=self.family_name,
            picture=self.picture,
            locale=self.locale,
        )


class EmailModel(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    sender_email = Column(String, nullable=False)
    sender_name = Column(String, nullable=False)
    receiver_email = Column(String, nullable=False)
    history_id = Column(String, nullable=False)
    date = Column(DateTime, nullable=False)
    title = Column(String, nullable=False)
    summary = Column(String, nullable=False)
    priority = Column(String, nullable=False)
    read = Column(String, nullable=False)

    def to_domain(self) -> Email:
        return Email(
            id=self.id,
            user_id=self.user_id,
            sender_email=self.sender_email,
            sender_name=self.sender_name,
            receiver_email=self.receiver_email,
            history_id=self.history_id,
            date=self.date,
            title=self.title,
            summary=self.summary,
            priority=self.priority,
            read=self.read
        )
