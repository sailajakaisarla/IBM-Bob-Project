"""
SQLAlchemy database models for the Legal Aid system.
"""

import uuid
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def _uuid():
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc)


# ── Users ─────────────────────────────────────────────────────────────────────

class User(db.Model):
    __tablename__ = "users"

    id            = db.Column(db.String(36), primary_key=True, default=_uuid)
    email         = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)   # nullable for OAuth-only
    full_name     = db.Column(db.String(255), nullable=False)
    role          = db.Column(db.String(20), nullable=False, default="citizen")  # citizen|lawyer|admin
    provider      = db.Column(db.String(20), default="local")   # local|google|ibm
    provider_id   = db.Column(db.String(255), nullable=True)
    is_active     = db.Column(db.Boolean, default=True)
    is_verified   = db.Column(db.Boolean, default=False)
    avatar_url    = db.Column(db.String(512), nullable=True)
    created_at    = db.Column(db.DateTime, default=_now)
    last_login    = db.Column(db.DateTime, nullable=True)

    # Relationships
    cases         = db.relationship("Case", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    documents     = db.relationship("Document", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    notifications = db.relationship("Notification", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    otps          = db.relationship("OTPRecord", backref="user", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "provider": self.provider,
            "is_verified": self.is_verified,
            "avatar_url": self.avatar_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


# ── OTP Records ───────────────────────────────────────────────────────────────

class OTPRecord(db.Model):
    __tablename__ = "otp_records"

    id         = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id    = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    otp_code   = db.Column(db.String(10), nullable=False)
    purpose    = db.Column(db.String(30), default="password_reset")  # password_reset|verify_email
    expires_at = db.Column(db.DateTime, nullable=False)
    used       = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=_now)


# ── Cases (Consultations) ─────────────────────────────────────────────────────

class Case(db.Model):
    __tablename__ = "cases"

    id           = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id      = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    title        = db.Column(db.String(255), nullable=False)
    case_type    = db.Column(db.String(50), nullable=False)   # legal domain
    country      = db.Column(db.String(100), nullable=True)
    state        = db.Column(db.String(100), nullable=True)
    language     = db.Column(db.String(50), default="English")
    urgency      = db.Column(db.String(20), default="medium")
    description  = db.Column(db.Text, nullable=True)
    status       = db.Column(db.String(30), default="active")  # active|pending|complete|archived
    intake_data  = db.Column(db.Text, nullable=True)    # JSON string
    research     = db.Column(db.Text, nullable=True)
    advice       = db.Column(db.Text, nullable=True)
    document     = db.Column(db.Text, nullable=True)
    chat_history = db.Column(db.Text, nullable=True)    # JSON string
    stage        = db.Column(db.String(30), default="consultation_form")
    created_at   = db.Column(db.DateTime, default=_now)
    updated_at   = db.Column(db.DateTime, default=_now)

    # Relationships
    # foreign_keys specified to remove ambiguity (Document has both user_id and case_id FKs pointing to different tables)
    documents    = db.relationship("Document", foreign_keys="Document.case_id", backref="case", lazy="dynamic")
    reports      = db.relationship("Report", backref="case", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self, brief=True):
        d = {
            "id": self.id,
            "title": self.title,
            "case_type": self.case_type,
            "country": self.country,
            "state": self.state,
            "language": self.language,
            "urgency": self.urgency,
            "status": self.status,
            "stage": self.stage,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if not brief:
            import json
            d["description"]  = self.description
            d["intake_data"]  = json.loads(self.intake_data) if self.intake_data else None
            d["research"]     = self.research
            d["advice"]       = self.advice
            d["document"]     = self.document
            d["chat_history"] = json.loads(self.chat_history) if self.chat_history else []
        return d


# ── Documents ─────────────────────────────────────────────────────────────────

class Document(db.Model):
    __tablename__ = "documents"

    id           = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id      = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    case_id      = db.Column(db.String(36), db.ForeignKey("cases.id"), nullable=True)
    filename     = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    file_type    = db.Column(db.String(20), nullable=False)
    file_size    = db.Column(db.Integer, nullable=True)
    doc_category = db.Column(db.String(50), default="general")  # contract|payslip|notice|offer_letter|agreement|general
    extracted_text = db.Column(db.Text, nullable=True)
    analysis     = db.Column(db.Text, nullable=True)  # JSON: clauses, risk_score
    created_at   = db.Column(db.DateTime, default=_now)

    def to_dict(self, include_text=False):
        import json
        d = {
            "id": self.id,
            "case_id": self.case_id,
            "filename": self.filename,
            "original_name": self.original_name,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "doc_category": self.doc_category,
            "has_analysis": self.analysis is not None,
            "analysis": json.loads(self.analysis) if self.analysis else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_text:
            d["extracted_text"] = self.extracted_text
        return d


# ── Reports ───────────────────────────────────────────────────────────────────

class Report(db.Model):
    __tablename__ = "reports"

    id          = db.Column(db.String(36), primary_key=True, default=_uuid)
    case_id     = db.Column(db.String(36), db.ForeignKey("cases.id"), nullable=False)
    user_id     = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    title       = db.Column(db.String(255), nullable=False)
    report_type = db.Column(db.String(30), default="full")  # full|summary|document_review
    file_path   = db.Column(db.String(512), nullable=True)
    content     = db.Column(db.Text, nullable=True)  # JSON report content
    created_at  = db.Column(db.DateTime, default=_now)

    def to_dict(self):
        return {
            "id": self.id,
            "case_id": self.case_id,
            "title": self.title,
            "report_type": self.report_type,
            "file_path": self.file_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ── Notifications ─────────────────────────────────────────────────────────────

class Notification(db.Model):
    __tablename__ = "notifications"

    id         = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id    = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    title      = db.Column(db.String(255), nullable=False)
    message    = db.Column(db.Text, nullable=True)
    notif_type = db.Column(db.String(30), default="info")  # info|success|warning|error
    is_read    = db.Column(db.Boolean, default=False)
    link       = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=_now)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "notif_type": self.notif_type,
            "is_read": self.is_read,
            "link": self.link,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ── RAG Knowledge Base ────────────────────────────────────────────────────────

class KnowledgeDoc(db.Model):
    __tablename__ = "knowledge_docs"

    id           = db.Column(db.String(36), primary_key=True, default=_uuid)
    title        = db.Column(db.String(255), nullable=False)
    domain       = db.Column(db.String(50), nullable=True)
    jurisdiction = db.Column(db.String(100), nullable=True)
    doc_type     = db.Column(db.String(50), default="statute")  # statute|judgment|regulation|guideline
    content      = db.Column(db.Text, nullable=False)
    source_url   = db.Column(db.String(512), nullable=True)
    added_by     = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    created_at   = db.Column(db.DateTime, default=_now)

    def to_dict(self, brief=True):
        d = {
            "id": self.id,
            "title": self.title,
            "domain": self.domain,
            "jurisdiction": self.jurisdiction,
            "doc_type": self.doc_type,
            "source_url": self.source_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if not brief:
            d["content"] = self.content
        return d
