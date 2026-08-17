import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Float,
    JSON,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def generate_uuid() -> str:
    return str(uuid.uuid4())


# =========================================================================
# LAYER 1: IMMUTABLE SOURCE EVIDENCE (What the regulator actually published)
# =========================================================================

class RegulatorySource(Base):
    __tablename__ = "regulatory_sources"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)  # e.g., "Reserve Bank of India", "OCC", "Fed", "MAS", "FCA"
    acronym = Column(String(50), nullable=False, index=True)
    jurisdiction = Column(String(50), nullable=False, index=True)  # IN, US, UK, SG, EU
    source_url = Column(String(1024), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    regulations = relationship("Regulation", back_populates="source")


class Regulation(Base):
    __tablename__ = "regulations"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    source_id = Column(String(64), ForeignKey("regulatory_sources.id"), nullable=False, index=True)
    code = Column(String(100), nullable=False, index=True)  # e.g., "RBI/2026-27/04"
    title = Column(String(512), nullable=False)
    doc_type = Column(String(50), nullable=False)  # Circular, Master Direction, Law, Guidance
    jurisdiction = Column(String(50), nullable=False, index=True)
    current_version = Column(String(20), default="1.0.0")
    status = Column(String(50), default="ACTIVE")  # ACTIVE, SUPERSEDED, DRAFT
    created_at = Column(DateTime, default=datetime.utcnow)

    source = relationship("RegulatorySource", back_populates="regulations")
    versions = relationship("DocumentVersion", back_populates="regulation", cascade="all, delete-orphan")


class DocumentVersion(Base):
    """Immutable evidence snapshot of a regulatory document at a specific point in time."""
    __tablename__ = "document_versions"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    regulation_id = Column(String(64), ForeignKey("regulations.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(String(20), nullable=False, default="1.0.0")
    sha256_hash = Column(String(64), nullable=False, index=True)  # Immutable cryptographic fingerprint
    storage_uri = Column(String(1024), nullable=False)  # s3://compliance-platform/raw/...
    retrieved_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    publication_date = Column(DateTime, nullable=False)
    effective_date = Column(DateTime, nullable=False)
    superseded_date = Column(DateTime, nullable=True)
    page_count = Column(Integer, default=1)
    raw_content = Column(Text, nullable=False)
    metadata_payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    regulation = relationship("Regulation", back_populates="versions")
    sections = relationship("RegulatorySection", back_populates="document_version", cascade="all, delete-orphan")
    requirements = relationship("RequirementVersion", back_populates="document_version", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_reg_version_unique", "regulation_id", "version_number", unique=True),
    )


class RegulatorySection(Base):
    """Specific section/paragraph/page coordinates of source evidence."""
    __tablename__ = "regulatory_sections"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    document_version_id = Column(String(64), ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    section_number = Column(String(50), nullable=False)  # "Section 4.1.2"
    heading = Column(String(512), nullable=True)
    page_number = Column(Integer, default=1)
    paragraph_index = Column(Integer, default=0)
    content = Column(Text, nullable=False)
    table_data = Column(JSON, nullable=True)  # Structured table data if applicable
    order_index = Column(Integer, default=0)
    embedding = Column(JSON, nullable=True)

    document_version = relationship("DocumentVersion", back_populates="sections")


# =========================================================================
# LAYER 2: STRUCTURED INTERPRETATION (What extraction believes it means)
# =========================================================================

class RequirementVersion(Base):
    """Structured, versioned compliance obligation extracted from source evidence."""
    __tablename__ = "requirement_versions"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    document_version_id = Column(String(64), ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    section_id = Column(String(64), ForeignKey("regulatory_sections.id", ondelete="SET NULL"), nullable=True)
    req_code = Column(String(100), nullable=False, index=True)  # "REQ-RBI-2026-04-01"
    version_number = Column(String(20), default="1.0.0")
    
    obligation_text = Column(Text, nullable=False)
    obligation_type = Column(String(50), default="MANDATORY")  # MANDATORY, CONDITIONAL, PROHIBITED, RECOMMENDED
    conditions = Column(JSON, default=list)  # ["customer_risk == 'high'", "transaction_value > 50000"]
    exceptions = Column(JSON, default=list)  # ["except when customer is central government entity"]
    applies_to = Column(JSON, default=list)  # ["Commercial Banks", "NBFCs"]
    penalties = Column(JSON, default=list)
    risk_category = Column(String(100), default="Operational & Cybersecurity Risk")
    
    extracted_by_model = Column(String(100), default="claude-3-5-sonnet")
    extraction_prompt_version = Column(String(50), default="v1.0")
    created_at = Column(DateTime, default=datetime.utcnow)

    document_version = relationship("DocumentVersion", back_populates="requirements")
    claim_lineages = relationship("ClaimLineage", back_populates="requirement")


# =========================================================================
# LAYER 3: AI-GENERATED ACTIONS & POLICIES (Tenant-Scoped)
# =========================================================================

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(64), unique=True, nullable=False, index=True)
    tier = Column(String(50), default="standard")  # standard, enterprise, dedicated
    neo4j_database = Column(String(64), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    policies = relationship("Policy", back_populates="tenant")
    audit_events = relationship("AuditEvent", back_populates="tenant")
    compliance_runs = relationship("ComplianceRunSnapshot", back_populates="tenant")


class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="compliance_officer")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Policy(Base):
    __tablename__ = "policies"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    policy_code = Column(String(100), nullable=False)  # "POL-INF-001"
    title = Column(String(512), nullable=False)
    category = Column(String(100), nullable=False)
    jurisdiction = Column(String(50), nullable=False)
    current_version = Column(String(20), default="1.0.0")
    status = Column(String(50), default="APPROVED")
    owner_department = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="policies")
    versions = relationship("PolicyVersion", back_populates="policy", cascade="all, delete-orphan")
    clauses = relationship("PolicyClause", back_populates="policy", cascade="all, delete-orphan")
    controls = relationship("Control", back_populates="policy", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_tenant_policy_code", "tenant_id", "policy_code", unique=True),
    )


class PolicyVersion(Base):
    __tablename__ = "policy_versions"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    policy_id = Column(String(64), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    version_number = Column(String(20), nullable=False)
    status = Column(String(50), default="APPROVED")  # DRAFT, IN_REVIEW, APPROVED, SUPERSEDED
    content_full = Column(Text, nullable=False)
    changelog = Column(Text, nullable=True)
    approved_by = Column(String(255), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    effective_date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    policy = relationship("Policy", back_populates="versions")


class PolicyClause(Base):
    __tablename__ = "policy_clauses"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    policy_id = Column(String(64), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    clause_number = Column(String(50), nullable=False)
    title = Column(String(255), nullable=True)
    text = Column(Text, nullable=False)
    version = Column(String(20), default="1.0.0")
    embedding = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    policy = relationship("Policy", back_populates="clauses")


class Control(Base):
    __tablename__ = "controls"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(64), nullable=False, index=True)
    policy_id = Column(String(64), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False, index=True)
    control_code = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    frequency = Column(String(50), default="CONTINUOUS")
    control_type = Column(String(50), default="PREVENTIVE")
    version = Column(String(20), default="1.0.0")
    responsible_role = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    policy = relationship("Policy", back_populates="controls")


# =========================================================================
# CLAIM LINEAGE & REPRODUCIBILITY SNAPSHOTS
# =========================================================================

class ClaimLineage(Base):
    """
    Explainability by Construction:
    Every AI-generated sentence/claim links directly to the exact requirement,
    source section, document version, and page coordinates.
    """
    __tablename__ = "claim_lineages"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    policy_change_id = Column(String(64), ForeignKey("policy_changes.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_version_id = Column(String(64), ForeignKey("requirement_versions.id"), nullable=False, index=True)
    source_section_id = Column(String(64), ForeignKey("regulatory_sections.id"), nullable=True)
    document_version_id = Column(String(64), ForeignKey("document_versions.id"), nullable=False)
    
    claim_text = Column(Text, nullable=False)
    source_verbatim_quote = Column(Text, nullable=False)
    page_number = Column(Integer, default=1)
    paragraph_index = Column(Integer, default=0)
    verification_status = Column(String(50), default="VERIFIED")  # VERIFIED, UNVERIFIED, HALLUCINATION_FLAGGED
    similarity_score = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    requirement = relationship("RequirementVersion", back_populates="claim_lineages")
    policy_change = relationship("PolicyChange", back_populates="claim_lineages")


class ComplianceAssessment(Base):
    __tablename__ = "compliance_assessments"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(64), nullable=False, index=True)
    regulation_id = Column(String(64), ForeignKey("regulations.id"), nullable=False, index=True)
    document_version_id = Column(String(64), ForeignKey("document_versions.id"), nullable=True)
    status = Column(String(50), default="QUEUED")  # QUEUED, PROCESSING, COMPLETED, FAILED, GATES_FAILED
    confidence_score = Column(Float, default=0.0)
    overall_summary = Column(Text, nullable=True)
    total_requirements = Column(Integer, default=0)
    gaps_detected = Column(Integer, default=0)
    mode = Column(String(50), default="standard")  # standard, shadow
    
    # 8-Gate Verification Scorecard
    verification_scorecard = Column(JSON, default=dict)
    all_gates_passed = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    changes = relationship("PolicyChange", back_populates="assessment", cascade="all, delete-orphan")


class PolicyChange(Base):
    __tablename__ = "policy_changes"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    assessment_id = Column(String(64), ForeignKey("compliance_assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    policy_id = Column(String(64), ForeignKey("policies.id"), nullable=False, index=True)
    clause_id = Column(String(64), ForeignKey("policy_clauses.id"), nullable=True)
    change_type = Column(String(50), default="AMENDMENT")
    original_text = Column(Text, nullable=True)
    proposed_text = Column(Text, nullable=False)
    justification = Column(Text, nullable=False)
    citations = Column(JSON, default=list)
    
    # Gate Verification Results
    citation_verified = Column(Boolean, default=False)
    coverage_verified = Column(Boolean, default=False)
    rule_check_passed = Column(Boolean, default=False)
    exceptions_preserved = Column(Boolean, default=True)
    
    status = Column(String(50), default="PENDING_REVIEW")  # PENDING_REVIEW, APPROVED, REJECTED, REVISE
    reviewed_by = Column(String(255), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    # Maker-Checker (4-Eyes Principle) Dual Control Governance
    maker_id = Column(String(255), nullable=True)
    maker_submitted_at = Column(DateTime, nullable=True)
    maker_rationale = Column(Text, nullable=True)
    checker_id = Column(String(255), nullable=True)
    checker_reviewed_at = Column(DateTime, nullable=True)
    checker_comments = Column(Text, nullable=True)
    maker_checker_status = Column(String(50), default="DRAFT")  # DRAFT, MAKER_SUBMITTED, CHECKER_APPROVED, REJECTED, PUBLISHED
    digital_signature_hash = Column(String(64), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    assessment = relationship("ComplianceAssessment", back_populates="changes")
    claim_lineages = relationship("ClaimLineage", back_populates="policy_change", cascade="all, delete-orphan")


class ComplianceRunSnapshot(Base):
    """
    Auditor Replay Snapshot:
    Enables re-running and inspecting the exact frozen system state 6 months later.
    """
    __tablename__ = "compliance_run_snapshots"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    run_id = Column(String(100), unique=True, nullable=False, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    assessment_id = Column(String(64), ForeignKey("compliance_assessments.id", ondelete="CASCADE"), nullable=False)
    
    # Frozen Version Matrix
    regulation_version_id = Column(String(64), nullable=False)
    document_sha256 = Column(String(64), nullable=False)
    model_version = Column(String(100), nullable=False)  # e.g., "anthropic.claude-3-5-sonnet-20240620-v1:0"
    prompt_version = Column(String(50), nullable=False)  # e.g., "v2.1"
    workflow_version = Column(String(50), nullable=False)  # e.g., "workflow-3.2"
    
    # Recorded State & Intermediate Payloads
    input_state = Column(JSON, default=dict)
    retrieved_chunks = Column(JSON, default=list)
    graph_query_snapshot = Column(JSON, default=list)
    intermediate_steps = Column(JSON, default=dict)
    verification_scorecard = Column(JSON, default=dict)
    final_output = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="compliance_runs")


class ReviewerFeedbackRecord(Base):
    """Stores human reviewer decisions & corrections as evaluation/benchmark dataset."""
    __tablename__ = "reviewer_feedback_records"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(64), nullable=False, index=True)
    run_id = Column(String(100), nullable=False, index=True)
    policy_change_id = Column(String(64), nullable=False, index=True)
    decision = Column(String(50), nullable=False)  # APPROVE, REJECT, REVISE
    rejection_reason_category = Column(String(100), nullable=True)  # SCOPE_MISMATCH, JURISDICTION_ERROR, OVERBROAD
    reviewer_comments = Column(Text, nullable=True)
    reviewer_id = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(64), nullable=False, index=True)
    workflow_type = Column(String(50), default="defensible_compliance_orchestration")
    status = Column(String(50), default="RUNNING")
    current_node = Column(String(100), nullable=True)
    state_checkpoint = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(64), nullable=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(64), nullable=False)
    action = Column(String(50), nullable=False)
    details = Column(JSON, default=dict)
    ip_address = Column(String(50), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    tenant = relationship("Tenant", back_populates="audit_events")
