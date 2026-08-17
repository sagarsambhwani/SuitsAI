import pytest
from ai.langgraph.state import ComplianceState
from ai.langgraph.workflow import get_compliance_workflow


@pytest.mark.asyncio
async def test_full_compliance_state_graph():
    workflow = get_compliance_workflow()

    initial_state = ComplianceState(
        tenant_id="BANK-TEST-001",
        workflow_run_id="RUN-TEST-01",
        regulatory_change_id="REG-TEST-01",
        regulation_code="RBI/2026/04",
        jurisdiction="IN",
        raw_document_text="""
        Section 4.1 Key Lifecycle:
        Regulated entities shall ensure cryptographic keys and API tokens are rotated at intervals not exceeding 90 days.
        Automated revocation and audit logging shall trigger immediately upon credential exposure.
        """,
    )

    final_state_dict = await workflow.ainvoke(initial_state)
    final_state = ComplianceState(**final_state_dict)

    assert len(final_state.extracted_requirements) >= 1
    assert len(final_state.identified_gaps) >= 1
    assert len(final_state.proposed_changes) >= 1
    assert final_state.confidence_score >= 0.8
    assert final_state.approval_status in ("PENDING_REVIEW", "APPROVED", "GATES_FAILED")
