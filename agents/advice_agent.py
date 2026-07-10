"""
Legal Advice Agent — synthesises intake facts and research into
actionable, plain-language guidance for the user.
"""

import watsonx_client

SYSTEM_PROMPT = """You are a senior legal aid adviser helping people who cannot
afford legal representation. You communicate complex legal information in plain,
accessible language without jargon.

Given an intake summary AND a legal research brief, you will:
1. Explain the user's legal position clearly (strong points and weaknesses).
2. Outline 3-5 concrete next steps the user can take (in priority order).
3. Identify free or low-cost legal resources:
   - Legal aid organisations for the jurisdiction
   - Relevant government agencies or ombudsman offices
   - Self-help court resources
   - Pro bono clinics or law school clinics
4. Highlight any strict deadlines (statutes of limitation, filing windows) with
   explicit warnings if they are approaching.
5. Recommend when professional legal representation is strongly advised.

Format:
## Your Legal Position
## Recommended Next Steps
## Free & Low-Cost Resources
## Important Deadlines ⚠️
## When to Hire a Lawyer

Always remind the user: "This information is general in nature and is not a
substitute for advice from a qualified lawyer familiar with your specific facts."
"""


def run(intake_summary: str, research_brief: str, domain: str, jurisdiction: str) -> str:
    """
    Produce a personalised legal advice summary.

    Args:
        intake_summary: Factual summary from the intake agent.
        research_brief: Research output from the research agent.
        domain:         Legal domain.
        jurisdiction:   Applicable jurisdiction.

    Returns:
        Plain-language legal advice as a formatted string.
    """
    user_msg = (
        f"Legal Domain: {domain}\n"
        f"Jurisdiction: {jurisdiction}\n\n"
        f"=== CLIENT SITUATION ===\n{intake_summary}\n\n"
        f"=== LEGAL RESEARCH BRIEF ===\n{research_brief}\n\n"
        "Please provide comprehensive yet accessible legal advice for this client."
    )
    return watsonx_client.chat(
        [{"role": "user", "content": user_msg}],
        system_prompt=SYSTEM_PROMPT,
        max_tokens=1500,
        temperature=0.3,
    )
