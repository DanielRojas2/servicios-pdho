from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(AsyncAttrs, DeclarativeBase):
    """Clase base declarativa de SQLAlchemy 2.0 con soporte asíncrono."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Generador de sesiones asíncronas para inyección de dependencias de FastAPI."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
