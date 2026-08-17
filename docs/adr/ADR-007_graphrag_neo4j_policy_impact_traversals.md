# ADR-007: GraphRAG with Neo4j Ontology for Cross-Policy Impact Paths

* **Status**: Accepted
* **Date**: 2026-08-17
* **Deciders**: Graph Architecture, Enterprise Engineering

---

## Context & Problem Statement
When a central bank issues an amendment to an AML circular or cyber resilience guideline, the amendment rarely affects a single standalone policy. It cascades across multiple bank policies, internal clauses, operational controls, and specific business units (e.g. Risk, IT Operations, Customer Onboarding). Text retrieval alone cannot reliably determine structural downstream impact.

## Decision
We implement a **Neo4j Knowledge Graph (GraphRAG)** linking:
$$\text{Regulation} \overset{\text{CONTAINS}}{\longrightarrow} \text{Requirement} \overset{\text{AFFECTS}}{\longrightarrow} \text{Policy} \overset{\text{CONTAINS}}{\longrightarrow} \text{PolicyClause} \overset{\text{GOVERNS}}{\longrightarrow} \text{Control} \overset{\text{OWNED\_BY}}{\longrightarrow} \text{BusinessUnit}$$

During Step 3 of the LangGraph reasoning pipeline (`node_graph_impact_analysis`), the orchestrator traverses Cypher graph paths to extract all impacted internal policies and controls with explicit provenance before prompting the gap analysis LLM.

## Consequences
### Positive
* Complete multi-hop structural visibility into which departments and controls must be amended.
* Eliminates blind spots where a circular impacts secondary policies that text similarity missed.
* Built-in standalone mock graph engine ensures local tests and CI/CD pass without a live Neo4j instance.

### Negative
* Requires keeping the graph ontology nodes and relationships synchronized with relational database events.
