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
            cols_to_add = [
                # policy_changes
                ("policy_changes", "maker_id", "VARCHAR(255)"),
                ("policy_changes", "maker_submitted_at", "DATETIME"),
                ("policy_changes", "maker_rationale", "TEXT"),
                ("policy_changes", "checker_id", "VARCHAR(255)"),
                ("policy_changes", "checker_reviewed_at", "DATETIME"),
                ("policy_changes", "checker_comments", "TEXT"),
                ("policy_changes", "maker_checker_status", "VARCHAR(50) DEFAULT 'DRAFT'"),
                ("policy_changes", "digital_signature_hash", "VARCHAR(64)"),
                # regulatory_sources
                ("regulatory_sources", "regulator", "VARCHAR(255)"),
                ("regulatory_sources", "authority_level", "VARCHAR(50) DEFAULT 'OFFICIAL_PRIMARY'"),
                ("regulatory_sources", "source_type", "VARCHAR(50) DEFAULT 'STATUTORY_BODY'"),
                ("regulatory_sources", "publication_id", "VARCHAR(100)"),
                ("regulatory_sources", "title", "VARCHAR(512)"),
                ("regulatory_sources", "document_sha256", "VARCHAR(64)"),
                ("regulatory_sources", "publication_date", "DATETIME"),
                ("regulatory_sources", "effective_date", "DATETIME"),
                ("regulatory_sources", "superseded_date", "DATETIME"),
                ("regulatory_sources", "status", "VARCHAR(50) DEFAULT 'ACTIVE'"),
                ("regulatory_sources", "retrieved_at", "DATETIME"),
                ("regulatory_sources", "canonical_source", "VARCHAR(255)"),
                ("regulatory_sources", "metadata_payload", "JSON"),
                # compliance_assessments
                ("compliance_assessments", "total_obligations", "INTEGER DEFAULT 0"),
                ("compliance_assessments", "remediations_created", "INTEGER DEFAULT 0"),
                # compliance_run_snapshots
                ("compliance_run_snapshots", "source_version", "VARCHAR(50) DEFAULT '1.0.0'"),
                ("compliance_run_snapshots", "obligation_ids", "JSON"),
                ("compliance_run_snapshots", "applicability_assessment_ids", "JSON"),
                ("compliance_run_snapshots", "control_ids", "JSON"),
                ("compliance_run_snapshots", "gap_ids", "JSON"),
                ("compliance_run_snapshots", "remediation_ids", "JSON"),
                ("compliance_run_snapshots", "evidence_ids", "JSON"),
                ("compliance_run_snapshots", "human_decisions", "JSON"),
                # controls
                ("controls", "owner_id", "VARCHAR(255)"),
                ("controls", "business_unit_id", "VARCHAR(100)"),
                ("controls", "process_id", "VARCHAR(100)"),
                ("controls", "system_id", "VARCHAR(100)"),
                ("controls", "execution_type", "VARCHAR(50) DEFAULT 'AUTOMATED'"),
                ("controls", "preventive_or_detective", "VARCHAR(50) DEFAULT 'PREVENTIVE'"),
                ("controls", "automation_level", "VARCHAR(50) DEFAULT 'HIGH'"),
                ("controls", "regulatory_obligation_ids", "JSON"),
                ("controls", "policy_ids", "JSON"),
                ("controls", "evidence_requirements", "TEXT"),
                ("controls", "test_procedure", "TEXT"),
                ("controls", "last_tested_at", "DATETIME"),
                ("controls", "effectiveness_status", "VARCHAR(50) DEFAULT 'EFFECTIVE'"),
                ("controls", "status", "VARCHAR(50) DEFAULT 'ACTIVE'"),
                ("controls", "effective_from", "DATETIME"),
                ("controls", "effective_to", "DATETIME"),
                # policies
                ("policies", "effective_from", "DATETIME"),
                ("policies", "effective_to", "DATETIME"),
                # claim_lineages
                ("claim_lineages", "obligation_id", "VARCHAR(64)"),
            ]
            for tbl, col, col_type in cols_to_add:
                try:
                    await conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN {col} {col_type}"))
                except Exception:
                    pass
