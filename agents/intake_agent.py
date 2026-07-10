"""
Intake Agent — first point of contact.
Gathers facts about the user's legal issue and categorises it
into one of the supported legal domains.
"""

import watsonx_client

SYSTEM_PROMPT = """You are a compassionate and professional legal intake specialist.
Your role is to:
1. Warmly greet the user and ask them to describe their legal situation.
2. Ask focused follow-up questions to gather: names of parties involved, jurisdiction
   (country/state), key dates, and the main relief or outcome the user seeks.
3. After gathering enough facts, OUTPUT a JSON block wrapped in ```json ... ``` with:
   {
     "domain": one of ["employment", "family", "housing", "criminal", "immigration",
                       "consumer", "civil_rights", "business", "other"],
     "jurisdiction": "<country or state/province>",
     "summary": "<2-3 sentence factual summary of the issue>",
     "urgency": "high" | "medium" | "low",
     "key_facts": ["<fact 1>", "<fact 2>", ...]
   }

Be empathetic. Do NOT give legal advice yet — only gather facts.
Keep responses concise and plain-language."""


def run(user_message: str, history: list[dict]) -> dict:
    """
    Process one turn of the intake conversation.

    Args:
        user_message: The latest user input.
        history:      Prior conversation turns (role/content dicts).

    Returns:
        {
          "reply":    str  — agent's response text,
          "complete": bool — True when intake JSON has been extracted,
          "intake":   dict | None — parsed intake data if complete
        }
    """
    import json, re

    history = history + [{"role": "user", "content": user_message}]
    reply = watsonx_client.chat(history, system_prompt=SYSTEM_PROMPT)

    # Check for completed intake JSON
    intake_data = None
    match = re.search(r"```json\s*(\{.*?\})\s*```", reply, re.DOTALL)
    if match:
        try:
            intake_data = json.loads(match.group(1))
        except json.JSONDecodeError:
            intake_data = None

    return {
        "reply": reply,
        "complete": intake_data is not None,
        "intake": intake_data,
    }
