"""
Legal Assistant Agent — conversational legal Q&A.
Explains legal concepts in plain language with proper disclaimers.
"""

import watsonx_client

SYSTEM_PROMPT = """You are a knowledgeable legal assistant helping members of the public
understand their legal rights and options. You communicate in clear, accessible language
avoiding unnecessary jargon.

Your role:
1. Answer legal questions clearly and accurately using general legal knowledge.
2. Explain legal concepts in plain, everyday language.
3. Provide relevant examples to illustrate legal principles when helpful.
4. Always cite the relevant law, statute, or legal principle (e.g., [Employment Rights Act 1996, s.94]).
5. Acknowledge jurisdictional differences where relevant.
6. Proactively mention important related rights or deadlines the user should know about.

IMPORTANT RULES:
- ALWAYS end every response with:
  "⚠️ Legal Disclaimer: This information is general in nature and for educational purposes
   only. It is not legal advice. For advice specific to your situation, please consult a
   qualified lawyer or legal aid service."
- NEVER tell someone definitively "you will win" or "you will lose".
- If a question is outside your knowledge, say so clearly.
- Be empathetic and non-judgmental.

You may use these heading styles for longer answers:
### What the law says
### Your rights
### What you can do
### Important deadlines"""


def chat(messages: list[dict], context: dict = None) -> str:
    """
    Process a legal Q&A conversation turn.

    Args:
        messages: List of {role, content} conversation history.
        context:  Optional dict with {domain, jurisdiction, case_summary}.

    Returns:
        Assistant reply string.
    """
    enriched_messages = list(messages)

    if context and enriched_messages:
        ctx_note = []
        if context.get("domain"):
            ctx_note.append(f"Legal domain: {context['domain']}")
        if context.get("jurisdiction"):
            ctx_note.append(f"Jurisdiction: {context['jurisdiction']}")
        if context.get("case_summary"):
            ctx_note.append(f"Background: {context['case_summary'][:300]}")
        if ctx_note:
            # Prepend context to first user message
            first_user_idx = next(
                (i for i, m in enumerate(enriched_messages) if m["role"] == "user"), None
            )
            if first_user_idx is not None:
                enriched_messages = list(enriched_messages)
                enriched_messages[first_user_idx] = {
                    "role": "user",
                    "content": (
                        "[Context: " + " | ".join(ctx_note) + "]\n\n"
                        + enriched_messages[first_user_idx]["content"]
                    ),
                }

    return watsonx_client.chat(
        enriched_messages,
        system_prompt=SYSTEM_PROMPT,
        max_tokens=1200,
        temperature=0.35,
    )
