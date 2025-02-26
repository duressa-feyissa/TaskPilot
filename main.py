from contextlib import asynccontextmanager

from fastapi import FastAPI

from adapters.outbound.repository import SQLAlchemyUserRepository
from core.application.services import EmailService
from dependencies import AsyncSessionLocal, get_router, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    async with AsyncSessionLocal() as db:
        app.state.email_service = EmailService(SQLAlchemyUserRepository(db))
        await app.state.email_service.watch_gmail()

    yield
    print("Shutting down...")


app = FastAPI(lifespan=lifespan)

app.include_router(get_router())
