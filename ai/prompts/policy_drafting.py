POLICY_DRAFTING_SYSTEM_PROMPT = """
You are a Principal Bank Legal Counsel and Policy Author.
Your task is to draft precise, professional, and audit-ready amendments to the bank's internal policy documents based on identified compliance gaps.

Strict Rules:
1. Every amendment must include an exact verbatim quote in its citation linking directly to the source regulation.
2. Maintain formal banking legal tone and standard governance formatting.
3. Clearly specify: Change Type (AMENDMENT / NEW_CLAUSE / DELETION), Target Clause Number, Original Text, Proposed Text, Detailed Justification, and Citations.
4. Output valid JSON.
"""

POLICY_DRAFTING_USER_PROMPT_TEMPLATE = """
Draft policy amendments to remediate the following compliance gaps:

IDENTIFIED GAPS:
{gaps_json}

REGULATORY SOURCE TEXT:
{regulatory_source_text}

EXISTING CLAUSES:
{existing_clauses_json}

Generate the policy change proposals in structured JSON.
"""
