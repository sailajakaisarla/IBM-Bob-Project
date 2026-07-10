"""
Report Generator Agent — produces a structured legal aid report
that can be exported as PDF or JSON.
"""

import json
from datetime import datetime, timezone
import watsonx_client


SYSTEM_PROMPT = """You are a professional legal report writer. Your task is to compile
a formal Legal Aid Report from the provided case data.

The report must include these sections in order:
1. EXECUTIVE SUMMARY — 2-3 sentences overview
2. CLIENT SITUATION — Factual description of the issue
3. APPLICABLE LAWS — Key statutes and regulations with citations
4. CASE REFERENCES — Relevant precedents (if available)
5. RISK ANALYSIS — Assessment of the client's legal position
6. RECOMMENDATIONS — Prioritised action steps (numbered list)
7. FREE LEGAL RESOURCES — Relevant aid organisations and government resources
8. IMPORTANT DEADLINES — Any time-sensitive legal deadlines
9. DISCLAIMER — Standard legal disclaimer

Write in formal but accessible language. Use clear headings.
Always conclude with: "This report was generated with AI assistance (IBM WatsonX granite-4-h-small)
and constitutes general legal information only. It is not legal advice. Please consult a
qualified lawyer for advice specific to your situation.\""""


def generate_report_content(
    case_title: str,
    case_type: str,
    jurisdiction: str,
    intake_data: dict,
    research: str,
    advice: str,
    document_analysis: dict = None,
) -> str:
    """
    Generate a comprehensive legal report as structured text.

    Returns:
        Full report text (markdown-style).
    """
    intake_summary = intake_data.get("summary", "") if intake_data else ""
    key_facts = intake_data.get("key_facts", []) if intake_data else []
    urgency = intake_data.get("urgency", "medium") if intake_data else "medium"

    facts_text = "\n".join(f"- {f}" for f in key_facts) if key_facts else "No key facts recorded."

    doc_section = ""
    if document_analysis:
        doc_section = (
            f"\n\nDOCUMENT ANALYSIS SUMMARY:\n"
            f"Risk Score: {document_analysis.get('risk_score', 'N/A')}\n"
            f"Summary: {document_analysis.get('summary', 'N/A')}\n"
        )

    user_msg = (
        f"Case Title: {case_title}\n"
        f"Case Type: {case_type}\n"
        f"Jurisdiction: {jurisdiction}\n"
        f"Urgency: {urgency}\n\n"
        f"KEY FACTS:\n{facts_text}\n\n"
        f"SITUATION SUMMARY:\n{intake_summary}\n\n"
        f"LEGAL RESEARCH:\n{research}\n\n"
        f"LEGAL ADVICE:\n{advice}"
        + doc_section
        + "\n\nGenerate the complete formal Legal Aid Report."
    )

    return watsonx_client.chat(
        [{"role": "user", "content": user_msg}],
        system_prompt=SYSTEM_PROMPT,
        max_tokens=2500,
        temperature=0.2,
    )


def generate_pdf(
    report_text: str,
    case_title: str,
    client_name: str,
    output_path: str,
) -> bool:
    """
    Generate a PDF from report text using reportlab.

    Returns:
        True on success, False on failure.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
        )

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=2.5 * cm,
            rightMargin=2.5 * cm,
            topMargin=2.5 * cm,
            bottomMargin=2.5 * cm,
        )

        styles = getSampleStyleSheet()
        style_normal = styles["Normal"]
        style_normal.fontSize = 10
        style_normal.leading = 16

        style_h1 = ParagraphStyle(
            "H1", parent=styles["Heading1"],
            fontSize=16, textColor=colors.HexColor("#1f2328"),
            spaceAfter=6,
        )
        style_h2 = ParagraphStyle(
            "H2", parent=styles["Heading2"],
            fontSize=12, textColor=colors.HexColor("#3b82d4"),
            spaceBefore=12, spaceAfter=4,
        )
        style_disclaimer = ParagraphStyle(
            "Disclaimer", parent=styles["Normal"],
            fontSize=8, textColor=colors.HexColor("#57606a"),
            borderColor=colors.HexColor("#e5e7eb"),
            borderWidth=1, borderPadding=6,
            backColor=colors.HexColor("#f7f8fa"),
        )

        story = []

        # Cover header
        story.append(Paragraph("⚖️ AI Legal Aid Report", style_h1))
        story.append(Paragraph(f"<b>Case:</b> {case_title}", style_normal))
        story.append(Paragraph(f"<b>Client:</b> {client_name}", style_normal))
        story.append(Paragraph(
            f"<b>Generated:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} "
            f"| <b>Powered by:</b> IBM WatsonX granite-4-h-small",
            style_normal
        ))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb"), spaceAfter=12))

        # Body
        for line in report_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                story.append(Spacer(1, 6))
            elif stripped.startswith("## "):
                story.append(Paragraph(stripped[3:], style_h2))
            elif stripped.startswith("# "):
                story.append(Paragraph(stripped[2:], style_h1))
            elif stripped.startswith("- "):
                story.append(Paragraph(f"&bull; {stripped[2:]}", style_normal))
            elif stripped.startswith("⚠️"):
                story.append(Paragraph(stripped, style_disclaimer))
                story.append(Spacer(1, 6))
            else:
                story.append(Paragraph(stripped, style_normal))

        # Footer disclaimer
        story.append(Spacer(1, 16))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e5e7eb")))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "Made with IBM Bob · AI Legal Aid System · This report is for informational purposes only.",
            style_disclaimer
        ))

        doc.build(story)
        return True

    except Exception as exc:
        print(f"[ReportGenerator] PDF generation error: {exc}")
        return False
