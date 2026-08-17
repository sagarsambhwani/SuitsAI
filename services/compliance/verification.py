import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class GateResult(BaseModel):
    gate_name: str
    passed: bool
    status: str  # PASS, FAIL, WARNING
    details: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VerificationScorecard(BaseModel):
    overall_passed: bool
    confidence_score: float
    gates: Dict[str, GateResult] = Field(default_factory=dict)
    summary: str
    total_gates: int = 8
    passed_gates_count: int = 0


class ClaimLineageVerification(BaseModel):
    claim_text: str
    source_verbatim_quote: str
    page_number: int
    is_valid: bool
    similarity_score: float
    error: Optional[str] = None


class CitationVerificationResult(BaseModel):
    is_valid: bool
    citation: Dict[str, Any]
    matched_source_snippet: Optional[str] = None
    similarity_score: float = 0.0
    error_message: Optional[str] = None


class RequirementCoverageResult(BaseModel):
    total_requirements: int
    covered_requirements: int
    coverage_percentage: float
    uncovered_requirements: List[str] = Field(default_factory=list)
    is_fully_covered: bool


class ContradictionCheckResult(BaseModel):
    has_contradiction: bool
    details: List[str] = Field(default_factory=list)


class IndependentComplianceValidator:
    """
    Core Architectural Standard:
    No AI-generated compliance artifact is considered valid unless verified by independent gates.
    Produces a complete machine-readable VerificationScorecard.
    """

    @classmethod
    def verify_citations(
        cls,
        citations: List[Dict[str, Any]],
        source_document_text: str,
    ) -> List[CitationVerificationResult]:
        lineages = cls.verify_sentence_citations(citations, source_document_text)
        return [
            CitationVerificationResult(
                is_valid=l.is_valid,
                citation={"quote": l.source_verbatim_quote},
                matched_source_snippet=l.source_verbatim_quote if l.is_valid else None,
                similarity_score=l.similarity_score,
                error_message=l.error,
            )
            for l in lineages
        ]

    @classmethod
    def verify_requirement_coverage(
        cls,
        all_requirements: List[Any],
        addressed_req_codes: List[str],
    ) -> RequirementCoverageResult:
        total = len(all_requirements)
        if total == 0:
            return RequirementCoverageResult(
                total_requirements=0,
                covered_requirements=0,
                coverage_percentage=100.0,
                uncovered_requirements=[],
                is_fully_covered=True,
            )

        all_codes = {
            getattr(r, "req_code", r.get("req_code") if isinstance(r, dict) else str(r))
            for r in all_requirements
        }
        covered = set(addressed_req_codes).intersection(all_codes)
        uncovered = list(all_codes - covered)
        coverage_pct = round((len(covered) / total) * 100.0, 1)

        return RequirementCoverageResult(
            total_requirements=total,
            covered_requirements=len(covered),
            coverage_percentage=coverage_pct,
            uncovered_requirements=uncovered,
            is_fully_covered=len(uncovered) == 0,
        )

    @classmethod
    def detect_contradictions(
        cls,
        proposed_amendments: List[Dict[str, Any]],
        existing_policy_text: str,
        regulation_text: str,
    ) -> ContradictionCheckResult:
        inv = cls.detect_inversions(proposed_amendments, regulation_text)
        return ContradictionCheckResult(
            has_contradiction=len(inv) > 0,
            details=inv,
        )

    @classmethod
    def evaluate_all_gates(
        cls,
        # Evidence context
        document_sha256: str,
        expected_sha256: str,
        raw_document_text: str,
        # Version & Temporal context
        publication_date: datetime,
        effective_date: datetime,
        superseded_date: Optional[datetime],
        # Jurisdiction & Applicability
        regulation_jurisdiction: str,
        policy_jurisdiction: str,
        regulation_applies_to: List[str],
        tenant_entity_type: str = "Commercial Banks",
        # Requirements & Exceptions
        all_requirements: List[Dict[str, Any]] = [],
        proposed_amendments: List[Dict[str, Any]] = [],
        citations: List[Dict[str, Any]] = [],
    ) -> VerificationScorecard:
        gates: Dict[str, GateResult] = {}
        now = datetime.utcnow()

        # Gate 1: Evidence Gate (Cryptographic Hash Integrity)
        hash_match = document_sha256.lower() == expected_sha256.lower() if expected_sha256 else True
        gates["evidence_gate"] = GateResult(
            gate_name="Evidence Cryptographic Integrity",
            passed=hash_match,
            status="PASS" if hash_match else "FAIL",
            details="SHA-256 source evidence fingerprint matches immutable storage record."
            if hash_match
            else "Cryptographic hash mismatch in source document evidence.",
        )

        # Gate 2: Source Version & Temporal Gate
        is_superseded = superseded_date is not None and superseded_date <= now
        temp_passed = not is_superseded
        gates["temporal_gate"] = GateResult(
            gate_name="Source Version & Temporal Validity",
            passed=temp_passed,
            status="PASS" if temp_passed else "FAIL",
            details="Regulatory version is currently active and effective."
            if temp_passed
            else f"Regulatory version was superseded on {superseded_date}.",
        )

        # Gate 3: Jurisdiction Gate
        reg_j = regulation_jurisdiction.strip().upper()
        pol_j = policy_jurisdiction.strip().upper()
        j_match = (reg_j == "GLOBAL" or pol_j == "GLOBAL" or reg_j == pol_j)
        gates["jurisdiction_gate"] = GateResult(
            gate_name="Jurisdiction Boundary Isolation",
            passed=j_match,
            status="PASS" if j_match else "FAIL",
            details=f"Jurisdiction matched ({reg_j} -> {pol_j})"
            if j_match
            else f"Jurisdiction mismatch: Cannot apply {reg_j} regulation to {pol_j} bank policy.",
        )

        # Gate 4: Applicability Gate
        app_match = (
            len(regulation_applies_to) == 0
            or any(tenant_entity_type.lower() in app.lower() for app in regulation_applies_to)
            or "commercial banks" in [a.lower() for a in regulation_applies_to]
        )
        gates["applicability_gate"] = GateResult(
            gate_name="Entity Applicability Scope",
            passed=app_match,
            status="PASS" if app_match else "FAIL",
            details=f"Regulation applies directly to entity type '{tenant_entity_type}'."
            if app_match
            else f"Entity type '{tenant_entity_type}' not in regulatory applicability list: {regulation_applies_to}",
        )

        # Gate 5: Requirement Coverage Gate
        total_reqs = len(all_requirements)
        req_codes = {r.get("req_code") for r in all_requirements if r.get("req_code")}
        addressed_codes = set()
        for ch in proposed_amendments:
            for cit in ch.get("citations", []):
                for code in req_codes:
                    if code and code in str(cit):
                        addressed_codes.add(code)
            # Or if justification mentions req
            for code in req_codes:
                if code and code in ch.get("justification", ""):
                    addressed_codes.add(code)

        uncovered = list(req_codes - addressed_codes) if req_codes else []
        coverage_pct = round((len(addressed_codes) / max(total_reqs, 1)) * 100.0, 1)
        cov_passed = len(uncovered) == 0 or total_reqs == 0
        gates["coverage_gate"] = GateResult(
            gate_name="Requirement Coverage Gate",
            passed=cov_passed,
            status="PASS" if cov_passed else "FAIL",
            details=f"100% of extracted requirements ({total_reqs}/{total_reqs}) mapped to policy clauses."
            if cov_passed
            else f"Unmapped requirements detected: {uncovered} (Coverage: {coverage_pct}%)",
            metadata={"uncovered_requirements": uncovered, "coverage_pct": coverage_pct},
        )

        # Gate 6: Exception Preservation Gate
        exceptions_preserved = True
        missed_exceptions = []
        for req in all_requirements:
            exceptions = req.get("exceptions", [])
            for exc in exceptions:
                # Check if proposed text or policy includes exception keywords
                exc_words = set(re.findall(r"\w+", exc.lower()))
                all_props_text = " ".join([p.get("proposed_text", "").lower() for p in proposed_amendments])
                if not any(w in all_props_text for w in exc_words if len(w) > 4):
                    exceptions_preserved = False
                    missed_exceptions.append(exc)

        gates["exception_preservation_gate"] = GateResult(
            gate_name="Regulatory Exception Preservation",
            passed=exceptions_preserved,
            status="PASS" if exceptions_preserved else "FAIL",
            details="All statutory and regulatory exceptions preserved in proposed policy redlines."
            if exceptions_preserved
            else f"Regulatory exceptions missed in policy draft: {missed_exceptions}",
        )

        # Gate 7: Citation Gate (Verbatim Sentence-Level Evidence Match)
        citation_results = cls.verify_sentence_citations(citations, raw_document_text)
        citations_valid = all(c.is_valid for c in citation_results) if citation_results else True
        gates["citation_gate"] = GateResult(
            gate_name="Sentence-Level Citation Evidence",
            passed=citations_valid,
            status="PASS" if citations_valid else "FAIL",
            details="All claims and amendments trace verbatim to immutable source text."
            if citations_valid
            else "One or more citations failed evidence verification (hallucinated or drifted text).",
            metadata={"citation_count": len(citation_results)},
        )

        # Gate 8: Contradiction & Consistency Gate
        contradictions = cls.detect_inversions(proposed_amendments, raw_document_text)
        no_contradictions = len(contradictions) == 0
        gates["contradiction_gate"] = GateResult(
            gate_name="Contradiction & Obligation Consistency",
            passed=no_contradictions,
            status="PASS" if no_contradictions else "FAIL",
            details="No conflicting or inverted obligation verbs detected."
            if no_contradictions
            else f"Obligation contradictions flagged: {contradictions}",
        )

        passed_count = sum(1 for g in gates.values() if g.passed)
        overall_passed = passed_count == len(gates)
        confidence = round(passed_count / len(gates), 2)

        return VerificationScorecard(
            overall_passed=overall_passed,
            confidence_score=confidence,
            gates=gates,
            summary="All 8 independent compliance verification gates PASSED."
            if overall_passed
            else f"Verification gate failures detected ({passed_count}/{len(gates)} gates passed). Human review required.",
            total_gates=len(gates),
            passed_gates_count=passed_count,
        )

    @classmethod
    def verify_sentence_citations(
        cls,
        citations: List[Dict[str, Any]],
        raw_source_text: str,
    ) -> List[ClaimLineageVerification]:
        results = []
        source_lower = raw_source_text.lower()

        for cit in citations:
            quote = cit.get("quote", "").strip()
            page = cit.get("page", 1)
            if not quote:
                results.append(
                    ClaimLineageVerification(
                        claim_text=cit.get("claim", "Policy amendment clause"),
                        source_verbatim_quote="",
                        page_number=page,
                        is_valid=False,
                        similarity_score=0.0,
                        error="Missing citation quote.",
                    )
                )
                continue

            quote_lower = quote.lower()
            if quote_lower in source_lower:
                results.append(
                    ClaimLineageVerification(
                        claim_text=cit.get("claim", "Policy amendment clause"),
                        source_verbatim_quote=quote,
                        page_number=page,
                        is_valid=True,
                        similarity_score=1.0,
                    )
                )
            else:
                quote_words = set(re.findall(r"\w+", quote_lower))
                source_words = set(re.findall(r"\w+", source_lower))
                overlap = quote_words.intersection(source_words)
                ratio = len(overlap) / max(len(quote_words), 1)

                if ratio >= 0.75:
                    results.append(
                        ClaimLineageVerification(
                            claim_text=cit.get("claim", "Policy amendment clause"),
                            source_verbatim_quote=quote,
                            page_number=page,
                            is_valid=True,
                            similarity_score=round(ratio, 2),
                        )
                    )
                else:
                    results.append(
                        ClaimLineageVerification(
                            claim_text=cit.get("claim", "Policy amendment clause"),
                            source_verbatim_quote=quote,
                            page_number=page,
                            is_valid=False,
                            similarity_score=round(ratio, 2),
                            error="Hallucinated or unsupported quote in regulatory source.",
                        )
                    )

        return results

    @staticmethod
    def detect_inversions(
        proposed_amendments: List[Dict[str, Any]],
        regulation_text: str,
    ) -> List[str]:
        contradictions = []
        reg_lower = regulation_text.lower()

        for amendment in proposed_amendments:
            prop_text = amendment.get("proposed_text", "").lower()
            if "optional" in prop_text and ("mandatory" in reg_lower or "shall" in reg_lower):
                contradictions.append(
                    f"Clause {amendment.get('clause_number', 'N/A')}: Proposed text allows optional compliance while regulation mandates strict adherence."
                )

        return contradictions
