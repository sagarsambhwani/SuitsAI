from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class ComplianceState(BaseModel):
    # Tenant & Execution Context
    tenant_id: str
    workflow_run_id: str
    regulatory_change_id: str
    regulation_code: str
    jurisdiction: str = "GLOBAL"
    document_version_id: Optional[str] = None
    document_sha256: str = ""
    mode: str = "standard"  # standard, shadow

    # Layer 1: Source Documents & Coordinates
    source_documents: List[Dict[str, Any]] = Field(default_factory=list)
    raw_document_text: str = ""

    # Layer 2: Structured Requirements (Conditions & Exceptions)
    extracted_requirements: List[Dict[str, Any]] = Field(default_factory=list)

    # Layer 3: Knowledge Graph Topology & Impact
    affected_policies: List[Dict[str, Any]] = Field(default_factory=list)
    affected_controls: List[Dict[str, Any]] = Field(default_factory=list)
    graph_impact_paths: List[Dict[str, Any]] = Field(default_factory=list)

    # Intermediate Structured Gap & Amendment Models
    identified_gaps: List[Dict[str, Any]] = Field(default_factory=list)
    proposed_changes: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    claim_lineages: List[Dict[str, Any]] = Field(default_factory=list)

    # Machine-Readable 8-Gate Scorecard
    verification_scorecard: Dict[str, Any] = Field(default_factory=dict)
    all_gates_passed: bool = False
    confidence_score: float = 0.0
    gate_failure_reasons: List[str] = Field(default_factory=list)

    # Human Review Gateway & Governance
    human_review_required: bool = True
    approval_status: str = "PENDING_REVIEW"  # PENDING_REVIEW, APPROVED, REJECTED, GATES_FAILED
    approved_by: Optional[str] = None
    reviewer_rationale: Optional[str] = None
    published_version_id: Optional[str] = None
    audit_events_recorded: List[str] = Field(default_factory=list)
