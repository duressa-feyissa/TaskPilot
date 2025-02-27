from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from adapters.outbound.model import EmailModel, UserModel
from core.application.ports.outbound import IUserRepositoryPort
from core.domain.entity import Email, User


class SQLAlchemyUserRepository(IUserRepositoryPort):
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def add_user(self, user: User) -> User:
        async with self.db_session.begin():
            user_db = UserModel(**user.model_dump())
            self.db_session.add(user_db)
            await self.db_session.commit()
            return user_db.to_domain()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        async with self.db_session.begin():
            result = await self.db_session.execute(select(UserModel).filter_by(email=email))
            user_db = result.scalars().first()
            return user_db.to_domain() if user_db else None

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        async with self.db_session.begin():
            result = await self.db_session.execute(select(UserModel).filter_by(id=user_id))
            user_db = result.scalars().first()
            return user_db.to_domain() if user_db else None

    async def update_user(self, user_id: int, user: User) -> User:
        async with self.db_session.begin():
            result = await self.db_session.execute(select(UserModel).filter_by(id=user_id))
            user_db = result.scalars().first()
            if not user_db:
                raise None

            for key, value in user.dict(exclude_unset=True).items():
                setattr(user_db, key, value)

            await self.db_session.commit()
            return user_db.to_domain()

    async def get_users(self) -> List[User]:
        async with self.db_session.begin():
            result = await self.db_session.execute(select(UserModel))
            return [user.to_domain() for user in result.scalars()]

    async def set_email_history(self, email: Email) -> None:
        async with self.db_session.begin():
            email_db = EmailModel(**email.model_dump())
            self.db_session.add(email_db)
            await self.db_session.commit()
            return email_db.to_domain()

    async def get_emails(self, receiver_email: str, skip: int, limit: int) -> List[Email]:
        async with self.db_session.begin():
            result = await self.db_session.execute(select(EmailModel).filter_by(receiver_email=receiver_email).offset(skip).limit(limit))
            return [email.to_domain() for email in result.scalars()]
