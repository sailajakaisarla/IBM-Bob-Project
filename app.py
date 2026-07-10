"""
Flask REST API — AI Legal Aid Multi-Agent System (Production)

Endpoints grouped by blueprint:
  /api/auth        — login, signup, Google, forgot-password, OTP
  /api/dashboard   — stats, notifications
  /api/cases       — CRUD consultations + chat
  /api/documents   — upload, parse, analyse, contract-review, compliance
  /api/reports     — generate, download PDF
  /api/assistant   — conversational legal Q&A
  /api/admin       — user management, analytics (admin only)
  /api/health      — health check
"""

import json
import os
import uuid
import threading
from datetime import datetime, timezone

from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS

import config
from models import db, User, Case, Document, Report, Notification, KnowledgeDoc
from auth import (
    hash_password, check_password,
    create_token, login_required, role_required,
    generate_otp, verify_otp, is_valid_email,
)
from orchestrator import LegalAidOrchestrator

# ── App factory ───────────────────────────────────────────────────────────────

def create_app():
    app = Flask(__name__, static_folder=".", static_url_path="")
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Database
    app.config["SQLALCHEMY_DATABASE_URI"] = config.DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024
    app.config["SECRET_KEY"] = config.SECRET_KEY

    db.init_app(app)

    # Ensure upload / report directories exist
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(config.REPORTS_FOLDER, exist_ok=True)

    with app.app_context():
        db.create_all()
        _seed_admin()          # already inside app_context — no need to re-enter

    # In-memory active session orchestrators
    _sessions: dict[str, LegalAidOrchestrator] = {}
    _lock = threading.Lock()

    # ─────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────

    def _get_orch(sid):
        with _lock:
            return _sessions.get(sid)

    def _set_orch(sid, orch):
        with _lock:
            _sessions[sid] = orch

    def _notify(user_id, title, message, notif_type="info", link=None):
        n = Notification(user_id=user_id, title=title, message=message,
                         notif_type=notif_type, link=link)
        db.session.add(n)
        db.session.commit()

    # ─────────────────────────────────────────────────────────────────
    # Static UI
    # ─────────────────────────────────────────────────────────────────

    @app.route("/")
    @app.route("/index.html")
    def serve_ui():
        return send_from_directory(".", "index.html")

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "active_sessions": len(_sessions)})

    # ─────────────────────────────────────────────────────────────────
    # AUTH ROUTES
    # ─────────────────────────────────────────────────────────────────

    @app.route("/api/auth/signup", methods=["POST"])
    def signup():
        data = request.get_json(force=True) or {}
        email     = (data.get("email") or "").strip().lower()
        password  = data.get("password", "")
        full_name = (data.get("full_name") or "").strip()
        role      = data.get("role", "citizen")

        if not email or not password or not full_name:
            return jsonify({"error": "email, password, and full_name are required"}), 400
        if not is_valid_email(email):
            return jsonify({"error": "Invalid email address"}), 400
        if len(password) < 8:
            return jsonify({"error": "Password must be at least 8 characters"}), 400
        if role not in config.USER_ROLES:
            role = "citizen"
        if User.query.filter_by(email=email).first():
            return jsonify({"error": "An account with this email already exists"}), 409

        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role=role,
            is_verified=True,   # skip email verification for now
        )
        db.session.add(user)
        db.session.commit()

        _notify(user.id, "Welcome to Legal Aid AI! 🎉",
                "Your account has been created. Start your first consultation today.", "success")

        token = create_token(user.id, user.role)
        return jsonify({"token": token, "user": user.to_dict()}), 201


    @app.route("/api/auth/login", methods=["POST"])
    def login():
        data     = request.get_json(force=True) or {}
        email    = (data.get("email") or "").strip().lower()
        password = data.get("password", "")

        if not email or not password:
            return jsonify({"error": "email and password required"}), 400

        user = User.query.filter_by(email=email, provider="local").first()
        if not user or not user.password_hash:
            return jsonify({"error": "Invalid email or password"}), 401
        if not check_password(password, user.password_hash):
            return jsonify({"error": "Invalid email or password"}), 401
        if not user.is_active:
            return jsonify({"error": "Account is disabled"}), 403

        user.last_login = datetime.now(timezone.utc)
        db.session.commit()

        token = create_token(user.id, user.role)
        return jsonify({"token": token, "user": user.to_dict()})


    @app.route("/api/auth/google", methods=["POST"])
    def google_login():
        """Google OAuth — verify ID token from frontend."""
        data     = request.get_json(force=True) or {}
        id_token = data.get("id_token", "")
        if not id_token:
            return jsonify({"error": "id_token required"}), 400

        # Verify with Google
        try:
            import requests as req
            r = req.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}", timeout=10)
            r.raise_for_status()
            gdata = r.json()
            if gdata.get("aud") != config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_ID:
                return jsonify({"error": "Token audience mismatch"}), 401
            google_id = gdata["sub"]
            email     = gdata.get("email", "").lower()
            full_name = gdata.get("name", email)
            avatar    = gdata.get("picture", "")
        except Exception as exc:
            return jsonify({"error": f"Google token verification failed: {exc}"}), 401

        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(
                email=email, full_name=full_name,
                provider="google", provider_id=google_id,
                avatar_url=avatar, is_verified=True,
            )
            db.session.add(user)
            db.session.commit()
            _notify(user.id, "Welcome!", "Sign in with Google successful.", "success")
        else:
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()

        token = create_token(user.id, user.role)
        return jsonify({"token": token, "user": user.to_dict()})


    @app.route("/api/auth/forgot-password", methods=["POST"])
    def forgot_password():
        data  = request.get_json(force=True) or {}
        email = (data.get("email") or "").strip().lower()
        if not email:
            return jsonify({"error": "email required"}), 400

        user = User.query.filter_by(email=email).first()
        if not user:
            # Don't reveal if email exists
            return jsonify({"message": "If that email exists, an OTP has been sent."}), 200

        otp = generate_otp(user.id, "password_reset")
        # In production: send via email service. For now return in response (dev mode).
        return jsonify({
            "message": "OTP generated. In production this is sent via email.",
            "otp": otp,          # remove this line in production!
            "user_id": user.id,
        })


    @app.route("/api/auth/reset-password", methods=["POST"])
    def reset_password():
        data        = request.get_json(force=True) or {}
        user_id     = data.get("user_id", "")
        otp_code    = data.get("otp", "")
        new_password = data.get("new_password", "")

        if not all([user_id, otp_code, new_password]):
            return jsonify({"error": "user_id, otp, and new_password required"}), 400
        if len(new_password) < 8:
            return jsonify({"error": "Password must be at least 8 characters"}), 400

        if not verify_otp(user_id, otp_code, "password_reset"):
            return jsonify({"error": "Invalid or expired OTP"}), 400

        user = db.session.get(User, user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        user.password_hash = hash_password(new_password)
        db.session.commit()
        return jsonify({"message": "Password reset successful."})


    @app.route("/api/auth/me", methods=["GET"])
    @login_required
    def me():
        return jsonify({"user": g.current_user.to_dict()})


    # ─────────────────────────────────────────────────────────────────
    # DASHBOARD
    # ─────────────────────────────────────────────────────────────────

    @app.route("/api/dashboard", methods=["GET"])
    @login_required
    def dashboard():
        uid = g.current_user.id

        recent_cases  = Case.query.filter_by(user_id=uid).order_by(Case.updated_at.desc()).limit(5).all()
        pending_cases = Case.query.filter_by(user_id=uid, status="active").count()
        total_docs    = Document.query.filter_by(user_id=uid).count()
        total_reports = Report.query.filter_by(user_id=uid).count()
        unread_notifs = Notification.query.filter_by(user_id=uid, is_read=False).count()
        notifications = Notification.query.filter_by(user_id=uid).order_by(
            Notification.created_at.desc()).limit(10).all()

        return jsonify({
            "stats": {
                "recent_cases":    len(recent_cases),
                "pending_cases":   pending_cases,
                "total_documents": total_docs,
                "total_reports":   total_reports,
                "unread_notifications": unread_notifs,
            },
            "recent_cases":  [c.to_dict() for c in recent_cases],
            "notifications": [n.to_dict() for n in notifications],
        })


    @app.route("/api/notifications/<notif_id>/read", methods=["PATCH"])
    @login_required
    def mark_notification_read(notif_id):
        n = Notification.query.filter_by(id=notif_id, user_id=g.current_user.id).first_or_404()
        n.is_read = True
        db.session.commit()
        return jsonify({"ok": True})

    @app.route("/api/notifications/read-all", methods=["POST"])
    @login_required
    def mark_all_read():
        # synchronize_session=False is required for bulk UPDATE in SQLAlchemy 2.x
        Notification.query.filter_by(
            user_id=g.current_user.id, is_read=False
        ).update({"is_read": True}, synchronize_session=False)
        db.session.commit()
        return jsonify({"ok": True})

    # ─────────────────────────────────────────────────────────────────
    # CASES (Consultations)
    # ─────────────────────────────────────────────────────────────────

    @app.route("/api/cases", methods=["GET"])
    @login_required
    def list_cases():
        uid    = g.current_user.id
        search = request.args.get("q", "")
        status = request.args.get("status", "")
        domain = request.args.get("domain", "")

        query = Case.query.filter_by(user_id=uid)
        if search:
            query = query.filter(Case.title.ilike(f"%{search}%"))
        if status:
            query = query.filter_by(status=status)
        if domain:
            query = query.filter_by(case_type=domain)

        cases = query.order_by(Case.updated_at.desc()).all()
        return jsonify({"cases": [c.to_dict() for c in cases]})


    @app.route("/api/cases", methods=["POST"])
    @login_required
    def create_case():
        data = request.get_json(force=True) or {}
        required = ["case_type", "title"]
        for f in required:
            if not data.get(f):
                return jsonify({"error": f"{f} is required"}), 400

        case = Case(
            user_id     = g.current_user.id,
            title       = data["title"],
            case_type   = data["case_type"],
            country     = data.get("country", ""),
            state       = data.get("state", ""),
            language    = data.get("language", "English"),
            urgency     = data.get("urgency", "medium"),
            description = data.get("description", ""),
        )
        db.session.add(case)
        db.session.commit()

        # Create orchestrator and configure it
        orch = LegalAidOrchestrator()
        orch.set_app(app)
        orch.set_consultation_context(
            case_type   = data["case_type"],
            country     = data.get("country", ""),
            state       = data.get("state", ""),
            language    = data.get("language", "English"),
            urgency     = data.get("urgency", "medium"),
            description = data.get("description", ""),
        )
        _set_orch(case.id, orch)

        _notify(g.current_user.id, "New case opened",
                f"Case '{case.title}' is ready for consultation.", "info", f"/cases/{case.id}")

        return jsonify({"case": case.to_dict(brief=False)}), 201


    @app.route("/api/cases/<case_id>", methods=["GET"])
    @login_required
    def get_case(case_id):
        case = Case.query.filter_by(id=case_id, user_id=g.current_user.id).first_or_404()
        docs    = [d.to_dict() for d in case.documents.all()]
        reports = [r.to_dict() for r in case.reports.all()]
        return jsonify({"case": case.to_dict(brief=False), "documents": docs, "reports": reports})


    @app.route("/api/cases/<case_id>", methods=["PATCH"])
    @login_required
    def update_case(case_id):
        case = Case.query.filter_by(id=case_id, user_id=g.current_user.id).first_or_404()
        data = request.get_json(force=True) or {}
        for field in ("title", "status", "description", "urgency"):
            if field in data:
                setattr(case, field, data[field])
        # Explicitly set updated_at (onupdate callables are unreliable with SQLite)
        case.updated_at = datetime.now(timezone.utc)
        db.session.add(case)
        db.session.commit()
        return jsonify({"case": case.to_dict()})


    @app.route("/api/cases/<case_id>", methods=["DELETE"])
    @login_required
    def delete_case(case_id):
        case = Case.query.filter_by(id=case_id, user_id=g.current_user.id).first_or_404()
        db.session.delete(case)
        db.session.commit()
        with _lock:
            _sessions.pop(case_id, None)
        return jsonify({"deleted": case_id})


    @app.route("/api/cases/<case_id>/chat", methods=["POST"])
    @login_required
    def case_chat(case_id):
        case = Case.query.filter_by(id=case_id, user_id=g.current_user.id).first_or_404()
        data    = request.get_json(force=True) or {}
        message = (data.get("message") or "").strip()
        if not message:
            return jsonify({"error": "message required"}), 400

        # Restore or create orchestrator
        orch = _get_orch(case_id)
        if orch is None:
            orch = LegalAidOrchestrator()
            orch.set_app(app)
            orch.set_consultation_context(
                case_type   = case.case_type,
                country     = case.country or "",
                state       = case.state or "",
                language    = case.language or "English",
                urgency     = case.urgency or "medium",
                description = case.description or "",
            )
            # Restore history from DB
            if case.chat_history:
                orch.history = json.loads(case.chat_history)
            if case.intake_data:
                orch.intake = json.loads(case.intake_data)
                orch.research = case.research or ""
                orch.advice   = case.advice or ""
                orch.document = case.document or ""
                orch.stage    = case.stage or "intake"
            _set_orch(case_id, orch)

        try:
            result = orch.send(message)

            if result.get("trigger_analysis"):
                analysis = orch.run_analysis()
                reply = result["reply"] + "\n\n---\n\n" + analysis["reply"]
                stage = analysis["stage"]
                complete = analysis["complete"]
                outputs  = analysis.get("outputs")
            else:
                reply    = result["reply"]
                stage    = result["stage"]
                complete = result["complete"]
                outputs  = result.get("outputs")

            # Persist state — always add to session so SQLite tracks the dirty object
            case.stage        = orch.stage
            case.chat_history = json.dumps(orch.history)
            if orch.intake:
                case.intake_data = json.dumps(orch.intake)
            if orch.research:
                case.research = orch.research
            if orch.advice:
                case.advice = orch.advice
            if orch.document:
                case.document = orch.document
            if complete:
                case.status = "complete"
                _notify(g.current_user.id, "Consultation complete ✅",
                        f"Your legal analysis for '{case.title}' is ready.", "success", f"/cases/{case_id}")
            case.updated_at = datetime.now(timezone.utc)
            db.session.add(case)
            db.session.commit()

            return jsonify({
                "case_id":  case_id,
                "stage":    stage,
                "reply":    reply,
                "complete": complete,
                "outputs":  outputs,
            })

        except Exception as exc:
            return jsonify({"error": str(exc)}), 500


    # ─────────────────────────────────────────────────────────────────
    # DOCUMENTS
    # ─────────────────────────────────────────────────────────────────

    @app.route("/api/documents", methods=["GET"])
    @login_required
    def list_documents():
        uid      = g.current_user.id
        case_id  = request.args.get("case_id")
        category = request.args.get("category")
        query    = Document.query.filter_by(user_id=uid)
        if case_id:
            query = query.filter_by(case_id=case_id)
        if category:
            query = query.filter_by(doc_category=category)
        docs = query.order_by(Document.created_at.desc()).all()
        return jsonify({"documents": [d.to_dict() for d in docs]})


    @app.route("/api/documents/upload", methods=["POST"])
    @login_required
    def upload_document():
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file    = request.files["file"]
        case_id = request.form.get("case_id")
        category = request.form.get("category", "general")

        if not file.filename:
            return jsonify({"error": "Empty filename"}), 400

        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in config.ALLOWED_EXTENSIONS:
            return jsonify({"error": f"File type .{ext} not allowed"}), 400

        safe_name = f"{uuid.uuid4()}.{ext}"
        save_path = os.path.join(config.UPLOAD_FOLDER, safe_name)
        file.save(save_path)

        file_size = os.path.getsize(save_path)

        # Extract text
        from agents.document_parser_agent import extract_text
        extracted = extract_text(save_path, ext)

        doc = Document(
            user_id       = g.current_user.id,
            case_id       = case_id or None,
            filename      = safe_name,
            original_name = file.filename,
            file_type     = ext,
            file_size     = file_size,
            doc_category  = category,
            extracted_text= extracted,
        )
        db.session.add(doc)
        db.session.commit()

        return jsonify({"document": doc.to_dict()}), 201


    @app.route("/api/documents/<doc_id>", methods=["GET"])
    @login_required
    def get_document(doc_id):
        doc = Document.query.filter_by(id=doc_id, user_id=g.current_user.id).first_or_404()
        return jsonify({"document": doc.to_dict(include_text=True)})


    @app.route("/api/documents/<doc_id>/analyse", methods=["POST"])
    @login_required
    def analyse_document(doc_id):
        doc = Document.query.filter_by(id=doc_id, user_id=g.current_user.id).first_or_404()
        if not doc.extracted_text:
            return jsonify({"error": "No extracted text available for analysis"}), 400

        from agents.document_parser_agent import analyse_document as _analyse
        result = _analyse(doc.extracted_text, doc.doc_category)
        doc.analysis = json.dumps(result)
        db.session.commit()
        return jsonify({"analysis": result})


    @app.route("/api/documents/<doc_id>/contract-review", methods=["POST"])
    @login_required
    def contract_review(doc_id):
        doc = Document.query.filter_by(id=doc_id, user_id=g.current_user.id).first_or_404()
        if not doc.extracted_text:
            return jsonify({"error": "No text to review"}), 400

        data       = request.get_json(force=True) or {}
        party_role = data.get("party_role", "employee")
        jurisdiction = data.get("jurisdiction", "unspecified")

        from agents.contract_review_agent import run as contract_run
        result = contract_run(doc.extracted_text, party_role, jurisdiction)

        # Merge into document analysis
        existing = json.loads(doc.analysis) if doc.analysis else {}
        existing["contract_review"] = result
        doc.analysis = json.dumps(existing)
        db.session.commit()
        return jsonify({"contract_review": result})


    @app.route("/api/documents/<doc_id>/compliance", methods=["POST"])
    @login_required
    def compliance_check(doc_id):
        doc = Document.query.filter_by(id=doc_id, user_id=g.current_user.id).first_or_404()
        data         = request.get_json(force=True) or {}
        jurisdiction = data.get("jurisdiction", "unspecified")
        domain       = data.get("domain", doc.doc_category)
        scenario     = data.get("scenario", "Document compliance review")

        from agents.compliance_agent import run as compliance_run
        result = compliance_run(scenario, jurisdiction, domain, doc.extracted_text or "")

        existing = json.loads(doc.analysis) if doc.analysis else {}
        existing["compliance"] = result
        doc.analysis = json.dumps(existing)
        db.session.commit()
        return jsonify({"compliance": result})


    @app.route("/api/documents/<doc_id>", methods=["DELETE"])
    @login_required
    def delete_document(doc_id):
        doc = Document.query.filter_by(id=doc_id, user_id=g.current_user.id).first_or_404()
        try:
            path = os.path.join(config.UPLOAD_FOLDER, doc.filename)
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
        db.session.delete(doc)
        db.session.commit()
        return jsonify({"deleted": doc_id})


    # ─────────────────────────────────────────────────────────────────
    # REPORTS
    # ─────────────────────────────────────────────────────────────────

    @app.route("/api/reports", methods=["GET"])
    @login_required
    def list_reports():
        reports = Report.query.filter_by(user_id=g.current_user.id).order_by(Report.created_at.desc()).all()
        return jsonify({"reports": [r.to_dict() for r in reports]})


    @app.route("/api/cases/<case_id>/report", methods=["POST"])
    @login_required
    def generate_report(case_id):
        case = Case.query.filter_by(id=case_id, user_id=g.current_user.id).first_or_404()

        if not case.research or not case.advice:
            return jsonify({"error": "Case consultation must be complete before generating a report"}), 400

        intake_data = json.loads(case.intake_data) if case.intake_data else {}

        from agents.report_generator import generate_report_content, generate_pdf
        report_text = generate_report_content(
            case_title     = case.title,
            case_type      = case.case_type,
            jurisdiction   = f"{case.country or ''}, {case.state or ''}".strip(", ") or "unspecified",
            intake_data    = intake_data,
            research       = case.research,
            advice         = case.advice,
        )

        # Save report record
        report = Report(
            case_id     = case.id,
            user_id     = g.current_user.id,
            title       = f"Legal Aid Report — {case.title}",
            report_type = "full",
            content     = json.dumps({"text": report_text}),
        )
        db.session.add(report)
        db.session.flush()  # get report.id

        # Generate PDF
        pdf_name = f"report_{report.id}.pdf"
        pdf_path = os.path.join(config.REPORTS_FOLDER, pdf_name)
        ok = generate_pdf(report_text, case.title, g.current_user.full_name, pdf_path)
        if ok:
            report.file_path = pdf_name

        db.session.commit()

        _notify(g.current_user.id, "Report ready 📄",
                f"Your report for '{case.title}' is ready to download.", "success")

        return jsonify({
            "report":   report.to_dict(),
            "content":  report_text,
            "pdf_ready": ok,
        }), 201


    @app.route("/api/reports/<report_id>/download", methods=["GET"])
    @login_required
    def download_report(report_id):
        report = Report.query.filter_by(id=report_id, user_id=g.current_user.id).first_or_404()
        if not report.file_path:
            return jsonify({"error": "PDF not available"}), 404
        return send_from_directory(
            os.path.abspath(config.REPORTS_FOLDER),
            report.file_path,
            as_attachment=True,
            download_name=f"legal_aid_report_{report_id[:8]}.pdf",
        )


    @app.route("/api/reports/<report_id>", methods=["DELETE"])
    @login_required
    def delete_report(report_id):
        report = Report.query.filter_by(id=report_id, user_id=g.current_user.id).first_or_404()
        try:
            if report.file_path:
                p = os.path.join(config.REPORTS_FOLDER, report.file_path)
                if os.path.exists(p):
                    os.remove(p)
        except Exception:
            pass
        db.session.delete(report)
        db.session.commit()
        return jsonify({"deleted": report_id})


    # ─────────────────────────────────────────────────────────────────
    # LEGAL ASSISTANT (Conversational Q&A)
    # ─────────────────────────────────────────────────────────────────

    @app.route("/api/assistant/chat", methods=["POST"])
    @login_required
    def assistant_chat():
        data     = request.get_json(force=True) or {}
        messages = data.get("messages", [])
        context  = data.get("context", {})

        if not messages:
            return jsonify({"error": "messages required"}), 400

        from agents.legal_assistant_agent import chat as assistant_chat_fn
        reply = assistant_chat_fn(messages, context)
        return jsonify({"reply": reply})


    # ─────────────────────────────────────────────────────────────────
    # ADMIN ROUTES
    # ─────────────────────────────────────────────────────────────────

    @app.route("/api/admin/users", methods=["GET"])
    @login_required
    @role_required("admin")
    def admin_list_users():
        search = request.args.get("q", "")
        role   = request.args.get("role", "")
        query  = User.query
        if search:
            query = query.filter(
                (User.email.ilike(f"%{search}%")) | (User.full_name.ilike(f"%{search}%"))
            )
        if role:
            query = query.filter_by(role=role)
        users = query.order_by(User.created_at.desc()).all()
        return jsonify({"users": [u.to_dict() for u in users]})


    @app.route("/api/admin/users/<user_id>", methods=["PATCH"])
    @login_required
    @role_required("admin")
    def admin_update_user(user_id):
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        data = request.get_json(force=True) or {}
        for field in ("role", "is_active", "is_verified"):
            if field in data:
                setattr(user, field, data[field])
        db.session.commit()
        return jsonify({"user": user.to_dict()})


    @app.route("/api/admin/analytics", methods=["GET"])
    @login_required
    @role_required("admin")
    def admin_analytics():
        return jsonify({
            "total_users":     User.query.count(),
            "total_cases":     Case.query.count(),
            "active_cases":    Case.query.filter_by(status="active").count(),
            "complete_cases":  Case.query.filter_by(status="complete").count(),
            "total_documents": Document.query.count(),
            "total_reports":   Report.query.count(),
            "active_sessions": len(_sessions),
            "users_by_role": {
                "citizen": User.query.filter_by(role="citizen").count(),
                "lawyer":  User.query.filter_by(role="lawyer").count(),
                "admin":   User.query.filter_by(role="admin").count(),
            },
        })


    @app.route("/api/admin/knowledge", methods=["GET"])
    @login_required
    @role_required("admin")
    def admin_list_knowledge():
        docs = KnowledgeDoc.query.order_by(KnowledgeDoc.created_at.desc()).all()
        return jsonify({"docs": [d.to_dict() for d in docs]})


    @app.route("/api/admin/knowledge", methods=["POST"])
    @login_required
    @role_required("admin")
    def admin_add_knowledge():
        data = request.get_json(force=True) or {}
        if not data.get("title") or not data.get("content"):
            return jsonify({"error": "title and content required"}), 400
        doc = KnowledgeDoc(
            title        = data["title"],
            domain       = data.get("domain"),
            jurisdiction = data.get("jurisdiction"),
            doc_type     = data.get("doc_type", "statute"),
            content      = data["content"],
            source_url   = data.get("source_url"),
            added_by     = g.current_user.id,
        )
        db.session.add(doc)
        db.session.commit()
        return jsonify({"doc": doc.to_dict()}), 201


    @app.route("/api/admin/knowledge/<doc_id>", methods=["DELETE"])
    @login_required
    @role_required("admin")
    def admin_delete_knowledge(doc_id):
        # get_or_404 is deprecated in SQLAlchemy 2.x — use db.session.get + manual 404
        doc = db.session.get(KnowledgeDoc, doc_id)
        if doc is None:
            return jsonify({"error": "Knowledge document not found"}), 404
        db.session.delete(doc)
        db.session.commit()
        return jsonify({"deleted": doc_id})

    return app


# ── Seeder ────────────────────────────────────────────────────────────────────

def _seed_admin():
    """
    Create a default admin account if none exists.
    Must be called from within an active app_context (no re-entry needed).
    """
    if not User.query.filter_by(role="admin").first():
        admin = User(
            email         = "admin@legalaid.ai",
            password_hash = hash_password("Admin@1234"),
            full_name     = "System Administrator",
            role          = "admin",
            is_verified   = True,
        )
        db.session.add(admin)
        db.session.commit()


# ── Entry point ───────────────────────────────────────────────────────────────

application = create_app()

if __name__ == "__main__":
    print("🏛️  AI Legal Aid System (Production) starting…")
    print("   ✅ Open: http://127.0.0.1:5000")
    print("   🔑 Default admin: admin@legalaid.ai / Admin@1234")
    application.run(debug=False, host="127.0.0.1", port=5000, threaded=True)
