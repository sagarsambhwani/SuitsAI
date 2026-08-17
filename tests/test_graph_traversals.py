import pytest
from services.graph.client import get_graph_client
from services.graph.ontology import GraphNode, GraphRelationship


def test_graph_impact_traversal():
    client = get_graph_client()
    client._in_memory.clear()

    # 1. Setup Graph: Regulation -> Requirement -> Policy -> Clause & Control
    reg = GraphNode(
        id="REG-RBI-04",
        label="Regulation",
        properties={"code": "RBI/2026-27/04", "title": "Digital Lending Circular"},
    )
    req = GraphNode(
        id="REQ-04-01",
        label="Requirement",
        properties={"req_code": "REQ-04-01", "obligation_text": "Rotate API keys every 90 days."},
    )
    policy = GraphNode(
        id="POL-INF-001",
        label="Policy",
        properties={"tenant_id": "BANK-001", "policy_code": "POL-INF-001", "title": "InfoSec Policy"},
    )
    clause = GraphNode(
        id="CLAUSE-4.2",
        label="PolicyClause",
        properties={"tenant_id": "BANK-001", "clause_number": "Clause 4.2"},
    )
    control = GraphNode(
        id="CTL-SEC-09",
        label="Control",
        properties={"tenant_id": "BANK-001", "control_code": "CTL-SEC-09"},
    )

    client.sync_node(reg)
    client.sync_node(req)
    client.sync_node(policy)
    client.sync_node(clause)
    client.sync_node(control)

    # Relationships
    client.sync_relationship(GraphRelationship(source_id=reg.id, target_id=req.id, rel_type="CONTAINS"))
    client.sync_relationship(GraphRelationship(source_id=req.id, target_id=policy.id, rel_type="AFFECTS"))
    client.sync_relationship(GraphRelationship(source_id=policy.id, target_id=clause.id, rel_type="CONTAINS"))
    client.sync_relationship(GraphRelationship(source_id=req.id, target_id=control.id, rel_type="IMPLEMENTED_BY"))

    # 2. Traverse Impact Path for Tenant BANK-001
    paths = client.get_impact_paths(regulation_id=reg.id, tenant_id="BANK-001")

    assert len(paths) >= 1
    path = paths[0]
    assert path.regulation_code == "RBI/2026-27/04"
    assert path.requirement_code == "REQ-04-01"
    assert path.policy_code == "POL-INF-001"
    assert path.control_code == "CTL-SEC-09"
