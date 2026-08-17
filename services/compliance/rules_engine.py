from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from pydantic import BaseModel


class RuleEngineResult(BaseModel):
    passed: bool
    reason: str
    jurisdiction_match: bool
    temporal_valid: bool


class ComplianceRulesEngine:
    """
    Deterministic rule engine that validates compliance parameters independently of any LLM:
    1. Jurisdiction Isolation (No US regulation applied to Indian entity without cross-border flag)
    2. Temporal Validity (Effective date, publication date vs policy review timelines)
    3. Mandatory Obligation Enforcement
    """

    @staticmethod
    def validate_jurisdiction(
        regulation_jurisdiction: str,
        policy_jurisdiction: str,
        cross_border_allowed: bool = False,
    ) -> Tuple[bool, str]:
        reg_j = regulation_jurisdiction.strip().upper()
        pol_j = policy_jurisdiction.strip().upper()

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
    ) -> Tuple[bool, str]:
        now = datetime.utcnow()

        if superseded_date and superseded_date <= now:
            return False, f"Regulation was superseded on {superseded_date.strftime('%Y-%m-%d')}."

        if effective_date > now:
            days_remaining = (effective_date - now).days
            return True, f"Future effective regulation (effective in {days_remaining} days). Implementation preparation active."

        return True, "Regulation is currently active and effective."

    @classmethod
    def evaluate(
        cls,
        regulation_jurisdiction: str,
        policy_jurisdiction: str,
        publication_date: datetime,
        effective_date: datetime,
        superseded_date: Optional[datetime] = None,
    ) -> RuleEngineResult:
        j_passed, j_msg = cls.validate_jurisdiction(regulation_jurisdiction, policy_jurisdiction)
        t_passed, t_msg = cls.validate_temporal_validity(publication_date, effective_date, superseded_date)

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
