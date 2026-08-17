import logging
from typing import List, Dict, Any, Optional
from services.api.config import get_settings
from services.graph.ontology import GraphNode, GraphRelationship, RegulatoryImpactPath

logger = logging.getLogger(__name__)
settings = get_settings()


class InMemoryGraphStore:
    """In-memory Graph Engine with full provenance tracking and tenant scoping."""

    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        self.relationships: List[GraphRelationship] = []

    def clear(self):
        self.nodes.clear()
        self.relationships.clear()

    def add_node(self, node: GraphNode):
        self.nodes[node.id] = node

    def add_relationship(self, rel: GraphRelationship):
        self.relationships.append(rel)

    def find_impact_paths(self, regulation_id: str, tenant_id: str) -> List[RegulatoryImpactPath]:
        paths: List[RegulatoryImpactPath] = []
        reg_node = self.nodes.get(regulation_id)
        if not reg_node:
            return paths

        # Find requirements linked to this regulation
        req_ids = []
        for r in self.relationships:
            if r.source_id == regulation_id and r.rel_type in ("CONTAINS", "REQUIRES"):
                req_ids.append((r.target_id, r.source_evidence_id, r.reviewer_status))
            elif r.source_id == regulation_id and r.rel_type == "HAS_SECTION":
                # Find requirements under that section
                sec_id = r.target_id
                for sr in self.relationships:
                    if sr.source_id == sec_id and sr.rel_type in ("CONTAINS", "REQUIRES"):
                        req_ids.append((sr.target_id, sr.source_evidence_id or sec_id, sr.reviewer_status))

        for req_id, evidence_id, rev_status in set(req_ids):
            req_node = self.nodes.get(req_id)
            if not req_node:
                continue

            # Traverse to affected Policies (scoped by tenant_id)
            for rel in self.relationships:
                if rel.source_id == req_id and rel.rel_type == "AFFECTS":
                    policy_node = self.nodes.get(rel.target_id)
                    if policy_node and (
                        policy_node.properties.get("tenant_id") == tenant_id
                        or not policy_node.properties.get("tenant_id")
                    ):
                        clause_id = None
                        clause_num = None
                        control_id = None
                        control_code = None
                        bu_name = policy_node.properties.get("owner_department", "Compliance & Risk")

                        for c_rel in self.relationships:
                            if c_rel.source_id == policy_node.id and c_rel.rel_type == "CONTAINS":
                                clause_node = self.nodes.get(c_rel.target_id)
                                if clause_node:
                                    clause_id = clause_node.id
                                    clause_num = clause_node.properties.get("clause_number", "1.0")
                            elif c_rel.source_id == req_id and c_rel.rel_type == "IMPLEMENTED_BY":
                                ctl_node = self.nodes.get(c_rel.target_id)
                                if ctl_node:
                                    control_id = ctl_node.id
                                    control_code = ctl_node.properties.get("control_code")

                        paths.append(
                            RegulatoryImpactPath(
                                regulation_id=reg_node.id,
                                regulation_code=reg_node.properties.get("code", "REG"),
                                requirement_id=req_node.id,
                                requirement_code=req_node.properties.get("req_code", "REQ"),
                                obligation_text=req_node.properties.get("obligation_text", ""),
                                policy_id=policy_node.id,
                                policy_code=policy_node.properties.get("policy_code", "POL"),
                                policy_title=policy_node.properties.get("title", ""),
                                clause_id=clause_id,
                                clause_number=clause_num,
                                control_id=control_id,
                                control_code=control_code,
                                business_unit=bu_name,
                                source_evidence_id=evidence_id,
                                provenance_status=rev_status,
                                path_nodes=[
                                    reg_node.properties.get("code", "REG"),
                                    req_node.properties.get("req_code", "REQ"),
                                    policy_node.properties.get("policy_code", "POL"),
                                ],
                            )
                        )

        return paths


class Neo4jClient:
    """Client for executing Cypher queries with edge provenance and tenant scoping."""

    def __init__(self):
        self._driver = None
        self._in_memory = InMemoryGraphStore()
        self.mock_mode = settings.NEO4J_MOCK_MODE

    def connect(self):
        if not self.mock_mode:
            try:
                from neo4j import GraphDatabase
                self._driver = GraphDatabase.driver(
                    settings.NEO4J_URI,
                    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                )
                self._driver.verify_connectivity()
                logger.info("Connected successfully to Neo4j database")
            except Exception as e:
                logger.warning(f"Could not connect to Neo4j: {e}. Falling back to in-memory graph store.")
                self.mock_mode = True

    def close(self):
        if self._driver:
            self._driver.close()

    def sync_node(self, node: GraphNode):
        self._in_memory.add_node(node)
        if not self.mock_mode and self._driver:
            try:
                with self._driver.session(database=settings.NEO4J_DATABASE) as session:
                    props_cypher = ", ".join([f"n.{k} = ${k}" for k in node.properties.keys()])
                    query = f"MERGE (n:{node.label} {{id: $id}}) SET {props_cypher}"
                    params = {"id": node.id, **node.properties}
                    session.run(query, params)
            except Exception as e:
                logger.error(f"Error syncing node to Neo4j: {e}")

    def sync_relationship(self, rel: GraphRelationship):
        self._in_memory.add_relationship(rel)
        if not self.mock_mode and self._driver:
            try:
                with self._driver.session(database=settings.NEO4J_DATABASE) as session:
                    query = f"""
                    MATCH (a {{id: $source_id}}), (b {{id: $target_id}})
                    MERGE (a)-[r:{rel.rel_type}]->(b)
                    SET r += $props,
                        r.source_evidence_id = $source_evidence_id,
                        r.extraction_run_id = $extraction_run_id,
                        r.method = $method,
                        r.confidence = $confidence,
                        r.reviewer_status = $reviewer_status
                    """
                    session.run(
                        query,
                        source_id=rel.source_id,
                        target_id=rel.target_id,
                        props=rel.properties,
                        source_evidence_id=rel.source_evidence_id,
                        extraction_run_id=rel.extraction_run_id,
                        method=rel.method,
                        confidence=rel.confidence,
                        reviewer_status=rel.reviewer_status,
                    )
            except Exception as e:
                logger.error(f"Error syncing relationship with provenance to Neo4j: {e}")

    def get_impact_paths(self, regulation_id: str, tenant_id: str) -> List[RegulatoryImpactPath]:
        """Traverse the knowledge graph from a regulation to affected tenant policies and controls."""
        if not self.mock_mode and self._driver:
            try:
                with self._driver.session(database=settings.NEO4J_DATABASE) as session:
                    cypher = """
                    MATCH (reg:Regulation {id: $regulation_id})-[:HAS_SECTION*0..1]->(sec)-[:CONTAINS|REQUIRES*1..1]->(req:Requirement)
                    MATCH (req)-[r:AFFECTS]->(pol:Policy {tenant_id: $tenant_id})
                    OPTIONAL MATCH (pol)-[:CONTAINS]->(clause:PolicyClause)
                    OPTIONAL MATCH (req)-[:IMPLEMENTED_BY]->(ctl:Control {tenant_id: $tenant_id})
                    RETURN reg.id AS reg_id, reg.code AS reg_code,
                           req.id AS req_id, req.req_code AS req_code, req.obligation_text AS obligation_text,
                           pol.id AS pol_id, pol.policy_code AS pol_code, pol.title AS pol_title, pol.owner_department AS bu,
                           clause.id AS clause_id, clause.clause_number AS clause_num,
                           ctl.id AS ctl_id, ctl.control_code AS ctl_code,
                           r.source_evidence_id AS evidence_id, r.reviewer_status AS rev_status
                    """
                    result = session.run(cypher, regulation_id=regulation_id, tenant_id=tenant_id)
                    paths = []
                    for record in result:
                        paths.append(
                            RegulatoryImpactPath(
                                regulation_id=record["reg_id"],
                                regulation_code=record["reg_code"],
                                requirement_id=record["req_id"],
                                requirement_code=record["req_code"],
                                obligation_text=record["obligation_text"],
                                policy_id=record["pol_id"],
                                policy_code=record["pol_code"],
                                policy_title=record["pol_title"],
                                clause_id=record["clause_id"],
                                clause_number=record["clause_num"],
                                control_id=record["ctl_id"],
                                control_code=record["ctl_code"],
                                business_unit=record["bu"] or "Compliance",
                                source_evidence_id=record["evidence_id"],
                                provenance_status=record["rev_status"] or "VERIFIED",
                                path_nodes=[record["reg_code"], record["req_code"], record["pol_code"]],
                            )
                        )
                    if paths:
                        return paths
            except Exception as e:
                logger.error(f"Error querying Neo4j for impact paths: {e}. Using fallback in-memory.")

        return self._in_memory.find_impact_paths(regulation_id, tenant_id)


_graph_client = None


def get_graph_client() -> Neo4jClient:
    global _graph_client
    if _graph_client is None:
        _graph_client = Neo4jClient()
        _graph_client.connect()
    return _graph_client
