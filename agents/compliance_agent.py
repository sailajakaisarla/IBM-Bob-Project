"""
Compliance Checker Agent — verifies a document or scenario against
applicable laws and regulations, returning Pass/Fail/Warning results.
"""

import json
import re
import watsonx_client

SYSTEM_PROMPT = """You are a specialist legal compliance auditor with expertise in
employment law, consumer protection, contract law, data privacy (GDPR, CCPA),
labour regulations, and corporate governance across multiple jurisdictions.

Given a legal scenario and/or document content, perform a compliance check:
1. Identify 5-10 specific legal requirements applicable to this scenario/document.
2. For each requirement, determine: PASS, FAIL, or WARNING.
3. For FAIL and WARNING items, explain the specific issue and what is required.
4. Provide an overall compliance rating: "compliant", "partially_compliant", or "non_compliant".
5. List specific remediation steps needed.

OUTPUT a JSON block wrapped in ```json ... ``` with this structure:
{
  "overall_status": "compliant|partially_compliant|non_compliant",
  "compliance_score": <integer 0-100>,
  "applicable_laws": ["law 1", "law 2"],
  "checks": [
    {
      "requirement": "Legal requirement description",
      "status": "PASS|FAIL|WARNING",
      "explanation": "Why this status",
      "law_reference": "Specific law/section if applicable"
    }
  ],
  "remediation": ["Step 1 to fix", "Step 2 to fix"],
  "jurisdiction_note": "Any jurisdiction-specific observations"
}

Be precise, cite specific legal provisions where possible."""


def run(scenario: str, jurisdiction: str, domain: str, document_text: str = "") -> dict:
    """
    Run compliance checks on a legal scenario and optional document.

    Returns:
        Compliance result dict with checks, status, and remediation steps.
    """
    content = f"Legal Domain: {domain}\nJurisdiction: {jurisdiction}\n\nScenario:\n{scenario}"
    if document_text:
        sample = document_text[:3000] if len(document_text) > 3000 else document_text
        content += f"\n\nDocument Content:\n{sample}"

    try:
        reply = watsonx_client.chat(
            [{"role": "user", "content": content}],
            system_prompt=SYSTEM_PROMPT,
            max_tokens=1800,
            temperature=0.1,
        )

        match = re.search(r"```json\s*(\{.*?\})\s*```", reply, re.DOTALL)
        if match:
            result = json.loads(match.group(1))
            result["disclaimer"] = (
                "⚠️ This compliance check is informational only. "
                "Consult a qualified lawyer for definitive compliance advice."
            )
            return result
    except Exception:
        pass

    return {
        "overall_status": "unknown",
        "compliance_score": 0,
        "applicable_laws": [],
        "checks": [],
        "remediation": ["Manual legal review recommended."],
        "jurisdiction_note": "",
        "disclaimer": "Compliance check could not be completed.",
    }
