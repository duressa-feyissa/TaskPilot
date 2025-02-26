from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.ext.declarative import declarative_base

from core.domain.entity import User

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
