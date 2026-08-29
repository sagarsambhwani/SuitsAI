from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class ChangeImpactType(str, Enum):
    NO_CHANGE = "NO_CHANGE"
    POLICY = "POLICY"
    PROCEDURE = "PROCEDURE"
    CONTROL = "CONTROL"
    SYSTEM = "SYSTEM"
    TRAINING = "TRAINING"
    MULTIPLE = "MULTIPLE"


class ComplianceState(BaseModel):
    # Tenant & Execution Context
    tenant_id: str
    workflow_run_id: str
    regulatory_change_id: str
    regulation_code: str
    jurisdiction: str = "GLOBAL"
    document_version_id: Optional[str] = None
    document_sha256: str = ""
    mode: str = "standard"  # standard (Production HITL), shadow (Historical Backtesting / Benchmark)

    # Layer 1: Source Documents & Provisions
    source_documents: List[Dict[str, Any]] = Field(default_factory=list)
    raw_document_text: str = ""
    extracted_provisions: List[Dict[str, Any]] = Field(default_factory=list)

    # Layer 2: Deontic Obligations & Applicability
    extracted_obligations: List[Dict[str, Any]] = Field(default_factory=list)
    extracted_requirements: List[Dict[str, Any]] = Field(default_factory=list)  # Compatibility
    applicability_assessments: List[Dict[str, Any]] = Field(default_factory=list)

    # Layer 3: Knowledge Graph Topology & Multi-Hop Impact
    affected_policies: List[Dict[str, Any]] = Field(default_factory=list)
    affected_controls: List[Dict[str, Any]] = Field(default_factory=list)
    affected_documents: List[Dict[str, Any]] = Field(default_factory=list)
    affected_systems: List[Any] = Field(default_factory=list)
    affected_processes: List[Any] = Field(default_factory=list)
    graph_impact_paths: List[Dict[str, Any]] = Field(default_factory=list)

    # Layer 4: Impact Assessment & Rich Change Classification
    impact_assessment: Dict[str, Any] = Field(default_factory=dict)
    primary_change_impact: ChangeImpactType = ChangeImpactType.POLICY
    impact_rationale: str = ""
    policy_change_required: bool = False
    procedure_change_required: bool = False
    system_change_required: bool = False
    control_change_required: bool = False
    training_change_required: bool = False

    # Layer 5: Gaps, Remediations & Exceptions
    compliance_gaps: List[Dict[str, Any]] = Field(default_factory=list)
    identified_gaps: List[Dict[str, Any]] = Field(default_factory=list)  # Compatibility
    risk_assessments: List[Dict[str, Any]] = Field(default_factory=list)
    remediation_plans: List[Dict[str, Any]] = Field(default_factory=list)
    compliance_exceptions: List[Dict[str, Any]] = Field(default_factory=list)

    # Layer 6: Policy Redlines (Conditional) & Citations
    proposed_changes: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    claim_lineages: List[Dict[str, Any]] = Field(default_factory=list)

    # Layer 7: Deterministic Verification Scorecard
    verification_scorecard: Dict[str, Any] = Field(default_factory=dict)
    all_gates_passed: bool = False
    confidence_score: float = 0.0
    gate_failure_reasons: List[str] = Field(default_factory=list)

    # Layer 8: Governance & Evaluation Output
    human_review_required: bool = True
    approval_status: str = "PENDING_REVIEW"  # PENDING_REVIEW, APPROVED, REJECTED, GATES_FAILED, SHADOW_RECORDED
    approved_by: Optional[str] = None
    reviewer_rationale: Optional[str] = None
    published_version_id: Optional[str] = None
    shadow_snapshot_id: Optional[str] = None
    audit_events_recorded: List[str] = Field(default_factory=list)
