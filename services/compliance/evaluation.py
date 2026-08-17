import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from services.compliance.verification import IndependentComplianceValidator, VerificationScorecard
from services.ingestion.parser import DocumentParser

logger = logging.getLogger(__name__)


class BenchmarkTestCase(BaseModel):
    test_id: str
    category: str  # EXCEPTION_RETENTION, INVERSION_DETECTION, CITATION_VERIFICATION, JURISDICTION_ISOLATION, TEMPORAL_VALIDITY
    description: str
    regulatory_text: str
    proposed_amendment: Dict[str, Any]
    expected_gate_to_fail: Optional[str] = None  # None if expected to pass
    expected_overall_pass: bool = True


class BenchmarkEvaluationReport(BaseModel):
    total_test_cases: int
    passed_test_cases: int
    faithfulness_score: float  # Zero hallucinations & verbatim accuracy (0.0 to 1.0)
    citation_precision: float
    exception_retention_rate: float
    directional_consistency: float
    overall_benchmark_passed: bool
    details: List[Dict[str, Any]] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)


GOLDEN_BENCHMARK_DATASET: List[BenchmarkTestCase] = [
    # 1. Statutory Exception Retention (Should PASS all 8 gates)
    BenchmarkTestCase(
        test_id="BENCH-01-EXCEPTION-PRESERVATION",
        category="EXCEPTION_RETENTION",
        description="Verifies statutory exception is preserved in redline.",
        regulatory_text="Section 5.1: Regulated entities must maintain video KYC records for 10 years, except when customer is central government entity.",
        proposed_amendment={
            "clause_number": "Clause 5.1.1",
            "proposed_text": "Video KYC records shall be retained for 10 years, except when customer is central government entity.",
            "justification": "Direct compliance alignment with Section 5.1 (REQ-BENCH-REG-1.0-01).",
            "citations": [{"quote": "maintain video KYC records for 10 years, except when customer is central government entity", "page": 1, "doc": "REQ-BENCH-REG-1.0-01"}],
        },
        expected_gate_to_fail=None,
        expected_overall_pass=True,
    ),
    # 2. Adversarial Exception Dropping Attack (Should Fail Gate 6: Exception Preservation)
    BenchmarkTestCase(
        test_id="BENCH-02-EXCEPTION-DROPPED-ADVERSARIAL",
        category="EXCEPTION_RETENTION",
        description="Detects when LLM omits statutory exception in proposed text.",
        regulatory_text="Section 5.1: Regulated entities must maintain video KYC records for 10 years, except when customer is central government entity.",
        proposed_amendment={
            "clause_number": "Clause 5.1.1",
            "proposed_text": "All retail video KYC archives shall strictly be retained for 10 years across every branch uniformly without exemptions.",
            "justification": "Direct compliance alignment with Section 5.1 (REQ-BENCH-REG-1.0-01).",
            "citations": [{"quote": "maintain video KYC records for 10 years", "page": 1, "doc": "REQ-BENCH-REG-1.0-01"}],
        },
        expected_gate_to_fail="exception_preservation_gate",
        expected_overall_pass=False,
    ),
    # 3. Obligation Inversion Attack (Should Fail Gate 8: Contradiction / Inversion)
    BenchmarkTestCase(
        test_id="BENCH-03-INVERSION-ATTACK",
        category="INVERSION_DETECTION",
        description="Detects when LLM weakens mandatory obligation 'shall' into 'optional'.",
        regulatory_text="Section 4.1: Regulated entities shall ensure cryptographic keys and API tokens are rotated at intervals not exceeding 90 days.",
        proposed_amendment={
            "clause_number": "Clause 4.1.1",
            "proposed_text": "Key rotation is optional for non-critical systems based on department discretion.",
            "justification": "Discretionary interpretation for REQ-BENCH-REG-1.0-01.",
            "citations": [{"quote": "cryptographic keys and API tokens are rotated at intervals not exceeding 90 days", "page": 1, "doc": "REQ-BENCH-REG-1.0-01"}],
        },
        expected_gate_to_fail="contradiction_gate",
        expected_overall_pass=False,
    ),
    # 4. Hallucinated Quote Attack (Should Fail Gate 7: Citation Evidence)
    BenchmarkTestCase(
        test_id="BENCH-04-HALLUCINATED-CITATION",
        category="CITATION_VERIFICATION",
        description="Detects fabricated or drifted citation quotes.",
        regulatory_text="Section 2.1: Regulated entities must report cyber security incidents within 6 hours of discovery.",
        proposed_amendment={
            "clause_number": "Clause 2.1.1",
            "proposed_text": "Incidents must be reported within 6 hours.",
            "justification": "Incident reporting mandate for REQ-BENCH-REG-1.0-01.",
            "citations": [{"quote": "entities may take up to 72 hours for minor incident reporting", "page": 1, "doc": "REQ-BENCH-REG-1.0-01"}],
        },
        expected_gate_to_fail="citation_gate",
        expected_overall_pass=False,
    ),
    # 5. Cross-Jurisdiction Boundary Violation (Should Fail Gate 3: Jurisdiction Isolation)
    BenchmarkTestCase(
        test_id="BENCH-05-JURISDICTION-MISMATCH",
        category="JURISDICTION_ISOLATION",
        description="Rejects applying US OCC regulation to Indian domestic bank policy.",
        regulatory_text="Section 1.1: Federal chartered banks must maintain capital adequacy ratios exceeding 12%.",
        proposed_amendment={
            "clause_number": "Clause 1.1",
            "proposed_text": "Maintain capital adequacy ratios exceeding 12%.",
            "justification": "OCC Mandate for REQ-BENCH-REG-1.0-01.",
            "citations": [{"quote": "Federal chartered banks must maintain capital adequacy ratios exceeding 12%", "page": 1, "doc": "REQ-BENCH-REG-1.0-01"}],
        },
        expected_gate_to_fail="jurisdiction_gate",
        expected_overall_pass=False,
    ),
]


class GoldenComplianceEvaluator:
    """
    Automated Continuous Evaluation Pipeline for measuring faithfulness,
    citation precision, exception retention, and directional consistency.
    """

    @classmethod
    def evaluate_benchmark(
        cls,
        test_cases: Optional[List[BenchmarkTestCase]] = None,
    ) -> BenchmarkEvaluationReport:
        dataset = test_cases or GOLDEN_BENCHMARK_DATASET
        total = len(dataset)
        passed_count = 0
        details = []

        faithfulness_hits = 0
        citation_hits = 0
        exception_hits = 0
        consistency_hits = 0

        for tc in dataset:
            parsed = DocumentParser.parse_regulatory_text(tc.regulatory_text, default_code="BENCH-REG")
            
            reg_jurisdiction = "US" if "OCC" in tc.description or "CCAR" in tc.regulatory_text or "Federal" in tc.regulatory_text else "IN"
            policy_jurisdiction = "IN"

            citations = tc.proposed_amendment.get("citations", [])
            
            scorecard: VerificationScorecard = IndependentComplianceValidator.evaluate_all_gates(
                document_sha256="bench_sha_hash",
                expected_sha256="bench_sha_hash",
                raw_document_text=tc.regulatory_text,
                publication_date=datetime.utcnow(),
                effective_date=datetime.utcnow(),
                superseded_date=None,
                regulation_jurisdiction=reg_jurisdiction,
                policy_jurisdiction=policy_jurisdiction,
                regulation_applies_to=["Commercial Banks"],
                tenant_entity_type="Commercial Banks",
                all_requirements=[r.model_dump() for r in parsed.extracted_requirements],
                proposed_amendments=[tc.proposed_amendment],
                citations=citations,
            )

            # Evaluate Gate Expectation
            test_passed = False
            if tc.expected_overall_pass:
                test_passed = scorecard.overall_passed
            else:
                if tc.expected_gate_to_fail:
                    failed_gate = scorecard.gates.get(tc.expected_gate_to_fail)
                    test_passed = failed_gate is not None and not failed_gate.passed
                else:
                    test_passed = not scorecard.overall_passed

            if test_passed:
                passed_count += 1

            # Metric accounting
            if scorecard.gates.get("citation_gate", {}).passed:
                citation_hits += 1
            if scorecard.gates.get("exception_preservation_gate", {}).passed:
                exception_hits += 1
            if scorecard.gates.get("contradiction_gate", {}).passed:
                consistency_hits += 1
            if test_passed:
                faithfulness_hits += 1

            details.append({
                "test_id": tc.test_id,
                "category": tc.category,
                "passed": test_passed,
                "scorecard_summary": scorecard.summary,
                "confidence_score": scorecard.confidence_score,
            })

        faithfulness = round(passed_count / max(total, 1), 4)
        citation_p = round(citation_hits / max(total, 1), 4)
        exception_p = round(exception_hits / max(total, 1), 4)
        consistency_p = round(consistency_hits / max(total, 1), 4)

        return BenchmarkEvaluationReport(
            total_test_cases=total,
            passed_test_cases=passed_count,
            faithfulness_score=faithfulness,
            citation_precision=citation_p,
            exception_retention_rate=exception_p,
            directional_consistency=consistency_p,
            overall_benchmark_passed=(passed_count == total),
            details=details,
        )
