# Gilberto — AI Legal Agent System (v3)

> *"Technology as a reasoning empowerment tool — not a brain substitute."*

---

## The Philosophy Behind Gilberto

I built Gilberto for young lawyers who want to use technology intelligently — not to replace their legal judgment, but to sharpen it.

The legal profession demands something that no AI system can replicate: the ability to understand context, exercise discretion, assume professional responsibility, and apply ethics under uncertainty. Gilberto does not pretend otherwise. What it does do is give you a structured, rigorous second opinion — powered by 20 specialized agents trained on Brazilian contract law — so that nothing slips through the cracks.

**The core belief:** a lawyer who uses AI critically is more dangerous than any AI system alone.

---

## Two Ways to Use Gilberto

### Way 1 — AI as a Verification Layer (Recommended for Complex Contracts)

```
YOU analyze the contract first
        ↓
Upload to Gilberto
        ↓
Gilberto runs its 20-agent cluster analysis
        ↓
YOU compare outputs against your own analysis
        ↓
Did Gilberto find something you missed?
Did you find something Gilberto missed?
        ↓
Final judgment is YOURS
```

This is the approach I personally recommend for complex contracts — shareholders agreements, M&A documents, long-term service agreements — where human judgment is irreplaceable but the volume of clauses is large enough that something can always be missed. Use Gilberto as a checklist engine with legal depth, not as your primary analyst.

---

### Way 2 — AI as a First-Pass Analyst (Useful for High Volume)

```
Upload contract directly
        ↓
Gilberto runs the full analysis loop
        ↓
YOU critically evaluate every output
Question every finding. Disagree where you know better.
        ↓
Submit feedback → Gilberto routes it to the correct cluster
        ↓
Revised analysis
        ↓
Final judgment is YOURS
```

This works well when you are processing a high volume of contracts and need a structured starting point. The key word is **critically** — never accept the output passively. The feedback loop exists precisely for this: push back on Gilberto's findings and force it to defend or revise them.

---

### What Gilberto Is Not

- It is **not a substitute for legal advice**
- It is **not a licensed lawyer**
- It is **not always right** — it will miss things, and you are the safeguard
- It is **not designed to be used passively** — the feedback loop is not optional, it is the point

---

## System Overview

Gilberto is a multi-agent hierarchical cluster system for Brazilian legal document analysis. It is powered by Maritaca AI (Sabiá-4) — a Brazilian large language model with deep knowledge of Brazilian law — and deployed on Railway.

```
┌─────────────────────────────────────────────────────────────┐
│                      Railway Platform                        │
│                                                              │
│  ┌──────────────────────┐   ┌──────────────────────────┐   │
│  │   Frontend Service   │   │    Backend Service        │   │
│  │   React + Nginx      │──▶│    FastAPI + CrewAI       │   │
│  │   Port 80            │   │    Port 8000              │   │
│  └──────────────────────┘   └────────────┬─────────────┘   │
└────────────────────────────────────────── ┼ ───────────────┘
                                            │
                                 ┌──────────▼──────────┐
                                 │   Maritaca AI API    │
                                 │   (Sabiá-4 model)    │
                                 └─────────────────────┘
```

---

## Multi-Agent Cluster Architecture (v3)

### Design Principle

> Agents vote **only within their cluster** (same domain knowledge).
> Cross-cluster synthesis happens **only at Cluster Manager level**.
> The Master Manager applies the Passo 11 risk formula across all 5 cluster summaries.

This eliminates a critical epistemic flaw: a LGPD Specialist should never score a Guarantee Clause analysis. A Penalty Specialist should never evaluate an Anti-Corruption clause. Domain-bounded voting means every score is epistemically valid.

### Sequential Execution Flow

```
USER uploads document
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│                       ROUND N                               │
│                                                             │
│  CLUSTER 1 — Foundation (Passos 0–2)                        │
│  ├── Contract Classifier          → analysis → JSON         │
│  ├── Document Integrity Auditor   → analysis → JSON         │
│  ├── Parties & Authority Validator→ analysis → JSON         │
│  └── Transactional Context Analyst→ analysis → JSON         │
│       ↓ intra-cluster vote (domain-valid scores only)       │
│       ↓ Cluster Manager 1 synthesizes                       │
│       ↓ summary passed to Cluster 2                         │
│                                                             │
│  CLUSTER 2 — Financial Risk (Passos 3–5)                    │
│  ├── Object Scope Specialist      → analysis → JSON         │
│  ├── Price & Payment Analyst      → analysis → JSON         │
│  ├── Penalty & Sanctions Spec.    → analysis → JSON         │
│  └── Financial Exposure Quantifier→ analysis → JSON         │
│       ↓ intra-cluster vote                                  │
│       ↓ Cluster Manager 2 synthesizes                       │
│       ↓ summaries 1+2 passed to Cluster 3                   │
│                                                             │
│  CLUSTER 3 — Mitigation & Exit (Passos 6–7)                 │
│  ├── Guarantee Specialist         → analysis → JSON         │
│  ├── Term & Renewal Analyst       → analysis → JSON         │
│  ├── Termination Strategist       → analysis → JSON         │
│  └── Hardship & Exceptio Spec.    → analysis → JSON         │
│       ↓ intra-cluster vote                                  │
│       ↓ Cluster Manager 3 synthesizes                       │
│       ↓ summaries 1+2+3 passed to Cluster 4                 │
│                                                             │
│  CLUSTER 4 — Compliance (Passos 8–10)                       │
│  ├── LGPD & Data Protection Spec. → analysis → JSON         │
│  ├── Anti-Corruption & Regulatory → analysis → JSON         │
│  ├── IP & Special Obligations     → analysis → JSON         │
│  └── General Provisions Auditor   → analysis → JSON         │
│       ↓ intra-cluster vote                                  │
│       ↓ Cluster Manager 4 synthesizes                       │
│       ↓ ALL summaries 1+2+3+4 passed to Cluster 5           │
│                                                             │
│  CLUSTER 5 — Strategy & Adversarial (Passo 9 + cross)       │
│  ├── Dispute Resolution Specialist→ analysis → JSON         │
│  ├── Negotiation Strategist       → analysis → JSON         │
│  ├── Devil's Advocate             → attacks ALL clusters    │
│  └── Risk Aggregation Specialist  → pre-applies Passo 11    │
│       ↓ intra-cluster vote                                  │
│       ↓ Cluster Manager 5 synthesizes                       │
│                                                             │
│  MASTER MANAGER                                             │
│  └── Applies Passo 11 formula across all 5 summaries        │
│       → Final synthesis → User                              │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
YOU review the analysis critically
        │
    ┌───┴────┐
    ▼        ▼
Feedback   Accept
    │
    ▼
Master Manager routes feedback to correct cluster
Feedback Advocate injected into target cluster
Target cluster + Cluster 5 re-run
Master Manager re-synthesizes
```

**26 LLM calls per round** (20 agents + 5 cluster managers + 1 master manager).

---

## Agent Roster (20 Agents)

### Cluster 1 — Foundation (Passos 0–2)
| Agent | Owns |
|-------|------|
| Contract Classifier | Passo 1.3 — nominado/atípico, negociado/adesão, sinalagmático |
| Document Integrity Auditor | Passo 1 — blank fields, missing annexes, cross-references |
| Parties & Authority Validator | Passo 2 — representation authority, alçadas, interveners |
| Transactional Context Analyst | Passo 0 — counterparty, sector regulation, CADE, integration |

### Cluster 2 — Financial Risk (Passos 3–5)
| Agent | Owns |
|-------|------|
| Object Scope Specialist | Passo 3 — object precision, scope delimitation |
| Price & Payment Analyst | Passo 4 — indexation, Lei 9.069/95 art. 28, pro rata die |
| Penalty & Sanctions Specialist | Passo 5 — CC art. 412 ceiling, moratória vs. compensatória |
| Financial Exposure Quantifier | Cross-Passo financial modeling and worst-case exposure |

### Cluster 3 — Mitigation & Exit (Passos 6–7)
| Agent | Owns |
|-------|------|
| Guarantee Specialist | Passo 6 — fiança, alienação fiduciária, penhor |
| Term & Renewal Analyst | Passo 7.1 — vigência, renovação automática, notice periods |
| Termination Strategist | Passo 7.2 — rescisão, resilição, cure periods, CC art. 473 |
| Hardship & Exceptio Specialist | Passos 7.3–7.4 — CC arts. 317, 476, 478–480, MAC |

### Cluster 4 — Compliance (Passos 8–10)
| Agent | Owns |
|-------|------|
| LGPD & Data Protection Specialist | LGPD full audit — DPA, DPO, ANPD Res. 2/2022 |
| Anti-Corruption & Regulatory Specialist | Lei 12.846/2013, FCPA, UKBA, sector regulation |
| IP & Special Obligations Specialist | Lei 9.610/98 art. 11, non-compete indemnity, exclusivity |
| General Provisions Auditor | Passo 10 — merger clause, severability, e-signature |

### Cluster 5 — Strategy & Adversarial (Passo 9 + cross-cluster)
| Agent | Owns |
|-------|------|
| Dispute Resolution Specialist | Passo 9 — forum election, arbitration clause quality |
| Negotiation Strategist | Ranked redlines with market benchmarks across ALL clusters |
| Devil's Advocate | Attacks ALL cluster outputs — finds the critical gap no one addressed |
| Risk Aggregation Specialist | Pre-applies Passo 11 formula before Master Manager |

### Master Manager
| Role | Function |
|------|----------|
| Master Legal Partner | Applies Passo 11 across all 5 cluster summaries — final synthesis |

---

## Feedback Routing (Human in the Loop)

When you submit feedback, the Master Manager classifies it and routes it intelligently — only the relevant cluster re-runs, not the entire system:

```
"The non-compete clause was not analyzed deeply enough"
        → classified as Cluster 4 (Compliance — IP & Special Obligations)
        → Feedback Advocate injected into Cluster 4
        → Cluster 4 re-runs with your concern
        → Cluster 5 (adversarial) always re-runs after any feedback
        → Master Manager re-synthesizes
        → You see the updated analysis
```

This is the mechanism that keeps you in control. Use it aggressively.

---

## Passo 11 Risk Formula (Hardcoded — Never Subjective)

```
CRITICAL:   ≥1 critical risk in any cluster
            OR absent clause with immediate patrimonial risk
            OR blank field in object, price, or term

RELEVANT:   No critical + (≥2 relevant risks
            OR 1 relevant risk in high-impact clause)

ACCEPTABLE: No critical + at most 1 relevant risk in limited-impact clause
```

Every risk classification includes the **exact activation criterion** — fully auditable. No subjective drift.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Maritaca AI Sabiá-4 (OpenAI-compatible API) |
| Agent Framework | CrewAI |
| Backend | FastAPI (Python 3.11) |
| Streaming | Server-Sent Events (SSE) |
| Frontend | React 18 + Vite |
| Styling | Tailwind CSS |
| Deployment | Railway (two services) |

---

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 20+
- Maritaca AI API key — get yours at [plataforma.maritaca.ai](https://plataforma.maritaca.ai)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create env file — never commit this
cp ../.env.example .env
# Edit .env and set MARITACA_API_KEY

uvicorn main:app --reload --port 8000
```

Verify your API key is loaded correctly:
```bash
python -c "from config import settings; print('KEY:', settings.MARITACA_API_KEY[:8], '...')"
```

Backend: http://localhost:8000
API docs: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
echo "VITE_API_URL=http://localhost:8000" > .env
npm run dev
```

Frontend: http://localhost:3000

---

## Railway Deployment

### Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "v3: 20-agent cluster architecture"
git remote add origin https://github.com/Santos123-Sys/Gilberto---Legal-agentic--system.git
git branch -M main
git push -u origin main
```

### Step 2 — Deploy Backend Service

1. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
2. Select your repository
3. Click the service → **Settings** → **Root Directory**: `backend`
4. **Variables** tab → add:

```
MARITACA_API_KEY    = mk-your-key-here
MARITACA_MODEL      = sabia-4
MAX_AGENTS          = 20
MAX_ROUNDS          = 5
CORS_ORIGINS        = *
PORT                = 8000
```

5. Deploy → copy the generated backend URL

### Step 3 — Deploy Frontend Service

1. New Service → GitHub Repo → same repo
2. **Settings** → **Root Directory**: `frontend`
3. **Variables** → add:

```
VITE_API_URL = https://your-backend-url.railway.app
```

4. Deploy → copy the generated frontend URL

### Step 4 — Lock CORS

Back to backend **Variables**:

```
CORS_ORIGINS = https://your-frontend-url.railway.app
```

Redeploy backend.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/sessions` | Create session |
| `POST` | `/api/sessions/{id}/start` | Upload document + start cluster analysis |
| `GET` | `/api/sessions/{id}/stream` | SSE stream — all 26 agent events per round |
| `GET` | `/api/sessions/{id}/status` | Current session status |
| `GET` | `/api/sessions/{id}/results` | Full results with all cluster summaries |
| `POST` | `/api/sessions/{id}/feedback` | Submit feedback → routes to correct cluster |
| `POST` | `/api/sessions/{id}/accept` | Accept final analysis |
| `GET` | `/api/health` | Health check |

---

## Project Structure

```
gilberto-legal-agent/
├── backend/
│   ├── main.py                      # FastAPI app + all endpoints
│   ├── debate_engine.py             # Cluster orchestration engine
│   ├── config.py                    # Settings from environment
│   ├── agents/
│   │   ├── cluster_definitions.py   # 20 agents + 5 cluster managers + Master Manager
│   │   └── prompts.py               # Brazilian workflow checklists + market parameters
│   ├── models/
│   │   └── schemas.py               # Pydantic request/response models
│   ├── requirements.txt
│   ├── Dockerfile
│   └── railway.toml
├── frontend/
│   ├── src/
│   │   ├── App.jsx                  # Root component + stage routing
│   │   ├── components/
│   │   │   ├── SessionConfig.jsx    # Step 1: configure session
│   │   │   ├── DebatePanel.jsx      # Step 2: live cluster debate view
│   │   │   ├── AgentCard.jsx        # Individual agent status cards
│   │   │   └── FeedbackForm.jsx     # Step 3: feedback + accept
│   │   ├── hooks/
│   │   │   └── useDebateSession.js  # All session state + SSE consumption
│   │   └── services/
│   │       └── api.js               # API calls + SSE stream helper
│   ├── Dockerfile
│   ├── nginx.conf
│   └── railway.toml
├── .env.example                     # Environment variable template
└── README.md
```

---

## Roadmap

- [ ] PostgreSQL session persistence (Railway Postgres addon)
- [ ] PDF text extraction with pdfplumber
- [ ] Export final report as PDF (Passo 12 — reportlab output)
- [ ] Authentication (JWT)
- [ ] Rate limiting per user
- [ ] Sabiá-4-thinking model for Cluster 5 (adversarial reasoning)
- [ ] Parallel cluster execution (Clusters 1–4 simultaneously)
- [ ] Contract type auto-detection (routes to specific checklist automatically)

---

## A Final Note

Gilberto is a personal project, built without commercial intent, for lawyers who believe that the future of legal practice is not AI replacing judgment — it is lawyers using AI to make their judgment sharper, faster, and harder to beat.

If you are using this tool passively, you are using it wrong.
