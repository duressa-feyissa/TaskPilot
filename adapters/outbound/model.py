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
    email = Column(String(255), unique=True, nullable=False)   # Added length
    access_token = Column(String(500), nullable=False)         # Added length
    refresh_token = Column(String(500), nullable=False)        # Added length
    token_uri = Column(String(500), nullable=False)            # Added length
    id_token = Column(String(500), nullable=False)             # Added length
    name = Column(String(255), nullable=True)                  # Added length
    given_name = Column(String(255), nullable=True)            # Added length
    family_name = Column(String(255), nullable=True)           # Added length
    picture = Column(String(500), nullable=True)               # Added length
    locale = Column(String(50), nullable=True)                 # Added length
    history_id = Column(String(255), nullable=True)

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
            history_id=self.history_id
        )


class EmailModel(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    sender_email = Column(String(255), nullable=False)    # Added length
    sender_name = Column(String(255), nullable=False)     # Added length
    receiver_email = Column(String(255), nullable=False)  # Added length
    history_id = Column(String(255), nullable=False)      # Added length
    date = Column(DateTime, nullable=False)
    title = Column(String(500), nullable=False)           # Added length
    summary = Column(String(2000), nullable=False)        # Added length
    priority = Column(String(50), nullable=False)         # Added length
    read = Column(String(10), nullable=False)             # Added length

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
