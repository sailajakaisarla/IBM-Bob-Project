"""
Document Parser Agent — extracts text from uploaded files (PDF, DOCX, TXT, images)
and identifies the document category and key metadata.
"""

import os
import io


def extract_text(file_path: str, file_ext: str) -> str:
    """
    Extract plain text from a file based on its extension.

    Returns:
        Extracted text string (may be empty if extraction fails).
    """
    ext = file_ext.lower().lstrip(".")

    try:
        if ext == "txt":
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

        if ext == "pdf":
            try:
                import PyPDF2
                with open(file_path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    pages = [p.extract_text() or "" for p in reader.pages]
                    return "\n".join(pages)
            except Exception:
                return "[PDF text extraction failed]"

        if ext in ("docx", "doc"):
            try:
                from docx import Document
                doc = Document(file_path)
                return "\n".join(p.text for p in doc.paragraphs)
            except Exception:
                return "[DOCX text extraction failed]"

        if ext in ("png", "jpg", "jpeg", "gif", "webp"):
            # Basic metadata only — OCR would require tesseract
            try:
                from PIL import Image
                img = Image.open(file_path)
                return f"[Image file: {img.format}, {img.width}x{img.height}px, mode={img.mode}]"
            except Exception:
                return "[Image metadata extraction failed]"

    except Exception as exc:
        return f"[Extraction error: {exc}]"

    return "[Unsupported file type]"


def analyse_document(extracted_text: str, doc_category: str) -> dict:
    """
    Use the WatsonX agent to analyse a document.

    Returns:
        {
          "clauses":    list of {name, text, risk_level},
          "risk_score": "low"|"medium"|"high",
          "risk_score_numeric": int 0-100,
          "summary":    str,
          "flags":      list of str,
          "disclaimer": str,
        }
    """
    import json, re
    import watsonx_client

    if not extracted_text or len(extracted_text.strip()) < 50:
        return {
            "clauses": [],
            "risk_score": "low",
            "risk_score_numeric": 0,
            "summary": "Insufficient text to analyse.",
            "flags": [],
            "disclaimer": _disclaimer(),
        }

    system_prompt = f"""You are an expert legal document analyst specialising in {doc_category} documents.

Analyse the provided document text and:
1. Identify key legal clauses present (Salary, Termination, NDA, Non-Compete, Arbitration,
   Obligations, Penalties, Liability, Indemnity, IP Assignment, Governing Law, Notice Period,
   Probation, Benefits, Confidentiality, Payment Terms).
2. For each clause found, assess its risk level: "low", "medium", or "high".
3. Calculate an overall risk score (0-100) where:
   0-30 = Low Risk, 31-65 = Medium Risk, 66-100 = High Risk.
4. Identify specific red flags or concerning provisions.

OUTPUT a JSON block wrapped in ```json ... ``` with this EXACT structure:
{{
  "clauses": [
    {{"name": "clause name", "text": "brief excerpt or description", "risk_level": "low|medium|high", "explanation": "why this risk level"}}
  ],
  "risk_score": "low|medium|high",
  "risk_score_numeric": <integer 0-100>,
  "summary": "2-3 sentence document summary",
  "flags": ["flag 1", "flag 2"]
}}

Be precise and objective. Focus on legally significant clauses."""

    # Truncate long documents to fit context
    text_sample = extracted_text[:4000] if len(extracted_text) > 4000 else extracted_text

    try:
        reply = watsonx_client.chat(
            [{"role": "user", "content": f"Analyse this {doc_category} document:\n\n{text_sample}"}],
            system_prompt=system_prompt,
            max_tokens=1500,
            temperature=0.1,
        )

        match = re.search(r"```json\s*(\{.*?\})\s*```", reply, re.DOTALL)
        if match:
            result = json.loads(match.group(1))
            result["disclaimer"] = _disclaimer()
            return result
    except Exception:
        pass

    return {
        "clauses": [],
        "risk_score": "medium",
        "risk_score_numeric": 50,
        "summary": "Analysis could not be completed automatically.",
        "flags": [],
        "disclaimer": _disclaimer(),
    }


def _disclaimer():
    return ("⚠️ This document analysis is for informational purposes only and does not "
            "constitute legal advice. Consult a qualified lawyer before relying on this analysis.")
