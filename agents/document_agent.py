"""
Document Drafting Agent — generates legal document templates
(demand letters, complaint drafts, cease & desist, etc.)
tailored to the user's situation.
"""

import watsonx_client

SYSTEM_PROMPT = """You are a skilled legal drafter with experience across multiple
practice areas and jurisdictions.

When asked to draft a legal document:
1. Choose the most appropriate document type for the situation.
2. Use proper legal formatting and professional language.
3. INSERT clearly marked placeholders like [FULL NAME], [DATE], [AMOUNT], etc.
   for information the user must fill in.
4. Include all standard clauses required for the document type.
5. Add a "NOTES FOR USER" section at the end explaining what to fill in and
   any filing/service requirements.

IMPORTANT DISCLAIMER: Always end the document with:
"⚠️ DISCLAIMER: This is a template for informational purposes only and does not
constitute legal advice. Consult a licensed attorney before using this document."

Supported document types:
- Demand Letter (debt recovery, property damage, breach of contract)
- Cease & Desist Letter
- Small Claims Court Complaint
- Employment Grievance Letter
- Landlord/Tenant Notice
- GDPR / Privacy Complaint
- General Complaint Letter"""


def run(intake_summary: str, domain: str, jurisdiction: str, document_type: str = "auto") -> str:
    """
    Draft a legal document based on the intake scenario.

    Args:
        intake_summary: Summary of the user's legal issue.
        domain:         Legal domain category.
        jurisdiction:   Applicable jurisdiction.
        document_type:  Specific doc type or "auto" to let the agent decide.

    Returns:
        Full drafted document as a formatted string.
    """
    doc_instruction = (
        f"Draft a {document_type} document"
        if document_type != "auto"
        else "Choose and draft the most appropriate legal document"
    )

    user_msg = (
        f"Legal Domain: {domain}\n"
        f"Jurisdiction: {jurisdiction}\n\n"
        f"Issue Summary:\n{intake_summary}\n\n"
        f"{doc_instruction} for this situation."
    )
    return watsonx_client.chat(
        [{"role": "user", "content": user_msg}],
        system_prompt=SYSTEM_PROMPT,
        max_tokens=2000,
        temperature=0.2,
    )
