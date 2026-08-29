from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    label: str  # RegulatorySource, RegulatoryProvision, RegulatoryObligation, Control, BusinessProcess, System, Vendor, InternalDocument, ComplianceGap, RemediationAction, ControlTest, ComplianceEvidence
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphRelationship(BaseModel):
    source_id: str
    target_id: str
    rel_type: str  # CONTAINS, HAS_APPLICABILITY, APPLIES_TO, REQUIRES, IMPACTS, SUPPORTED_BY, IMPLEMENTS, OPERATES_IN, RELATES_TO, AFFECTS, REMEDIATES, PRODUCES, TESTS, GENERATES, ASSESSES, SUPERSEDES
    
    # First-Class Provenance Metadata on every Edge
    source_evidence_id: Optional[str] = None  # DocumentVersion or Section ID
    extraction_run_id: Optional[str] = None  # RUN-ID that created this relationship
    method: str = "LLM"  # LLM, DETERMINISTIC_RULE, MANUAL_OVERRIDE
    confidence: float = 1.0
    reviewer_status: str = "VERIFIED"  # VERIFIED, DERIVED_UNVERIFIED
    properties: Dict[str, Any] = Field(default_factory=dict)


class RegulatoryImpactPath(BaseModel):
    regulation_id: str
    regulation_code: str
    requirement_id: str
    requirement_code: str
    obligation_text: str
    policy_id: str
    policy_code: str
    policy_title: str
    clause_id: Optional[str] = None
    clause_number: Optional[str] = None
    control_id: Optional[str] = None
    control_code: Optional[str] = None
    business_unit: Optional[str] = None
    
    # Extended Multi-Hop Impact Metadata
    provision_id: Optional[str] = None
    obligation_id: Optional[str] = None
    obligation_type: Optional[str] = "MANDATE"
    impacted_processes: List[str] = Field(default_factory=list)
    impacted_systems: List[str] = Field(default_factory=list)
    impacted_documents: List[str] = Field(default_factory=list)
    applicability_status: str = "APPLICABLE"
    
    # Traceability & Provenance
    source_evidence_id: Optional[str] = None
    provenance_status: str = "VERIFIED"
    path_nodes: List[str] = Field(default_factory=list)
