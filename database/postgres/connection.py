from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from services.api.config import get_settings
from database.postgres.models import Base

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing an async database session per request."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db(recreate: bool = False) -> None:
    """Initialize database tables and ensure all columns exist."""
    async with engine.begin() as conn:
        if recreate:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        
        # Soft migration for SQLite dev databases
        if "sqlite" in settings.DATABASE_URL:
            try:
                await conn.execute(text("ALTER TABLE policy_changes ADD COLUMN maker_id VARCHAR(255)"))
            except Exception:
                pass
            try:
                await conn.execute(text("ALTER TABLE policy_changes ADD COLUMN maker_submitted_at DATETIME"))
            except Exception:
                pass
            try:
                await conn.execute(text("ALTER TABLE policy_changes ADD COLUMN maker_rationale TEXT"))
            except Exception:
                pass
            try:
                await conn.execute(text("ALTER TABLE policy_changes ADD COLUMN checker_id VARCHAR(255)"))
            except Exception:
                pass
            try:
                await conn.execute(text("ALTER TABLE policy_changes ADD COLUMN checker_reviewed_at DATETIME"))
            except Exception:
                pass
            try:
                await conn.execute(text("ALTER TABLE policy_changes ADD COLUMN checker_comments TEXT"))
            except Exception:
                pass
            try:
                await conn.execute(text("ALTER TABLE policy_changes ADD COLUMN maker_checker_status VARCHAR(50) DEFAULT 'DRAFT'"))
            except Exception:
                pass
            try:
                await conn.execute(text("ALTER TABLE policy_changes ADD COLUMN digital_signature_hash VARCHAR(64)"))
            except Exception:
                pass
