"""
Authentication utilities — JWT tokens, password hashing, OTP generation.
"""

import re
import secrets
import string
from datetime import datetime, timedelta, timezone
from functools import wraps

import bcrypt
import jwt
from flask import request, jsonify, g

import config
from models import db, User, OTPRecord


# ── Password ─────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def check_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_token(user_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=config.JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, config.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"])


# ── Decorators ────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        token = auth.split(" ", 1)[1]
        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        user = db.session.get(User, payload["sub"])
        if not user or not user.is_active:
            return jsonify({"error": "User not found or inactive"}), 401
        g.current_user = user
        g.token_role   = payload.get("role", user.role)
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    """Decorator that requires login_required to run first."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, "current_user"):
                return jsonify({"error": "Authentication required"}), 401
            if g.current_user.role not in roles:
                return jsonify({"error": f"Requires role: {', '.join(roles)}"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


# ── OTP ───────────────────────────────────────────────────────────────────────

def generate_otp(user_id: str, purpose: str = "password_reset") -> str:
    # Invalidate any existing unused OTPs for same user/purpose
    OTPRecord.query.filter_by(user_id=user_id, purpose=purpose, used=False).delete()

    code = "".join(secrets.choice(string.digits) for _ in range(6))
    expires = datetime.now(timezone.utc) + timedelta(minutes=config.OTP_EXPIRY_MINS)
    otp = OTPRecord(user_id=user_id, otp_code=code, purpose=purpose, expires_at=expires)
    db.session.add(otp)
    db.session.commit()
    return code


def verify_otp(user_id: str, code: str, purpose: str = "password_reset") -> bool:
    now = datetime.now(timezone.utc)
    record = OTPRecord.query.filter_by(
        user_id=user_id, otp_code=code, purpose=purpose, used=False
    ).first()
    if not record:
        return False
    # Make expires_at timezone-aware if needed
    exp = record.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < now:
        return False
    record.used = True
    db.session.commit()
    return True


# ── Email validation ──────────────────────────────────────────────────────────

def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))
