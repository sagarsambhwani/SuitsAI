import pytest
from datetime import datetime, timedelta
from services.compliance.verification import IndependentComplianceValidator
from services.compliance.rules_engine import ComplianceRulesEngine
from services.ingestion.parser import ExtractedRequirement


def test_citation_validator_positive():
    source_text = """
    Section 4.1 Cryptographic Key Lifecycle:
    Regulated entities shall ensure cryptographic keys and API tokens are rotated at intervals not exceeding 90 days.
    """
    valid_citations = [
        {
            "doc": "RBI/2026/04",
            "section": "Section 4.1",
            "quote": "cryptographic keys and API tokens are rotated at intervals not exceeding 90 days",
        }
    ]

    results = IndependentComplianceValidator.verify_citations(valid_citations, source_text)
    assert len(results) == 1
    assert results[0].is_valid is True
    assert results[0].similarity_score == 1.0


def test_citation_validator_hallucination_detection():
    source_text = """
    Section 4.1 Cryptographic Key Lifecycle:
    Regulated entities shall ensure cryptographic keys and API tokens are rotated at intervals not exceeding 90 days.
    """
    hallucinated_citations = [
        {
            "doc": "RBI/2026/04",
            "section": "Section 4.1",
            "quote": "All financial institutions must transfer customer balances to decentralized smart contracts.",
        }
    ]

    results = IndependentComplianceValidator.verify_citations(hallucinated_citations, source_text)
    assert "Hallucinated" in results[0].error_message


def test_requirement_coverage_verification():
    reqs = [
        ExtractedRequirement(
            req_code="REQ-01",
            section_number="1.0",
            obligation_text="Maintain 90-day rotation.",
            obligation_type="MANDATORY",
        ),
        ExtractedRequirement(
            req_code="REQ-02",
            section_number="2.0",
            obligation_text="Automate revocation.",
            obligation_type="MANDATORY",
        ),
    ]

    # Full coverage
    full_cov = IndependentComplianceValidator.verify_requirement_coverage(reqs, ["REQ-01", "REQ-02"])
    assert full_cov.is_fully_covered is True
    assert full_cov.coverage_percentage == 100.0

    # Partial coverage
    partial_cov = IndependentComplianceValidator.verify_requirement_coverage(reqs, ["REQ-01"])
    assert partial_cov.is_fully_covered is False
    assert partial_cov.coverage_percentage == 50.0
    assert "REQ-02" in partial_cov.uncovered_requirements


def test_rules_engine_jurisdiction_and_temporal():
    now = datetime.utcnow()
    past_pub = now - timedelta(days=10)
    future_eff = now + timedelta(days=60)

    # Positive same jurisdiction
    res_in = ComplianceRulesEngine.evaluate(
        regulation_jurisdiction="IN",
        policy_jurisdiction="IN",
        publication_date=past_pub,
        effective_date=future_eff,
    )
    assert res_in.passed is True
    assert res_in.jurisdiction_match is True

    # Negative jurisdiction mismatch
    res_mismatch = ComplianceRulesEngine.evaluate(
        regulation_jurisdiction="US",
        policy_jurisdiction="IN",
        publication_date=past_pub,
        effective_date=future_eff,
    )
    assert res_mismatch.passed is False
    assert res_mismatch.jurisdiction_match is False
