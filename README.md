# Corvit AI Advisor

An intelligent, grounded academic and career advising platform for **Corvit Systems** (Founded 2000, 150,000+ alumni across Pakistan).

GitHub Repository: [https://github.com/araffay317/CORVIT-AI-ADVISOR.git](https://github.com/araffay317/CORVIT-AI-ADVISOR.git)

---

## 📌 Project Overview
**Corvit AI Advisor** provides prospective and enrolled students with authoritative, fact-checked academic advising. Built upon a curated 8-module local dataset of official Corvit knowledge, it guarantees zero hallucinations, verifiable citations, dual-model failover, and dynamic multi-factor course recommendations.

### Key Capabilities
* **Grounded Advisory Chat**: Answers student queries regarding IT curriculum, paid courses, NAVTTC free government training programs, physical lab hardware, fee structures, and batch timetables.
* **Dual-Model LLM Failover**:
  * **Primary Model**: `openai/gpt-oss-120b` (high reasoning capability).
  * **Fallback Model**: `llama-3.1-8b-instant` (automatic failover upon timeouts, rate limits, or connectivity issues).
  * **Safe Offline Response**: Displays verified Corvit campus contacts (Lahore, Islamabad, Rawalpindi, Peshawar) if both upstream models are unreachable.
* **Secondary Online Research**: Time-sensitive queries (`latest`, `2026 batch`, `upcoming`, `deadlines`) trigger secondary verification scoped strictly to official Corvit sources (`site:corvit.com`, `navttc.gov.pk`) with mandatory disclaimers.
* **Course Recommendation Engine**: Dynamically calculates personalized course suggestions from dataset curriculum chunks based on student education background, experience level, stated interests, and career ambitions (zero hardcoding).
* **Modern Responsive Frontend**: Dark glassmorphic interface with real-time markdown rendering, citation inspection, quick question chips, and campus directory modal.

---

## 🛠️ Technology Stack
* **Backend**: FastAPI, Uvicorn (Asynchronous Python 3.12)
* **LLM Engine**: Groq SDK (`openai/gpt-oss-120b` & `llama-3.1-8b-instant`)
* **Retrieval (RAG)**: In-memory TF-IDF vector space with category metadata filtering (`scikit-learn`, `numpy`)
* **Online Research**: DuckDuckGo search integration with domain filtering and in-memory TTL caching
* **Configuration**: `pydantic-settings`, `python-dotenv`
* **Testing**: `pytest`, `pytest-asyncio`
* **Frontend**: HTML5, Vanilla JavaScript, Vanilla CSS / Tailwind CSS, Google Fonts (`Outfit`, `Inter`)

---

## 📂 Knowledge Base Structure
The authoritative knowledge base is organized in `Dataset/` across 8 verified categories:
```text
Dataset/
├── admission/        # Admission application steps, campus contacts & guidelines
├── courses/          # 12 core professional IT course curricula & outlines
├── faq/              # 16 detailed student FAQs and common questions
├── fees/             # Fee structures, installment options & refund policies
├── general/          # Corvit history, mission, modes of training & head office
├── infrastructure/   # Physical equipment, Cisco racks & campus lab details
├── navttc/           # NAVTTC PM Youth Program free training & eligibility
└── timetable/        # Weekday/weekend morning/evening batch schedules
```

---

## 🚀 Local Development Setup

### 1. Prerequisites
* Python 3.12 (64-bit recommended)
* Git

### 2. Clone and Setup Environment
```bash
git clone https://github.com/araffay317/CORVIT-AI-ADVISOR.git
cd CORVIT-AI-ADVISOR

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.\.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Variables Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Inside `.env`, configure your server settings:
```env
# Groq API Key (Never commit this key to GitHub)
GROQ_API_KEY=your_groq_api_key_here

# Models
PRIMARY_MODEL=openai/gpt-oss-120b
FALLBACK_MODEL=llama-3.1-8b-instant

# Server Configuration
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
CORS_ORIGINS=http://localhost:5500,http://127.0.0.1:5500,http://localhost:3000,http://localhost:8000

# Feature Flags
ENABLE_ONLINE_RESEARCH=true
```

### 4. Run the FastAPI Backend Server
```bash
uvicorn backend.server:app --reload --host 127.0.0.1 --port 8000
```
Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

### 5. Open Frontend Locally
Open `index.html` in your browser or run a local static server (e.g. VS Code Live Server at port 5500).

---

## 📡 API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Root API status and version metadata |
| `GET` | `/health` | Application health and configured model indicators |
| `GET` | `/api/v1/health` | Health check alias |
| `GET` | `/api/v1/dataset-info` | Read-only inspection of the 8 dataset categories |
| `POST` | `/api/v1/chat` | Main advisory conversation endpoint with RAG + fallback |
| `POST` | `/api/v1/recommend-course` | Multi-factor course ranking and recommendations |

---

## 🧠 Architectural Design

### 1. Grounded RAG Flow
```
Student Query ──► TF-IDF Retriever (Dataset Chunks) ──► RAG Prompt Builder
                                                              │
                    ┌─────────────────────────────────────────┘
                    ▼
           Primary Model: openai/gpt-oss-120b
                    │ (Fails on timeout / 429 / 5xx)
                    ▼
           Fallback Model: llama-3.1-8b-instant
                    │ (Both fail)
                    ▼
           Offline Safe Response: Verified Corvit Admissions Contacts
```

### 2. Secondary Online Verification
When queries contain temporal terms (`latest`, `upcoming`, `2026 batch`, `deadline`, `starting date`), secondary web search investigates `site:corvit.com` and `navttc.gov.pk`. The result is appended to the RAG context with explicit disclaimers directing students to confirm details with Corvit Admissions.

### 3. Dynamic Course Recommender
Scores all parsed Corvit courses across 4 student parameters:
* Educational Background
* Experience Level (Beginner / Intermediate / Advanced)
* Interest Areas (Networking, AI, Cyber Security, Cloud, Python, Web)
* Career Ambitions (Network Engineer, AI Developer, etc.)
Returns top 2–3 recommendations with match scores, durations, outline scopes, reasons, and prerequisites.

---

## 🔒 Security Architecture
* **Server-Side API Key Isolation**: `GROQ_API_KEY` is loaded into Pydantic `SecretStr`. It is never serialized or displayed in `/health` or chat outputs.
* **Frontend Hygiene**: `index.html`, `style.css`, and `script.js` contain zero secrets or credentials.
* **Git Exclusions**: `.gitignore` strictly excludes `.env`, `*.env`, `.venv/`, `__pycache__/`, and `.pytest_cache/`.

---

## 🌐 Production Deployment Architecture

```text
┌──────────────────────────────────────┐       HTTPS        ┌──────────────────────────────────────┐
│  Netlify Static Frontend             │ ─────────────────► │  Python ASGI Backend                 │
│  - index.html, style.css, script.js  │    API Requests    │  - FastAPI, Uvicorn, RAG, Groq LLM  │
│  - Zero secrets stored in client     │                    │  - Hosted on Render, Railway, etc.   │
└──────────────────────────────────────┘                    └──────────────────────────────────────┘
```

### 1. Frontend Hosting (Netlify)
Netlify serves the client application directly from the repository root (`publish = "."` via `netlify.toml`).
Because Netlify is a static Jamstack host, it does not execute Python ASGI servers. To connect the frontend to your deployed backend:
* **Option A (Interactive UI - Recommended)**: Click the **⚙️ API URL** tab in the navigation header, enter your deployed FastAPI URL (e.g. `https://your-api.onrender.com`), test the `/health` endpoint, and click **Save & Apply**.
* **Option B (Global Window Config)**: Define `window.CORVIT_BACKEND_URL = "https://your-api.onrender.com";` in `index.html`.
* **Option C (Netlify Proxy Redirect)**: Uncomment the `[[redirects]]` section in `netlify.toml` to transparently route `/api/*` to your backend host.

### 2. Backend Hosting (Render, Railway, Fly.io, or VPS)
1. Deploy the FastAPI repository to your preferred Python ASGI host.
2. Configure environment variables in your hosting provider's dashboard:
   ```env
   GROQ_API_KEY=your_actual_groq_api_key
   PRIMARY_MODEL=openai/gpt-oss-120b
   FALLBACK_MODEL=llama-3.1-8b-instant
   CORS_ORIGINS=https://your-site.netlify.app,http://localhost:5500
   ENABLE_ONLINE_RESEARCH=true
   ```
3. Set the start command:
   ```bash
   uvicorn backend.server:app --host 0.0.0.0 --port $PORT
   ```

---

## 📦 Academic / Teacher Submission Package

To generate a clean ZIP archive for evaluation that strictly excludes virtual environments, real secrets, and cache folders:
```bash
.\.venv\Scripts\python.exe scripts/export_clean_submission.py
```
This utility automatically:
1. Verifies the SHA-256 integrity of all 8 original Dataset files.
2. Excludes `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, and `.git/`.
3. Preserves `.env.example`, documentation, test suite, and full source code.
4. Generates `CORVIT-AI-ADVISOR-SUBMISSION.zip` and audits it against credential leaks.

---

## 🧪 Automated Testing
Run the complete automated test suite:
```bash
.\.venv\Scripts\pytest.exe backend/tests/ -v
```
All 63 automated unit and integration tests validate the entire system across Phases 2, 3, 4, 5, Final Phase A, and Final Phase B.

