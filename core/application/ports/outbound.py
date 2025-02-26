from abc import ABC, abstractmethod
from typing import List, Optional

from core.domain.entity import User


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
