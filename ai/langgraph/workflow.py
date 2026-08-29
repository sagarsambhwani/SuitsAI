import logging
from typing import Any, Literal
from langgraph.graph import StateGraph, START, END

from ai.langgraph.state import ComplianceState
from ai.langgraph.nodes import (
    node_retrieve_regulatory_change,
    node_extract_provisions_and_obligations,
    node_applicability_analysis,
    node_graph_impact_analysis,
    node_impact_and_risk_assessment,
    node_identify_policy_gaps,
    node_generate_remediation_plan,
    node_generate_proposed_changes,
    node_verify_compliance,
    node_human_approval_gateway,
    node_record_shadow_audit_snapshot,
    node_publish_policy_version,
)

logger = logging.getLogger(__name__)


# =========================================================================
# CONDITIONAL ROUTING FUNCTIONS (Dynamic Edge Decisions)
# =========================================================================

def route_after_remediation(state: ComplianceState) -> Literal["generate_proposed_changes", "verify_compliance"]:
    """
    Conditional Routing Gate 1 (Impact-Driven Redlines):
    - If policy amendments are required (policy_change_required == True) -> Route to Sonnet Policy Redline Generator.
    - If only procedure / system / control / training changes are required -> Skip drafting directly to Verification.
    """
    if state.policy_change_required:
        logger.info(f"[Routing Gate 1] Policy amendment required ({state.primary_change_impact}) -> Routing to 'generate_proposed_changes'")
        return "generate_proposed_changes"
    
    logger.info(f"[Routing Gate 1] No policy amendment required ({state.primary_change_impact}: {state.impact_rationale}) -> Skipping to 'verify_compliance'")
    return "verify_compliance"


def route_after_verification(state: ComplianceState) -> Literal["human_approval_gateway", "record_shadow_audit_snapshot"]:
    """
    Conditional Routing Gate 2 (Production HITL vs Shadow Backtesting):
    - Standard / Production: Always routes to human approval gateway (Maker-Checker 4-Eyes Principle).
      * AI recommends; humans decide. Policy is ONLY published post-human signoff via Maker-Checker router.
    - Shadow Execution Mode: Routes to immutable benchmark snapshot recorder (Historical Backtesting).
      * Compares AI predicted obligations/gaps/redlines against ground-truth outcomes without touching production state.
    """
    if state.mode == "shadow":
        logger.info("[Routing Gate 2] Shadow Execution Mode -> Routing to 'record_shadow_audit_snapshot' (Evaluation / Backtesting)")
        return "record_shadow_audit_snapshot"
    
    logger.info("[Routing Gate 2] Production Mode -> Routing to 'human_approval_gateway' (4-Eyes Maker-Checker)")
    return "human_approval_gateway"


def route_approval_decision(state: ComplianceState) -> Literal["publish_policy_version", "__end__"]:
    """
    Conditional Routing Gate 3 (Maker-Checker Authorization Gate):
    - If authorized and approved by Checker (approval_status == 'APPROVED') -> Executes 'publish_policy_version'.
    - If awaiting review (PENDING_REVIEW) or rejected -> Suspends/persists state without publishing.
    """
    if state.approval_status == "APPROVED":
        logger.info("[Routing Gate 3] Approved by Checker -> Routing to 'publish_policy_version'")
        return "publish_policy_version"
    
    logger.info(f"[Routing Gate 3] Status is '{state.approval_status}' -> Workflow checkpointed for Maker-Checker review")
    return "__end__"


# =========================================================================
# STATEGRAPH COMPILATION
# =========================================================================

def build_compliance_workflow() -> Any:
    """
    Builds and compiles the expanded 11-stage Compliance StateGraph.
    
    Architecture:
    [START] -> retrieve -> extract -> applicability -> graph_impact -> impact_and_risk -> gaps -> remediation
                                                                                                        │
                                                   ┌────────────────────────────────────────────────────┴──────────────────────────┐
                                                   │ [policy_change_required == True]                              [policy_change_required == False]
                                                   ▼                                                                               │
                                       generate_proposed_changes                                                                   │
                                                   │                                                                               │
                                                   └───────────────────────────────┬───────────────────────────────────────────────┘
                                                                                   ▼
                                                                           verify_compliance
                                                                                   │
                                                   ┌───────────────────────────────┴───────────────────────────────┐
                                                   │ [mode == "standard" (Production)]                             │ [mode == "shadow" (Offline Eval)]
                                                   ▼                                                               ▼
                                        human_approval_gateway                                          record_shadow_audit_snapshot
                                                   │                                                               │
                                  ┌────────────────┴────────────────┐                                              │
                                  │ [APPROVED]                      │ [PENDING / REJECTED]                         │
                                  ▼                                 ▼                                              ▼
                        publish_policy_version                    [END]                                          [END]
                                  │
                                  ▼
                                [END]
    """
    graph = StateGraph(ComplianceState)

    # 1. Register All Compute Nodes
    graph.add_node("retrieve_regulatory_change", node_retrieve_regulatory_change)
    graph.add_node("extract_provisions_and_obligations", node_extract_provisions_and_obligations)
    graph.add_node("applicability_analysis", node_applicability_analysis)
    graph.add_node("graph_impact_analysis", node_graph_impact_analysis)
    graph.add_node("impact_and_risk_assessment", node_impact_and_risk_assessment)
    graph.add_node("identify_policy_gaps", node_identify_policy_gaps)
    graph.add_node("generate_remediation_plan", node_generate_remediation_plan)
    graph.add_node("generate_proposed_changes", node_generate_proposed_changes)
    graph.add_node("verify_compliance", node_verify_compliance)
    graph.add_node("human_approval_gateway", node_human_approval_gateway)
    graph.add_node("record_shadow_audit_snapshot", node_record_shadow_audit_snapshot)
    graph.add_node("publish_policy_version", node_publish_policy_version)

    # 2. Linear Stage Pipeline
    graph.add_edge(START, "retrieve_regulatory_change")
    graph.add_edge("retrieve_regulatory_change", "extract_provisions_and_obligations")
    graph.add_edge("extract_provisions_and_obligations", "applicability_analysis")
    graph.add_edge("applicability_analysis", "graph_impact_analysis")
    graph.add_edge("graph_impact_analysis", "impact_and_risk_assessment")
    graph.add_edge("impact_and_risk_assessment", "identify_policy_gaps")
    graph.add_edge("identify_policy_gaps", "generate_remediation_plan")

    # 3. Dynamic Conditional Routing 1: Policy Redlines vs Direct Verification
    graph.add_conditional_edges(
        "generate_remediation_plan",
        route_after_remediation,
        {
            "generate_proposed_changes": "generate_proposed_changes",
            "verify_compliance": "verify_compliance",
        },
    )

    # 4. Connect Drafting back to Verification
    graph.add_edge("generate_proposed_changes", "verify_compliance")

    # 5. Dynamic Conditional Routing 2: Production HITL vs Shadow Evaluation Snapshot
    graph.add_conditional_edges(
        "verify_compliance",
        route_after_verification,
        {
            "human_approval_gateway": "human_approval_gateway",
            "record_shadow_audit_snapshot": "record_shadow_audit_snapshot",
        },
    )

    # 6. Dynamic Conditional Routing 3: Post-Human Review Publishing Gate
    graph.add_conditional_edges(
        "human_approval_gateway",
        route_approval_decision,
        {
            "publish_policy_version": "publish_policy_version",
            "__end__": END,
        },
    )

    # 7. Terminal Endpoints
    graph.add_edge("publish_policy_version", END)
    graph.add_edge("record_shadow_audit_snapshot", END)

    return graph.compile()


_compiled_workflow = None


def get_compliance_workflow():
    global _compiled_workflow
    if _compiled_workflow is None:
        _compiled_workflow = build_compliance_workflow()
    return _compiled_workflow
