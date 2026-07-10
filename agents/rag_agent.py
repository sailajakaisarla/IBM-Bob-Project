"""
RAG (Retrieval-Augmented Generation) Legal Research Agent.

Retrieves relevant knowledge from the local database first,
then synthesises with WatsonX to produce cited legal research.
"""

import json
import re
import watsonx_client


def _retrieve_knowledge(domain: str, jurisdiction: str, db) -> list[dict]:
    """Retrieve relevant knowledge base docs from DB."""
    try:
        from models import KnowledgeDoc
        query = KnowledgeDoc.query
        if domain:
            query = query.filter(
                (KnowledgeDoc.domain == domain) | (KnowledgeDoc.domain.is_(None))
            )
        if jurisdiction:
            query = query.filter(
                (KnowledgeDoc.jurisdiction.ilike(f"%{jurisdiction}%")) |
                (KnowledgeDoc.jurisdiction.is_(None))
            )
        docs = query.limit(5).all()
        return [{"title": d.title, "content": d.content[:800], "source": d.source_url or "Internal KB"} for d in docs]
    except Exception:
        return []


SYSTEM_PROMPT = """You are an expert legal researcher with deep knowledge of law across
major jurisdictions (US, UK, EU, India, Canada, Australia, and others).

Using the provided knowledge context (if any) AND your training knowledge:
1. Identify the 3-5 most relevant legal principles, statutes, or regulations with CITATIONS.
2. Cite landmark cases or key precedents with case names, years, and brief descriptions.
3. Summarise the legal standards courts/tribunals apply to this type of issue.
4. Flag jurisdictional nuances that could affect the outcome.
5. Note any recent developments (post-2020) in this area.

ALWAYS:
- Format citations as: [Statute Name, Section X] or [Case Name (Year)]
- Use headings:
  ## Applicable Law & Statutes
  ## Key Cases & Precedents
  ## Legal Standards Applied
  ## Jurisdictional Notes
  ## Recent Developments
- End with: ⚠️ DISCLAIMER: This is general legal information, not legal advice.

Be precise. Indicate uncertainty where it exists."""


def run(
    intake_summary: str,
    jurisdiction: str,
    domain: str,
    app=None,
) -> str:
    """
    Run RAG-enhanced legal research.

    Args:
        intake_summary: Factual summary of the user's legal issue.
        jurisdiction:   Country or state/province.
        domain:         Legal domain.
        app:            Flask app instance (for DB context), optional.

    Returns:
        Formatted legal research report as a string.
    """
    # Retrieve local knowledge — only push a new context if one isn't active
    kb_context = ""
    if app:
        docs = []
        try:
            from flask import current_app  # raises RuntimeError outside a context
            current_app._get_current_object()  # probe: raises if no active context
            # Already inside an app context (e.g. called from a request handler)
            from models import db
            docs = _retrieve_knowledge(domain, jurisdiction, db)
        except RuntimeError:
            # No active context — push one (e.g. called from a background thread)
            with app.app_context():
                from models import db
                docs = _retrieve_knowledge(domain, jurisdiction, db)
        if docs:
            kb_context = "\n\n=== KNOWLEDGE BASE CONTEXT ===\n"
            for i, d in enumerate(docs, 1):
                kb_context += f"\n[Source {i}: {d['title']}]\n{d['content']}\n"

    user_msg = (
        f"Legal Domain: {domain}\n"
        f"Jurisdiction: {jurisdiction}\n\n"
        f"Issue Summary:\n{intake_summary}"
        + kb_context
        + "\n\nProvide a comprehensive legal research brief with citations."
    )

    return watsonx_client.chat(
        [{"role": "user", "content": user_msg}],
        system_prompt=SYSTEM_PROMPT,
        max_tokens=1800,
        temperature=0.2,
    )
