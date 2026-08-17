import logging
from typing import Any
from langgraph.graph import StateGraph, START, END

from ai.langgraph.state import ComplianceState
from ai.langgraph.nodes import (
    node_retrieve_regulatory_change,
    node_classify_and_extract_requirements,
    node_graph_impact_analysis,
    node_identify_policy_gaps,
    node_generate_proposed_changes,
    node_verify_compliance,
    node_human_approval_gateway,
    node_publish_and_audit,
)

logger = logging.getLogger(__name__)


def build_compliance_workflow() -> Any:
    """Builds and compiles the end-to-end Compliance StateGraph."""
    graph = StateGraph(ComplianceState)

    # Add Nodes
    graph.add_node("retrieve_regulatory_change", node_retrieve_regulatory_change)
    graph.add_node("classify_and_extract_requirements", node_classify_and_extract_requirements)
    graph.add_node("graph_impact_analysis", node_graph_impact_analysis)
    graph.add_node("identify_policy_gaps", node_identify_policy_gaps)
    graph.add_node("generate_proposed_changes", node_generate_proposed_changes)
    graph.add_node("verify_compliance", node_verify_compliance)
    graph.add_node("human_approval_gateway", node_human_approval_gateway)
    graph.add_node("publish_and_audit", node_publish_and_audit)

    # Define Linear & Conditional Flow
    graph.add_edge(START, "retrieve_regulatory_change")
    graph.add_edge("retrieve_regulatory_change", "classify_and_extract_requirements")
    graph.add_edge("classify_and_extract_requirements", "graph_impact_analysis")
    graph.add_edge("graph_impact_analysis", "identify_policy_gaps")
    graph.add_edge("identify_policy_gaps", "generate_proposed_changes")
    graph.add_edge("generate_proposed_changes", "verify_compliance")
    graph.add_edge("verify_compliance", "human_approval_gateway")
    graph.add_edge("human_approval_gateway", END)

    return graph.compile()


_compiled_workflow = None


def get_compliance_workflow():
    global _compiled_workflow
    if _compiled_workflow is None:
        _compiled_workflow = build_compliance_workflow()
    return _compiled_workflow
