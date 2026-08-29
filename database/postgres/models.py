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
# LAYER 1: IMMUTABLE REGULATORY SOURCE EVIDENCE & PROVISIONS
# =========================================================================

class AuthorityLevel:
    OFFICIAL_PRIMARY = "OFFICIAL_PRIMARY"
    OFFICIAL_SECONDARY = "OFFICIAL_SECONDARY"
    AUTHORITATIVE_INTERNAL = "AUTHORITATIVE_INTERNAL"
    INTERNAL_INTERPRETATION = "INTERNAL_INTERPRETATION"
    AI_GENERATED = "AI_GENERATED"


class RegulatorySource(Base):
    """The authoritative external regulatory body or primary publication source."""
    __tablename__ = "regulatory_sources"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)  # e.g., "Reserve Bank of India", "OCC", "Fed", "MAS", "FCA"
    regulator = Column(String(255), nullable=True)  # Alias for regulator name
    acronym = Column(String(50), nullable=False, index=True)
    authority_level = Column(String(50), default=AuthorityLevel.OFFICIAL_PRIMARY)
    source_type = Column(String(50), default="STATUTORY_BODY")
    source_url = Column(String(1024), nullable=True)
    publication_id = Column(String(100), nullable=True)
    title = Column(String(512), nullable=True)
    document_sha256 = Column(String(64), nullable=True)
    publication_date = Column(DateTime, nullable=True)
    effective_date = Column(DateTime, nullable=True)
    superseded_date = Column(DateTime, nullable=True)
    status = Column(String(50), default="ACTIVE")
    retrieved_at = Column(DateTime, default=datetime.utcnow)
    canonical_source = Column(String(255), nullable=True)
    metadata_payload = Column(JSON, default=dict)
    jurisdiction = Column(String(50), nullable=False, index=True)  # IN, US, UK, SG, EU, GLOBAL
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    regulations = relationship("Regulation", back_populates="source")
    provisions = relationship("RegulatoryProvision", back_populates="source", cascade="all, delete-orphan")


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


class RegulatoryProvision(Base):
    """Meaningful legal/regulatory unit (Section, Article, Paragraph) beneath the source."""
    __tablename__ = "regulatory_provisions"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    regulatory_source_id = Column(String(64), ForeignKey("regulatory_sources.id", ondelete="CASCADE"), nullable=True, index=True)
    document_version_id = Column(String(64), ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=True, index=True)
    section_number = Column(String(50), nullable=False)  # "Section 4.1.2"
    paragraph_number = Column(Integer, default=0)
    heading = Column(String(512), nullable=True)
    text = Column(Text, nullable=False)
    page_number = Column(Integer, default=1)
    hierarchy_path = Column(String(512), nullable=True)  # "Chapter 2 > Section 4 > Paragraph 1"
    effective_from = Column(DateTime, default=datetime.utcnow)
    effective_to = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    source = relationship("RegulatorySource", back_populates="provisions")
    obligations = relationship("RegulatoryObligation", back_populates="provision", cascade="all, delete-orphan")


class RegulatorySection(Base):
    """Specific section/paragraph/page coordinates of source evidence (compatibility)."""
    __tablename__ = "regulatory_sections"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    document_version_id = Column(String(64), ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    section_number = Column(String(50), nullable=False)  # "Section 4.1.2"
    heading = Column(String(512), nullable=True)
    page_number = Column(Integer, default=1)
    paragraph_index = Column(Integer, default=0)
    content = Column(Text, nullable=False)
    table_data = Column(JSON, nullable=True)
    order_index = Column(Integer, default=0)
    embedding = Column(JSON, nullable=True)

    document_version = relationship("DocumentVersion", back_populates="sections")


# =========================================================================
# LAYER 2: FIRST-CLASS REGULATORY OBLIGATION MODEL (Deontic Logic)
# =========================================================================

class ObligationType:
    MANDATE = "MANDATE"
    PROHIBITION = "PROHIBITION"
    CONDITION = "CONDITION"
    EXCEPTION = "EXCEPTION"
    THRESHOLD = "THRESHOLD"
    DEADLINE = "DEADLINE"
    REPORTING = "REPORTING"
    DISCLOSURE = "DISCLOSURE"
    RECORDKEEPING = "RECORDKEEPING"
    GOVERNANCE = "GOVERNANCE"


class RegulatoryObligation(Base):
    """First-class canonical compliance obligation with rich deontic structure."""
    __tablename__ = "regulatory_obligations"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    provision_id = Column(String(64), ForeignKey("regulatory_provisions.id", ondelete="SET NULL"), nullable=True, index=True)
    document_version_id = Column(String(64), ForeignKey("document_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    obligation_code = Column(String(100), nullable=False, index=True)  # "OBL-RBI-KYC-001"
    obligation_type = Column(String(50), default=ObligationType.MANDATE)
    
    requirement_text = Column(Text, nullable=False)
    normalized_requirement = Column(Text, nullable=True)
    mandatory_action = Column(Text, nullable=True)
    subject = Column(String(255), default="Regulated Entity")
    object = Column(String(255), nullable=True)
    
    conditions = Column(JSON, default=list)  # ["transaction_value > 50000"]
    exceptions = Column(JSON, default=list)  # ["except when customer is central government entity"]
    thresholds = Column(JSON, default=list)  # ["INR 50,000", "10 years"]
    deadlines = Column(JSON, default=list)  # ["within 6 hours"]
    reporting_requirements = Column(JSON, default=list)
    jurisdiction = Column(String(50), default="GLOBAL", index=True)
    
    effective_from = Column(DateTime, default=datetime.utcnow)
    effective_to = Column(DateTime, nullable=True)
    extraction_confidence = Column(Float, default=1.0)
    extraction_method = Column(String(50), default="STRUCTURAL_PARSER")
    status = Column(String(50), default="ACTIVE")
    created_at = Column(DateTime, default=datetime.utcnow)

    provision = relationship("RegulatoryProvision", back_populates="obligations")
    applicabilities = relationship("ApplicabilityAssessment", back_populates="obligation", cascade="all, delete-orphan")
    gaps = relationship("ComplianceGap", back_populates="obligation", cascade="all, delete-orphan")
    impact_assessments = relationship("ImpactAssessment", back_populates="obligation", cascade="all, delete-orphan")


class RequirementVersion(Base):
    """Compatibility requirement entity linking to legacy runs."""
    __tablename__ = "requirement_versions"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    document_version_id = Column(String(64), ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    section_id = Column(String(64), ForeignKey("regulatory_sections.id", ondelete="SET NULL"), nullable=True)
    req_code = Column(String(100), nullable=False, index=True)
    version_number = Column(String(20), default="1.0.0")
    
    obligation_text = Column(Text, nullable=False)
    obligation_type = Column(String(50), default="MANDATORY")
    conditions = Column(JSON, default=list)
    exceptions = Column(JSON, default=list)
    applies_to = Column(JSON, default=list)
    penalties = Column(JSON, default=list)
    risk_category = Column(String(100), default="Operational & Cybersecurity Risk")
    
    extracted_by_model = Column(String(100), default="claude-3-5-sonnet")
    extraction_prompt_version = Column(String(50), default="v1.0")
    created_at = Column(DateTime, default=datetime.utcnow)

    document_version = relationship("DocumentVersion", back_populates="requirements")
    claim_lineages = relationship("ClaimLineage", back_populates="requirement")


# =========================================================================
# LAYER 3: APPLICABILITY, TENANTS & INTERNAL DOCUMENTS
# =========================================================================

class ApplicabilityStatus:
    APPLICABLE = "APPLICABLE"
    PARTIALLY_APPLICABLE = "PARTIALLY_APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNDER_REVIEW = "UNDER_REVIEW"


class ApplicabilityAssessment(Base):
    """Explicit applicability determination layer distinguishing AI recommendation vs Human Approval."""
    __tablename__ = "applicability_assessments"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    obligation_id = Column(String(64), ForeignKey("regulatory_obligations.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    legal_entity_id = Column(String(100), nullable=True)
    jurisdiction = Column(String(50), default="GLOBAL")
    product_id = Column(String(100), nullable=True)
    business_unit_id = Column(String(100), nullable=True)
    
    status = Column(String(50), default=ApplicabilityStatus.APPLICABLE)
    rationale = Column(Text, nullable=False)
    evidence_refs = Column(JSON, default=list)
    
    assessed_by = Column(String(255), default="AI_ASSESSOR")
    assessed_at = Column(DateTime, default=datetime.utcnow)
    confidence = Column(Float, default=1.0)
    
    approval_required = Column(Boolean, default=True)
    approved_by = Column(String(255), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    obligation = relationship("RegulatoryObligation", back_populates="applicabilities")
    impact_assessments = relationship("ImpactAssessment", back_populates="applicability_assessment")


class InternalDocumentType:
    POLICY = "POLICY"
    STANDARD = "STANDARD"
    PROCEDURE = "PROCEDURE"
    SOP = "SOP"
    MANUAL = "MANUAL"
    WORK_INSTRUCTION = "WORK_INSTRUCTION"
    GUIDELINE = "GUIDELINE"
    TRAINING_MATERIAL = "TRAINING_MATERIAL"
    CONTRACT = "CONTRACT"
    CONTROL_DOCUMENT = "CONTROL_DOCUMENT"


class InternalDocument(Base):
    """Generic internal governance document covering Policies, Procedures, SOPs, and Manuals."""
    __tablename__ = "internal_documents"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(64), nullable=False, index=True)
    document_type = Column(String(50), default=InternalDocumentType.POLICY)
    doc_code = Column(String(100), nullable=False, index=True)
    title = Column(String(512), nullable=False)
    owner_id = Column(String(255), nullable=True)
    business_unit_id = Column(String(100), nullable=True)
    jurisdiction = Column(String(50), default="GLOBAL")
    version = Column(String(20), default="1.0.0")
    status = Column(String(50), default="ACTIVE")
    effective_from = Column(DateTime, default=datetime.utcnow)
    effective_to = Column(DateTime, nullable=True)
    supersedes_id = Column(String(64), nullable=True)
    content_hash = Column(String(64), nullable=True)
    content_full = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(64), unique=True, nullable=False, index=True)
    tier = Column(String(50), default="standard")
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


# =========================================================================
# LAYER 4: FIRST-CLASS CONTROLS & POLICY STRUCTURE
# =========================================================================

class Control(Base):
    """First-class internal control with automation, testing procedure, and execution metrics."""
    __tablename__ = "controls"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(64), nullable=False, index=True)
    policy_id = Column(String(64), ForeignKey("policies.id", ondelete="CASCADE"), nullable=True, index=True)
    control_code = Column(String(100), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    control_type = Column(String(50), default="REGULATORY")  # REGULATORY, RISK, OPERATIONAL, IT, FINANCIAL, COMPLIANCE
    execution_type = Column(String(50), default="AUTOMATED")  # MANUAL, AUTOMATED, SEMI_AUTOMATED
    frequency = Column(String(50), default="CONTINUOUS")  # REAL_TIME, DAILY, MONTHLY, QUARTERLY, ANNUAL
    owner_id = Column(String(255), nullable=True)
    business_unit_id = Column(String(100), nullable=True)
    process_id = Column(String(100), nullable=True)
    system_id = Column(String(100), nullable=True)
    preventive_or_detective = Column(String(50), default="PREVENTIVE")  # PREVENTIVE, DETECTIVE, MIXED
    automation_level = Column(String(50), default="HIGH")
    regulatory_obligation_ids = Column(JSON, default=list)
    policy_ids = Column(JSON, default=list)
    evidence_requirements = Column(Text, nullable=True)
    test_procedure = Column(Text, nullable=True)
    last_tested_at = Column(DateTime, nullable=True)
    effectiveness_status = Column(String(50), default="EFFECTIVE")  # EFFECTIVE, DEFICIENT, FAILED, UNTESTED
    version = Column(String(20), default="1.0.0")
    responsible_role = Column(String(100), nullable=True)
    status = Column(String(50), default="ACTIVE")
    effective_from = Column(DateTime, default=datetime.utcnow)
    effective_to = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    policy = relationship("Policy", back_populates="controls")
    control_tests = relationship("ControlTest", back_populates="control", cascade="all, delete-orphan")


class Policy(Base):
    __tablename__ = "policies"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    policy_code = Column(String(100), nullable=False)
    title = Column(String(512), nullable=False)
    category = Column(String(100), nullable=False)
    jurisdiction = Column(String(50), nullable=False)
    current_version = Column(String(20), default="1.0.0")
    status = Column(String(50), default="APPROVED")
    owner_department = Column(String(100), nullable=True)
    effective_from = Column(DateTime, default=datetime.utcnow)
    effective_to = Column(DateTime, nullable=True)
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
    status = Column(String(50), default="APPROVED")
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


# =========================================================================
# LAYER 5: IMPACT ASSESSMENT, RISK & GAP MANAGEMENT
# =========================================================================

class ImpactAssessment(Base):
    """Explicit multi-dimensional impact evaluation determining required organizational changes."""
    __tablename__ = "impact_assessments"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    obligation_id = Column(String(64), ForeignKey("regulatory_obligations.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    applicability_assessment_id = Column(String(64), ForeignKey("applicability_assessments.id", ondelete="SET NULL"), nullable=True)

    impacted_processes = Column(JSON, default=list)
    impacted_business_units = Column(JSON, default=list)
    impacted_systems = Column(JSON, default=list)
    impacted_vendors = Column(JSON, default=list)
    impacted_controls = Column(JSON, default=list)
    impacted_documents = Column(JSON, default=list)

    current_state = Column(Text, nullable=True)
    target_state = Column(Text, nullable=True)
    gap_summary = Column(Text, nullable=True)

    # Specific Change Triggers
    policy_change_required = Column(Boolean, default=False)
    procedure_change_required = Column(Boolean, default=False)
    system_change_required = Column(Boolean, default=False)
    control_change_required = Column(Boolean, default=False)
    training_change_required = Column(Boolean, default=False)

    impact_level = Column(String(50), default="MEDIUM")  # LOW, MEDIUM, HIGH, CRITICAL
    assessment_status = Column(String(50), default="AI_ASSESSED")  # NOT_STARTED, AI_ASSESSED, UNDER_REVIEW, APPROVED, REJECTED, SUPERSEDED

    ai_recommendation = Column(Text, nullable=True)
    human_decision = Column(Text, nullable=True)
    assessed_by = Column(String(255), default="AI_ASSESSOR")
    approved_by = Column(String(255), nullable=True)
    assessed_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    obligation = relationship("RegulatoryObligation", back_populates="impact_assessments")
    applicability_assessment = relationship("ApplicabilityAssessment", back_populates="impact_assessments")


class ComplianceGap(Base):
    """Formal compliance deficiency or control gap."""
    __tablename__ = "compliance_gaps"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    obligation_id = Column(String(64), ForeignKey("regulatory_obligations.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    control_id = Column(String(64), ForeignKey("controls.id", ondelete="SET NULL"), nullable=True)
    document_id = Column(String(64), ForeignKey("internal_documents.id", ondelete="SET NULL"), nullable=True)
    
    gap_type = Column(String(50), default="MISSING_CONTROL")  # MISSING_CONTROL, WEAK_CONTROL, POLICY_GAP, PROCEDURE_GAP, SYSTEM_GAP, PROCESS_GAP, TRAINING_GAP, EVIDENCE_GAP
    description = Column(Text, nullable=False)
    severity = Column(String(50), default="HIGH")  # LOW, MEDIUM, HIGH, CRITICAL
    status = Column(String(50), default="OPEN")  # OPEN, IN_REMEDIATION, REMEDIATED, RISK_ACCEPTED, CLOSED
    
    discovered_by = Column(String(255), default="AI_ASSESSOR")
    discovered_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    obligation = relationship("RegulatoryObligation", back_populates="gaps")
    risk_assessment = relationship("RiskAssessment", back_populates="gap", uselist=False, cascade="all, delete-orphan")
    remediations = relationship("RemediationAction", back_populates="gap", cascade="all, delete-orphan")
    exceptions = relationship("ComplianceException", back_populates="gap", cascade="all, delete-orphan")


class RiskAssessment(Base):
    """Explainable, deterministic risk scoring matrix for compliance gaps."""
    __tablename__ = "risk_assessments"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    gap_id = Column(String(64), ForeignKey("compliance_gaps.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    
    regulatory_severity = Column(String(50), default="HIGH")  # LOW, MEDIUM, HIGH, CRITICAL
    customer_impact = Column(String(50), default="MEDIUM")
    financial_impact = Column(String(50), default="HIGH")
    operational_impact = Column(String(50), default="MEDIUM")
    likelihood = Column(String(50), default="MEDIUM")
    
    inherent_risk = Column(String(50), default="HIGH")
    control_effectiveness = Column(String(50), default="WEAK")
    residual_risk = Column(String(50), default="HIGH")
    materiality = Column(String(50), default="HIGH")  # LOW, MEDIUM, HIGH, CRITICAL
    
    formula_version = Column(String(20), default="v1.0")
    calculation_inputs = Column(JSON, default=dict)
    rationale = Column(Text, nullable=False)
    assessed_by = Column(String(255), default="DETERMINISTIC_RISK_ENGINE")
    approved_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    gap = relationship("ComplianceGap", back_populates="risk_assessment")


# =========================================================================
# LAYER 6: REMEDIATION, EXCEPTIONS & TESTING
# =========================================================================

class RemediationAction(Base):
    """Actionable, time-bound remediation item owned by operational personnel."""
    __tablename__ = "remediation_actions"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    gap_id = Column(String(64), ForeignKey("compliance_gaps.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    action_type = Column(String(50), default="POLICY_REVISION")  # POLICY_REVISION, PROCEDURE_UPDATE, CONTROL_DEPLOYMENT, SYSTEM_CONFIG, TRAINING
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=False)
    
    owner_id = Column(String(255), nullable=True)
    accountable_id = Column(String(255), nullable=True)
    due_date = Column(DateTime, nullable=True)
    priority = Column(String(50), default="HIGH")  # LOW, MEDIUM, HIGH, URGENT
    dependency_ids = Column(JSON, default=list)
    
    status = Column(String(50), default="OPEN")  # OPEN, ASSIGNED, IN_PROGRESS, BLOCKED, IMPLEMENTED, PENDING_TEST, FAILED_TEST, REOPENED, VALIDATED, CLOSED
    target_document_id = Column(String(64), nullable=True)
    target_system_id = Column(String(100), nullable=True)
    target_control_id = Column(String(64), nullable=True)
    
    implementation_notes = Column(Text, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    validated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    gap = relationship("ComplianceGap", back_populates="remediations")
    evidences = relationship("ComplianceEvidence", back_populates="remediation")


class ComplianceException(Base):
    """Formal time-bound risk acceptance or regulatory exemption approval."""
    __tablename__ = "compliance_exceptions"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    gap_id = Column(String(64), ForeignKey("compliance_gaps.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    compensating_control = Column(Text, nullable=False)
    residual_risk = Column(String(50), default="MEDIUM")
    owner_id = Column(String(255), nullable=False)
    approver_id = Column(String(255), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    expiry_date = Column(DateTime, nullable=False)
    review_date = Column(DateTime, nullable=False)
    status = Column(String(50), default="REQUESTED")  # REQUESTED, UNDER_REVIEW, APPROVED, REJECTED, EXPIRED, REVOKED
    created_at = Column(DateTime, default=datetime.utcnow)

    gap = relationship("ComplianceGap", back_populates="exceptions")


class ControlTest(Base):
    """Test execution validating the operational effectiveness of a control."""
    __tablename__ = "control_tests"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    control_id = Column(String(64), ForeignKey("controls.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    test_type = Column(String(50), default="OPERATIONAL_EFFECTIVENESS")  # DESIGN_ADEQUACY, OPERATIONAL_EFFECTIVENESS, AUTOMATED_CHECK
    test_procedure = Column(Text, nullable=False)
    testing_period = Column(String(100), default="Q1-2026")
    tester_id = Column(String(255), nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    result = Column(String(50), default="NOT_TESTED")  # PASS, PARTIAL, FAIL, NOT_TESTED
    findings = Column(Text, nullable=True)
    evidence_ids = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    control = relationship("Control", back_populates="control_tests")
    evidences = relationship("ComplianceEvidence", back_populates="control_test")


class ComplianceEvidence(Base):
    """Immutable evidence artifact proving control execution or remediation completion."""
    __tablename__ = "compliance_evidences"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(64), nullable=False, index=True)
    evidence_type = Column(String(50), default="SYSTEM_LOG")  # SYSTEM_LOG, AUDIT_REPORT, SCREENSHOT, POLICY_DOC, TRAINING_RECORD
    source = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)  # Immutable SHA-256
    storage_reference = Column(String(1024), nullable=False)  # s3://compliance-platform/evidence/...
    
    control_id = Column(String(64), ForeignKey("controls.id", ondelete="SET NULL"), nullable=True)
    remediation_id = Column(String(64), ForeignKey("remediation_actions.id", ondelete="SET NULL"), nullable=True)
    test_id = Column(String(64), ForeignKey("control_tests.id", ondelete="SET NULL"), nullable=True)
    
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)
    collected_by = Column(String(255), nullable=True)
    collected_at = Column(DateTime, default=datetime.utcnow)
    verified_by = Column(String(255), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    retention_date = Column(DateTime, nullable=True)
    verification_status = Column(String(50), default="VERIFIED")  # PENDING, VERIFIED, REJECTED
    created_at = Column(DateTime, default=datetime.utcnow)

    remediation = relationship("RemediationAction", back_populates="evidences")
    control_test = relationship("ControlTest", back_populates="evidences")


# =========================================================================
# LAYER 7: CLAIM LINEAGE, ASSESSMENTS & AUDIT RECONSTRUCTION
# =========================================================================

class ClaimLineage(Base):
    """Explainability by Construction: sentence-level trace to source coordinates."""
    __tablename__ = "claim_lineages"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    policy_change_id = Column(String(64), ForeignKey("policy_changes.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_version_id = Column(String(64), ForeignKey("requirement_versions.id"), nullable=True, index=True)
    obligation_id = Column(String(64), ForeignKey("regulatory_obligations.id"), nullable=True, index=True)
    source_section_id = Column(String(64), ForeignKey("regulatory_sections.id"), nullable=True)
    document_version_id = Column(String(64), ForeignKey("document_versions.id"), nullable=False)
    
    claim_text = Column(Text, nullable=False)
    source_verbatim_quote = Column(Text, nullable=False)
    page_number = Column(Integer, default=1)
    paragraph_index = Column(Integer, default=0)
    verification_status = Column(String(50), default="VERIFIED")
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
    status = Column(String(50), default="QUEUED")
    confidence_score = Column(Float, default=0.0)
    overall_summary = Column(Text, nullable=True)
    total_requirements = Column(Integer, default=0)
    total_obligations = Column(Integer, default=0)
    gaps_detected = Column(Integer, default=0)
    remediations_created = Column(Integer, default=0)
    mode = Column(String(50), default="standard")
    
    # Deterministic Verification Scorecard
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
    
    status = Column(String(50), default="PENDING_REVIEW")
    reviewed_by = Column(String(255), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    # Maker-Checker Dual Control Governance
    maker_id = Column(String(255), nullable=True)
    maker_submitted_at = Column(DateTime, nullable=True)
    maker_rationale = Column(Text, nullable=True)
    checker_id = Column(String(255), nullable=True)
    checker_reviewed_at = Column(DateTime, nullable=True)
    checker_comments = Column(Text, nullable=True)
    maker_checker_status = Column(String(50), default="DRAFT")
    digital_signature_hash = Column(String(64), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    assessment = relationship("ComplianceAssessment", back_populates="changes")
    claim_lineages = relationship("ClaimLineage", back_populates="policy_change", cascade="all, delete-orphan")


class ComplianceRunSnapshot(Base):
    """Immutable audit reconstruction snapshot."""
    __tablename__ = "compliance_run_snapshots"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    run_id = Column(String(100), unique=True, nullable=False, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    assessment_id = Column(String(64), ForeignKey("compliance_assessments.id", ondelete="CASCADE"), nullable=False)
    
    # Extended Provenance & Version Matrix
    regulation_version_id = Column(String(64), nullable=False)
    document_sha256 = Column(String(64), nullable=False)
    source_version = Column(String(50), default="1.0.0")
    model_version = Column(String(100), nullable=False)
    prompt_version = Column(String(50), nullable=False)
    workflow_version = Column(String(50), nullable=False)
    
    obligation_ids = Column(JSON, default=list)
    applicability_assessment_ids = Column(JSON, default=list)
    control_ids = Column(JSON, default=list)
    gap_ids = Column(JSON, default=list)
    remediation_ids = Column(JSON, default=list)
    evidence_ids = Column(JSON, default=list)
    
    input_state = Column(JSON, default=dict)
    retrieved_chunks = Column(JSON, default=list)
    graph_query_snapshot = Column(JSON, default=list)
    intermediate_steps = Column(JSON, default=dict)
    verification_scorecard = Column(JSON, default=dict)
    final_output = Column(JSON, default=dict)
    human_decisions = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="compliance_runs")


class ReviewerFeedbackRecord(Base):
    __tablename__ = "reviewer_feedback_records"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(64), nullable=False, index=True)
    run_id = Column(String(100), nullable=False, index=True)
    policy_change_id = Column(String(64), nullable=False, index=True)
    decision = Column(String(50), nullable=False)
    rejection_reason_category = Column(String(100), nullable=True)
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
