"""
Extended Orchestrator — coordinates all agents with consultation-form
pre-intake, RAG research, compliance checks, and report generation.

Workflow stages:
  consultation_form → intake → research → advice → document_choice → complete
"""

import json
from agents import intake_agent, advice_agent, document_agent
from agents import rag_agent, compliance_agent


class LegalAidOrchestrator:
    """
    Full multi-agent orchestrator with extended consultation flow.

    Pre-intake data (set before first chat message):
        case_type    : legal domain
        country      : country string
        state        : state/province
        language     : user language
        urgency      : high|medium|low
        description  : initial description from consultation form
    """

    def __init__(self):
        self.stage: str = "intake"
        self.history: list[dict] = []
        self.intake: dict | None = None
        self.research: str = ""
        self.advice: str = ""
        self.document: str = ""
        self.compliance: dict | None = None
        # Pre-intake context from consultation form
        self.case_type: str = ""
        self.country: str = ""
        self.state: str = ""
        self.language: str = "English"
        self.urgency: str = "medium"
        self.description: str = ""
        # Flask app ref for RAG DB access
        self._app = None

    def set_app(self, app):
        self._app = app

    def set_consultation_context(self, case_type: str, country: str, state: str,
                                  language: str, urgency: str, description: str):
        """Called once before the first chat message with the form data."""
        self.case_type   = case_type
        self.country     = country
        self.state       = state
        self.language    = language
        self.urgency     = urgency
        self.description = description

    # ── Public API ─────────────────────────────────────────────────────────────

    def send(self, user_message: str) -> dict:
        if self.stage == "intake":
            return self._handle_intake(user_message)
        if self.stage == "document_choice":
            return self._handle_document_choice(user_message)
        return {
            "stage": self.stage,
            "reply": "Processing… please wait.",
            "complete": False,
            "outputs": None,
        }

    def run_analysis(self) -> dict:
        if not self.intake:
            raise RuntimeError("Intake must be complete before running analysis.")

        summary      = self.intake["summary"]
        domain       = self.intake.get("domain", self.case_type or "other")
        jurisdiction = f"{self.country}, {self.state}".strip(", ") or self.intake.get("jurisdiction", "unspecified")

        # Stage: Research (RAG-enhanced)
        self.stage    = "research"
        self.research = rag_agent.run(summary, jurisdiction, domain, self._app)

        # Stage: Advice
        self.stage = "advice"
        self.advice = advice_agent.run(summary, self.research, domain, jurisdiction)

        # Stage: Compliance check (auto, non-blocking)
        try:
            self.compliance = compliance_agent.run(summary, jurisdiction, domain)
        except Exception:
            self.compliance = None

        # Stage: Ask about document drafting
        self.stage = "document_choice"
        return {
            "stage": "document_choice",
            "reply": (
                "✅ I've completed the legal research and prepared your advice. "
                "Would you also like me to draft a legal document for your situation? "
                "(e.g. demand letter, cease & desist, complaint form)\n\n"
                "Reply with **yes** (or specify the document type), or **no** to skip."
            ),
            "complete": False,
            "outputs": None,
        }

    # ── Internal helpers ────────────────────────────────────────────────────────

    def _build_intake_system_prompt(self) -> str:
        """Build a context-aware intake system prompt using pre-filled form data."""
        from agents.intake_agent import SYSTEM_PROMPT as BASE

        context_lines = []
        if self.case_type:
            context_lines.append(f"Case type: {self.case_type}")
        if self.country:
            context_lines.append(f"Country: {self.country}")
        if self.state:
            context_lines.append(f"State/Province: {self.state}")
        if self.language and self.language != "English":
            context_lines.append(f"User's preferred language: {self.language}")
        if self.urgency:
            context_lines.append(f"Urgency: {self.urgency}")
        if self.description:
            context_lines.append(f"Initial description: {self.description}")

        if not context_lines:
            return BASE

        context_block = "\n".join(context_lines)
        return (
            BASE
            + f"\n\nPRE-FILLED CONTEXT (already collected via form — do NOT ask again):\n{context_block}\n"
            + "Focus your questions on specifics not covered by the pre-filled context."
        )

    def _handle_intake(self, user_message: str) -> dict:
        import re

        # Build history with context-aware system prompt embedded as first user turn
        system_prompt = self._build_intake_system_prompt()

        full_history = self.history + [{"role": "user", "content": user_message}]
        import watsonx_client
        reply = watsonx_client.chat(full_history, system_prompt=system_prompt)

        self.history.append({"role": "user",      "content": user_message})
        self.history.append({"role": "assistant",  "content": reply})

        # Check for completed intake JSON
        intake_data = None
        match = re.search(r"```json\s*(\{.*?\})\s*```", reply, re.DOTALL)
        if match:
            try:
                intake_data = json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        if intake_data:
            # Merge form context into intake
            if not intake_data.get("jurisdiction"):
                intake_data["jurisdiction"] = f"{self.country}, {self.state}".strip(", ")
            if not intake_data.get("domain") and self.case_type:
                intake_data["domain"] = self.case_type
            if not intake_data.get("urgency") and self.urgency:
                intake_data["urgency"] = self.urgency

            self.intake = intake_data
            self.stage  = "post_intake"
            return {
                "stage":    "post_intake",
                "reply":    reply,
                "complete": False,
                "outputs":  None,
                "trigger_analysis": True,
            }

        return {
            "stage":    "intake",
            "reply":    reply,
            "complete": False,
            "outputs":  None,
        }

    def _handle_document_choice(self, user_message: str) -> dict:
        lower = user_message.strip().lower()
        if lower in ("no", "nope", "skip", "no thanks", "no thank you", "n"):
            self.stage = "complete"
            return self._build_complete_response(document_drafted=False)

        doc_type = "auto"
        skip_words = {"yes", "sure", "ok", "okay", "please", "draft", "y", "yep", "yeah"}
        if lower not in skip_words and len(lower) > 3:
            doc_type = user_message.strip()

        intake_summary = self.intake.get("summary", self.description)
        domain         = self.intake.get("domain", self.case_type or "other")
        jurisdiction   = self.intake.get(
            "jurisdiction",
            f"{self.country}, {self.state}".strip(", ") or "unspecified"
        )

        self.document = document_agent.run(
            intake_summary=intake_summary,
            domain=domain,
            jurisdiction=jurisdiction,
            document_type=doc_type,
        )
        self.stage = "complete"
        return self._build_complete_response(document_drafted=True)

    def _build_complete_response(self, document_drafted: bool) -> dict:
        return {
            "stage":    "complete",
            "reply":    "Your legal aid package is ready. View the full report in the Reports tab.",
            "complete": True,
            "outputs": {
                "intake":     self.intake,
                "research":   self.research,
                "advice":     self.advice,
                "document":   self.document if document_drafted else None,
                "compliance": self.compliance,
            },
        }

    def to_dict(self) -> dict:
        """Serialise orchestrator state for persistence."""
        return {
            "stage":       self.stage,
            "history":     self.history,
            "intake":      self.intake,
            "research":    self.research,
            "advice":      self.advice,
            "document":    self.document,
            "compliance":  self.compliance,
            "case_type":   self.case_type,
            "country":     self.country,
            "state":       self.state,
            "language":    self.language,
            "urgency":     self.urgency,
            "description": self.description,
        }
