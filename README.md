# AI Legal Aid Multi-Agent System (Production)

A full-stack, production-ready legal aid platform powered by **IBM WatsonX** (`ibm/granite-4-h-small`).

## Quick Start

```powershell
# 1. Install all dependencies
py -m pip install -r requirements.txt

# 2. Start the server (auto-opens browser)
.\start.ps1
# or
py app.py

# 3. Open http://127.0.0.1:5000
# Default admin: admin@legalaid.ai / Admin@1234
```

---

## Architecture

```
┌──────────────────── Frontend (index.html) ─────────────────────┐
│  Auth  │  Dashboard  │  Chat  │  Docs  │  Reports  │  Admin    │
└────────────────────────────┬───────────────────────────────────┘
                             │ REST API
┌────────────────────────────▼───────────────────────────────────┐
│              Flask Application  (app.py)                        │
│  /api/auth  /api/cases  /api/documents  /api/reports  /api/admin│
└──────────────┬────────────┬───────────────┬────────────────────┘
               │            │               │
    ┌──────────▼──┐  ┌──────▼──────┐  ┌────▼──────────┐
    │ Orchestrator│  │ Agents       │  │  Database      │
    │ (session    │  │              │  │  (SQLite/      │
    │  state)     │  │  Intake      │  │   SQLAlchemy)  │
    └─────────────┘  │  RAG         │  └───────────────┘
                     │  Compliance  │
                     │  Contract    │
                     │  Advice      │
                     │  Document    │
                     │  Report Gen  │
                     │  Assistant   │
                     └──────┬───────┘
                            │
                     ┌──────▼───────┐
                     │ IBM WatsonX  │
                     │ granite-4-h  │
                     │ eu-de region │
                     └──────────────┘
```

---

## Features

### Authentication
| Feature | Details |
|---------|---------|
| JWT Login/Signup | Email + password, bcrypt hashed |
| Google OAuth | Verify ID token from frontend |
| IBM Cloud SSO | Stub ready — add in `.env` |
| Forgot Password | 6-digit OTP (dev: shown in response, prod: email it) |
| Roles | `citizen` / `lawyer` / `admin` |

### Dashboard
- Stats cards: Active Cases, Documents, Reports, Notifications
- Quick Actions: New Consultation, Upload Document, Search Laws, Ask Legal Question
- Recent Cases with status/urgency badges
- Notification bell with dropdown

### Consultation Flow
1. **Consultation Form** — Case Type, Country, State, Language, Urgency, Description
2. **Guided Intake Chat** — Dynamic AI questions pre-filled with form context
3. **RAG Research** — Legal principles, statutes, precedents with citations
4. **Legal Advice** — Plain-language guidance, next steps, free resources, deadlines
5. **Compliance Check** — Auto-run PASS/FAIL/WARN against applicable laws
6. **Document Drafting** — Optional demand letter / cease & desist / complaint
7. **Report View** — Tabbed: Summary · Research · Advice · Compliance · Document

### Documents
- Upload PDF, DOCX, TXT, images (drag-and-drop or click)
- Auto text extraction
- **Document Analysis** — Clause extraction, Risk Score 0–100 (Low/Medium/High)
- **Contract Review** — Risky clause detection, severity, recommendations
- **Compliance Check** — Per-document regulatory compliance

### Reports
- AI-generated full legal aid report
- PDF download via reportlab
- Report history with search

### Legal Assistant
- Conversational Q&A on any legal topic
- Citations: `[Statute Name, Section X]` / `[Case Name (Year)]`
- Always includes legal disclaimer

### Search Laws
- RAG-enhanced legal research
- Filter by domain and jurisdiction

### Admin Panel
- Analytics dashboard (users, cases, documents, sessions)
- User management (enable/disable, change roles)
- Knowledge Base management (add statutes, judgments, regulations for RAG)

---

## Project Structure

```
.
├── app.py                        # Flask app factory (37 routes)
├── config.py                     # All configuration
├── models.py                     # SQLAlchemy models (User, Case, Document, Report, Notification, KnowledgeDoc)
├── auth.py                       # JWT, bcrypt, OTP, role decorators
├── orchestrator.py               # Session state machine
├── watsonx_client.py             # IBM WatsonX REST wrapper
├── agents/
│   ├── intake_agent.py           # Guided fact-gathering agent
│   ├── rag_agent.py              # RAG-enhanced legal research
│   ├── compliance_agent.py       # Compliance checker (PASS/FAIL/WARN)
│   ├── contract_review_agent.py  # Contract risk analysis
│   ├── document_parser_agent.py  # PDF/DOCX/image text extraction + analysis
│   ├── legal_assistant_agent.py  # Conversational Q&A with citations
│   ├── report_generator.py       # PDF report generator (reportlab)
│   ├── advice_agent.py           # Legal advice synthesiser
│   └── document_agent.py        # Legal document drafter
├── index.html                    # Full SPA (Auth + Dashboard + all panels)
├── requirements.txt
├── .env.example                  # Copy to .env and set credentials
├── start.bat                     # Windows batch launcher
├── start.ps1                     # PowerShell launcher (auto-opens browser)
└── README.md
```

---

## API Reference (37 routes)

### Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/signup` | Create account |
| POST | `/api/auth/login` | Login → JWT |
| POST | `/api/auth/google` | Google OAuth |
| POST | `/api/auth/forgot-password` | Send OTP |
| POST | `/api/auth/reset-password` | Reset with OTP |
| GET  | `/api/auth/me` | Get current user |

### Cases
| Method | Path | Description |
|--------|------|-------------|
| GET  | `/api/cases` | List cases (search, filter) |
| POST | `/api/cases` | Create case + start orchestrator |
| GET  | `/api/cases/<id>` | Get case with docs + reports |
| PATCH | `/api/cases/<id>` | Update case |
| DELETE | `/api/cases/<id>` | Delete case |
| POST | `/api/cases/<id>/chat` | Send message to agents |
| POST | `/api/cases/<id>/report` | Generate PDF report |

### Documents
| Method | Path | Description |
|--------|------|-------------|
| GET  | `/api/documents` | List documents |
| POST | `/api/documents/upload` | Upload file |
| GET  | `/api/documents/<id>` | Get document + text |
| POST | `/api/documents/<id>/analyse` | AI document analysis |
| POST | `/api/documents/<id>/contract-review` | Contract risk review |
| POST | `/api/documents/<id>/compliance` | Compliance check |
| DELETE | `/api/documents/<id>` | Delete |

### Reports / Admin / Assistant
See `app.py` for full route list.

---

## Environment Variables

```env
WATSONX_API_KEY=your_key
WATSONX_URL=https://eu-de.ml.cloud.ibm.com
WATSONX_PROJECT_ID=your_project_id
WATSONX_MODEL_ID=ibm/granite-4-h-small
SECRET_KEY=auto_generated_if_not_set
DATABASE_URL=sqlite:///legal_aid.db
UPLOAD_FOLDER=uploads
REPORTS_FOLDER=reports
GOOGLE_CLIENT_ID=optional_for_google_oauth
```

---

> **⚠️ Legal Disclaimer:** This system provides general legal information only and does not constitute legal advice. Always consult a qualified lawyer.
