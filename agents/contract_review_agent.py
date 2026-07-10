"""
Contract Review Agent — detects risky clauses, explains risks,
assigns severity, and provides recommendations for each clause.
"""

import json
import re
import watsonx_client

SYSTEM_PROMPT = """You are a senior contract lawyer specialising in commercial,
employment, technology, and consumer contracts.

Review the provided contract and:
1. Identify ALL risky, unusual, or one-sided clauses.
2. For each risky clause:
   - Name the clause type
   - Quote the exact problematic text (or a representative excerpt)
   - Explain the risk in plain English
   - Assign severity: "critical" | "high" | "medium" | "low"
   - Provide a concrete recommendation to fix or negotiate the clause
3. Identify missing standard protections that should be present.
4. Provide an overall contract fairness assessment.

OUTPUT a JSON block wrapped in ```json ... ``` with this structure:
{
  "overall_assessment": "fair|unfair|heavily_one_sided|standard",
  "fairness_score": <integer 0-100, where 100 = fully fair>,
  "risky_clauses": [
    {
      "clause_type": "type name",
      "excerpt": "quoted text",
      "risk_explanation": "plain English explanation",
      "severity": "critical|high|medium|low",
      "recommendation": "what to negotiate or change"
    }
  ],
  "missing_protections": ["missing protection 1", "missing protection 2"],
  "positive_clauses": ["clause that protects the reviewing party"],
  "negotiation_summary": "Overall negotiation strategy in 2-3 sentences"
}

Always consider the perspective of the party asking for review."""


def run(contract_text: str, party_role: str = "employee", jurisdiction: str = "unspecified") -> dict:
    """
    Review a contract for risky clauses.

    Args:
        contract_text: Full or truncated contract text.
        party_role:    Who we are reviewing for (employee, employer, buyer, seller, tenant, landlord).
        jurisdiction:  Applicable jurisdiction.

    Returns:
        Contract review dict.
    """
    sample = contract_text[:5000] if len(contract_text) > 5000 else contract_text

    content = (
        f"Jurisdiction: {jurisdiction}\n"
        f"Reviewing party: {party_role}\n\n"
        f"CONTRACT TEXT:\n{sample}"
    )

    try:
        reply = watsonx_client.chat(
            [{"role": "user", "content": content}],
            system_prompt=SYSTEM_PROMPT,
            max_tokens=2000,
            temperature=0.1,
        )

        match = re.search(r"```json\s*(\{.*?\})\s*```", reply, re.DOTALL)
        if match:
            result = json.loads(match.group(1))
            result["disclaimer"] = (
                "⚠️ This contract review is for informational purposes only and does not "
                "constitute legal advice. Have a qualified lawyer review before signing."
            )
            return result
    except Exception:
        pass

    return {
        "overall_assessment": "unknown",
        "fairness_score": 50,
        "risky_clauses": [],
        "missing_protections": [],
        "positive_clauses": [],
        "negotiation_summary": "Manual review recommended.",
        "disclaimer": "Contract review could not be completed automatically.",
    }
