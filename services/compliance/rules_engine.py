from datetime import datetime
from typing import Dict, Any, Tuple, Optional, List
from pydantic import BaseModel, Field


class RuleEngineResult(BaseModel):
    passed: bool
    reason: str
    jurisdiction_match: bool
    temporal_valid: bool


class ApplicabilityResult(BaseModel):
    status: str  # APPLICABLE, PARTIALLY_APPLICABLE, NOT_APPLICABLE, UNDER_REVIEW
    rationale: str
    confidence: float = 1.0
    matched_criteria: List[str] = Field(default_factory=list)
    unmatched_criteria: List[str] = Field(default_factory=list)


class RiskScoringResult(BaseModel):
    regulatory_severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    customer_impact: str
    financial_impact: str
    operational_impact: str
    likelihood: str
    inherent_risk: str
    control_effectiveness: str  # STRONG, MODERATE, WEAK, NONE
    residual_risk: str
    materiality: str  # LOW, MEDIUM, HIGH, CRITICAL
    formula_version: str = "v1.0"
    calculation_inputs: Dict[str, Any] = Field(default_factory=dict)
    rationale: str


class ComplianceRulesEngine:
    """
    Deterministic rule engine that validates compliance parameters independently of any LLM:
    1. Jurisdiction Isolation
    2. Temporal Validity & Historical As-Of Checks
    3. Multi-Factor Applicability Assessment
    4. Explainable Risk & Materiality Scoring Matrix
    """

    @staticmethod
    def validate_jurisdiction(
        regulation_jurisdiction: str,
        policy_jurisdiction: str,
        cross_border_allowed: bool = False,
    ) -> Tuple[bool, str]:
        reg_j = (regulation_jurisdiction or "GLOBAL").strip().upper()
        pol_j = (policy_jurisdiction or "GLOBAL").strip().upper()

        if reg_j == "GLOBAL" or pol_j == "GLOBAL":
            return True, "Global applicability permitted."

        if reg_j == pol_j:
            return True, f"Direct jurisdiction match ({reg_j})."

        if cross_border_allowed:
            return True, f"Cross-border regulation applicability allowed ({reg_j} -> {pol_j})."

        return False, f"Jurisdiction mismatch: Regulation is for {reg_j} but Policy is scoped to {pol_j}."

    @staticmethod
    def validate_temporal_validity(
        publication_date: datetime,
        effective_date: datetime,
        superseded_date: Optional[datetime] = None,
        as_of_date: Optional[datetime] = None,
    ) -> Tuple[bool, str]:
        check_date = as_of_date or datetime.utcnow()

        if superseded_date and superseded_date <= check_date:
            return False, f"Regulation was superseded on {superseded_date.strftime('%Y-%m-%d')} (as of {check_date.strftime('%Y-%m-%d')})."

        if effective_date > check_date:
            days_remaining = (effective_date - check_date).days
            return True, f"Future effective regulation (effective in {days_remaining} days). Implementation preparation active."

        return True, "Regulation is currently active and effective."

    @classmethod
    def evaluate_applicability(
        cls,
        obligation_applies_to: List[str],
        obligation_jurisdiction: str,
        tenant_entity_type: str = "Commercial Bank",
        tenant_jurisdiction: str = "GLOBAL",
        product_scope: Optional[str] = None,
        is_overseas_subsidiary: bool = False,
    ) -> ApplicabilityResult:
        """
        Determines whether a regulatory obligation applies to the tenant/entity/product/jurisdiction.
        """
        # 1. Jurisdiction Match
        j_match, _ = cls.validate_jurisdiction(obligation_jurisdiction, tenant_jurisdiction)
        if not j_match:
            return ApplicabilityResult(
                status="NOT_APPLICABLE",
                rationale=f"Jurisdiction mismatch: Obligation is for {obligation_jurisdiction} whereas entity is in {tenant_jurisdiction}.",
                unmatched_criteria=[f"Jurisdiction {obligation_jurisdiction}"],
            )

        # 2. Scope & Entity Type Matching
        scope_str = " ".join(obligation_applies_to).lower() if obligation_applies_to else "all entities"
        entity_lower = tenant_entity_type.lower()

        if is_overseas_subsidiary and "overseas" not in scope_str and "subsidiary" not in scope_str and "global" not in scope_str:
            return ApplicabilityResult(
                status="PARTIALLY_APPLICABLE",
                rationale="Applies to parent commercial banking entity, but does not apply to overseas subsidiary.",
                matched_criteria=["Parent Entity"],
                unmatched_criteria=["Overseas Subsidiary"],
            )

        if "all" in scope_str or entity_lower in scope_str or "bank" in scope_str or "regulated entity" in scope_str:
            return ApplicabilityResult(
                status="APPLICABLE",
                rationale=f"Obligation explicitly applies to entity type '{tenant_entity_type}'.",
                matched_criteria=[tenant_entity_type],
            )

        # Partial matching
        if any(w in scope_str for w in entity_lower.split()):
            return ApplicabilityResult(
                status="PARTIALLY_APPLICABLE",
                rationale=f"Obligation has partial entity overlap with '{tenant_entity_type}' (Scope: {obligation_applies_to}).",
                matched_criteria=["Partial Entity Type"],
            )

        return ApplicabilityResult(
            status="NOT_APPLICABLE",
            rationale=f"Obligation scope ({obligation_applies_to}) does not match entity type '{tenant_entity_type}'.",
            unmatched_criteria=[tenant_entity_type],
        )

    @classmethod
    def calculate_risk_and_materiality(
        cls,
        regulatory_severity: str = "HIGH",
        customer_impact: str = "MEDIUM",
        financial_impact: str = "HIGH",
        operational_impact: str = "MEDIUM",
        likelihood: str = "MEDIUM",
        control_effectiveness: str = "WEAK",
    ) -> RiskScoringResult:
        """
        Explainable, deterministic risk scoring matrix for compliance gaps.
        """
        # Map ratings to numeric levels (1-4)
        rating_map = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        ctrl_map = {"STRONG": 0.25, "MODERATE": 0.5, "WEAK": 0.85, "NONE": 1.0}

        r_sev = rating_map.get(regulatory_severity.upper(), 3)
        c_imp = rating_map.get(customer_impact.upper(), 2)
        f_imp = rating_map.get(financial_impact.upper(), 3)
        o_imp = rating_map.get(operational_impact.upper(), 2)
        l_val = rating_map.get(likelihood.upper(), 2)
        c_factor = ctrl_map.get(control_effectiveness.upper(), 0.85)

        # Inherent Risk = weighted impact * likelihood
        inherent_score = ((0.4 * r_sev) + (0.25 * f_imp) + (0.2 * c_imp) + (0.15 * o_imp)) * (l_val / 2.0)

        if inherent_score >= 3.2:
            inherent_str = "CRITICAL"
        elif inherent_score >= 2.4:
            inherent_str = "HIGH"
        elif inherent_score >= 1.6:
            inherent_str = "MEDIUM"
        else:
            inherent_str = "LOW"

        # Residual Risk = Inherent Score * Control Deficiency Factor
        residual_score = inherent_score * c_factor

        if residual_score >= 2.8:
            residual_str = "CRITICAL"
            materiality_str = "CRITICAL"
        elif residual_score >= 2.0:
            residual_str = "HIGH"
            materiality_str = "HIGH"
        elif residual_score >= 1.2:
            residual_str = "MEDIUM"
            materiality_str = "MEDIUM"
        else:
            residual_str = "LOW"
            materiality_str = "LOW"

        rationale = (
            f"Regulatory Severity ({regulatory_severity}) + Financial Impact ({financial_impact}) "
            f"with {likelihood} likelihood yields Inherent Risk ({inherent_str}). "
            f"Factoring Control Effectiveness ({control_effectiveness}) gives Residual Risk ({residual_str}) "
            f"and Materiality ({materiality_str})."
        )

        return RiskScoringResult(
            regulatory_severity=regulatory_severity,
            customer_impact=customer_impact,
            financial_impact=financial_impact,
            operational_impact=operational_impact,
            likelihood=likelihood,
            inherent_risk=inherent_str,
            control_effectiveness=control_effectiveness,
            residual_risk=residual_str,
            materiality=materiality_str,
            formula_version="v1.0",
            calculation_inputs={
                "regulatory_severity": regulatory_severity,
                "customer_impact": customer_impact,
                "financial_impact": financial_impact,
                "operational_impact": operational_impact,
                "likelihood": likelihood,
                "control_effectiveness": control_effectiveness,
                "inherent_score": round(inherent_score, 2),
                "residual_score": round(residual_score, 2),
            },
            rationale=rationale,
        )

    @classmethod
    def evaluate(
        cls,
        regulation_jurisdiction: str,
        policy_jurisdiction: str,
        publication_date: datetime,
        effective_date: datetime,
        superseded_date: Optional[datetime] = None,
        as_of_date: Optional[datetime] = None,
    ) -> RuleEngineResult:
        j_passed, j_msg = cls.validate_jurisdiction(regulation_jurisdiction, policy_jurisdiction)
        t_passed, t_msg = cls.validate_temporal_validity(publication_date, effective_date, superseded_date, as_of_date)

        overall_passed = j_passed and t_passed
        reasons = []
        if not j_passed:
            reasons.append(j_msg)
        if not t_passed:
            reasons.append(t_msg)

        return RuleEngineResult(
            passed=overall_passed,
            reason="; ".join(reasons) if reasons else "All deterministic compliance rules passed.",
            jurisdiction_match=j_passed,
            temporal_valid=t_passed,
        )
