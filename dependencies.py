from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from adapters.outbound.model import Base
from adapters.outbound.repository import SQLAlchemyUserRepository
from core.application.services import EmailService, UserService

DATABASE_URL = "sqlite+aiosqlite:///./task_pilot.db"

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(SQLAlchemyUserRepository(db))


async def get_email_service(db: AsyncSession = Depends(get_db)) -> EmailService:
    return EmailService(SQLAlchemyUserRepository(db))


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_router():
    """Import `router` inside this function to avoid circular import."""
    from adapters.inbound.api import router
    return router
