"""
Legal Research Agent — given a categorised intake summary,
retrieves relevant legal principles, statutes, and precedent guidance.
"""

import watsonx_client

SYSTEM_PROMPT = """You are an expert legal researcher with knowledge of law across
major jurisdictions (US, UK, EU, Canada, Australia).

Given a structured legal issue summary, you will:
1. Identify the 3-5 most relevant legal principles, statutes, or regulations.
2. Cite landmark cases or precedents where applicable (with brief descriptions).
3. Summarise the typical legal standards courts apply to this type of issue.
4. Flag any jurisdictional nuances that could affect the outcome.
5. Note any recent legal developments (post-2020) in this area if relevant.

Format your response with clear headings:
## Applicable Law
## Key Precedents
## Legal Standards
## Jurisdictional Notes
## Recent Developments

Be precise and factual. Indicate when you are uncertain. Do NOT give personal
legal advice — present general legal information only."""


def run(intake_summary: str, jurisdiction: str, domain: str) -> str:
    """
    Perform legal research for a given intake scenario.

    Args:
        intake_summary: Plain-text summary of the user's legal issue.
        jurisdiction:   Country or state/province string.
        domain:         Legal domain (employment, family, etc.).

    Returns:
        Formatted legal research report as a string.
    """
    user_msg = (
        f"Legal Domain: {domain}\n"
        f"Jurisdiction: {jurisdiction}\n\n"
        f"Issue Summary:\n{intake_summary}\n\n"
        "Please provide a comprehensive legal research brief for this issue."
    )
    return watsonx_client.chat(
        [{"role": "user", "content": user_msg}],
        system_prompt=SYSTEM_PROMPT,
        max_tokens=1500,
        temperature=0.2,
    )
