from abc import abstractmethod
from typing import List, Optional

from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from adapters.outbound.model import UserModel
from core.application.ports.outbound import IUserRepositoryPort
from core.domain.entity import User


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
