from abc import ABC, abstractmethod
from typing import List, Optional

from core.domain.entity import Email, User


class IUserServicePort(ABC):

    @abstractmethod
    async def create_user(self, user: User) -> User:
        pass

    @abstractmethod
    async def get_user_by_email(self, email: str) -> User:
        pass


class IEmailServicePort(ABC):

    @abstractmethod
    async def watch_user(self, user: User) -> dict:
        pass

    @abstractmethod
    async def watch_gmail(self) -> dict:
        """Registers the user's Gmail inbox for push notifications."""
        pass

    @abstractmethod
    async def fetch_new_emails(self, user: User, history_id: str) -> List[dict]:
        """Fetches new emails since the given history ID."""
        pass

    @abstractmethod
    async def store_user_tokens(self, user: User) -> None:
        """Stores updated user authentication tokens securely."""
        pass

    @abstractmethod
    async def get_user_credentials(self, email: str) -> Optional[User]:
        """Retrieves stored credentials for a user."""
        pass

    @abstractmethod
    async def process_emails(self, user: User, history_id: str):
        """Retrieves stored credentials for a user."""
        pass

    @abstractmethod
    async def get_emails(self, receiver_email: str, skip: int, limit: int) -> List[Email]:
        pass
