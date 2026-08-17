# ADR-006: Deterministic 8-Gate Verification Engine Before Generation Acceptance

* **Status**: Accepted
* **Date**: 2026-08-17
* **Deciders**: AI Safety, Compliance & Legal Architecture

---

## Context & Problem Statement
Generative LLMs are probabilistic systems prone to hallucinations, citation drift (inventing non-existent circular clauses), subtle obligation inversions (turning mandatory rules into recommendations), and dropping statutory exceptions. In banking, an unverified AI output can lead to regulatory non-compliance, severe financial penalties, and loss of operating license.

## Decision
We enforce a core architectural rule: **No AI-generated compliance artifact is considered valid unless verified by independent deterministic gates.**

We implement the **8-Gate Verification Engine** in `services/compliance/verification.py`:
* **Gate 1 (Evidence Cryptographic Integrity)**: Verifies SHA-256 fingerprint against source document.
* **Gate 2 (Temporal & Superseded Validity)**: Confirms regulatory circular is currently active as of the target transaction date.
* **Gate 3 (Jurisdiction Isolation)**: Prevents cross-jurisdiction policy application.
* **Gate 4 (Entity Applicability Scope)**: Ensures the circular applies to the bank's specific license type.
* **Gate 5 (Requirement Coverage Gate)**: Proves 100% of extracted regulatory mandates are mapped to policy clauses.
* **Gate 6 (Exception Preservation Gate)**: Ensures statutory exceptions are preserved in policy text.
* **Gate 7 (Sentence-Level Citation Gate)**: Verifies verbatim text match for every cited quote.
* **Gate 8 (Contradiction & Inversion Gate)**: Detects verb inversions (e.g. "shall" $\to$ "optional").

## Consequences
### Positive
* 100% defensible, machine-verifiable audit scorecard (`VerificationScorecard`).
* Immediate detection and rejection of hallucinated citations.
* Regulatory compliance decisions can be defended in formal audits.

### Negative
* Proposals that fail any gate are blocked until reviewed or manually approved by a human compliance officer.
