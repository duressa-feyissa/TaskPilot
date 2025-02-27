from abc import ABC, abstractmethod
from typing import List, Optional

from core.domain.entity import Email, User


class IUserRepositoryPort(ABC):
    @abstractmethod
    async def add_user(self, user: User) -> User:
        pass

    @abstractmethod
    def get_user_by_email(self, email: str) -> Optional[User]:
        pass

    @abstractmethod
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        pass

    @abstractmethod
    async def update_user(self, id: int, user: User) -> User:
        pass

    @abstractmethod
    async def get_users(self) -> List[User]:
        pass

    @abstractmethod
    async def set_email_history(self, email: Email) -> None:
        pass

    @abstractmethod
    async def get_emails(self, receiver_email: str, skip: int, limit: int) -> List[Email]:
        pass
