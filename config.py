"""
Central configuration for the AI Legal Aid Multi-Agent System.
Loads credentials from .env or environment variables.
"""

import os
import secrets
from dotenv import load_dotenv

load_dotenv()

# ── WatsonX ─────────────────────────────────────────────────────────────────
WATSONX_API_KEY    = os.getenv("WATSONX_API_KEY", "")
WATSONX_URL        = os.getenv("WATSONX_URL", "https://eu-de.ml.cloud.ibm.com")
WATSONX_PROJECT_ID = os.getenv("WATSONX_PROJECT_ID", "")
WATSONX_MODEL_ID   = os.getenv("WATSONX_MODEL_ID", "ibm/granite-4-h-small")

CHAT_ENDPOINT = f"{WATSONX_URL}/ml/v1/text/chat?version=2023-05-29"

DEFAULT_MAX_TOKENS  = 1024
DEFAULT_TEMPERATURE = 0.3

# ── Application ──────────────────────────────────────────────────────────────
SECRET_KEY      = os.getenv("SECRET_KEY", secrets.token_hex(32))
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
OTP_EXPIRY_MINS  = int(os.getenv("OTP_EXPIRY_MINS", "10"))

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///legal_aid.db")

UPLOAD_FOLDER   = os.getenv("UPLOAD_FOLDER", "uploads")
MAX_UPLOAD_MB   = int(os.getenv("MAX_UPLOAD_MB", "20"))
ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt", "png", "jpg", "jpeg", "gif", "webp"}

REPORTS_FOLDER  = os.getenv("REPORTS_FOLDER", "reports")

# ── Google OAuth (optional) ──────────────────────────────────────────────────
GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

# ── Legal Domains ────────────────────────────────────────────────────────────
LEGAL_DOMAINS = [
    "employment", "family", "housing", "criminal",
    "immigration", "consumer", "civil_rights", "business", "other"
]

URGENCY_LEVELS = ["high", "medium", "low"]

USER_ROLES = ["citizen", "lawyer", "admin"]
