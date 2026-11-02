# Gilberto — Agentic legal analysis system

[Português](README.md) · **English**

> *"Technology as a reasoning empowerment tool — not a brain substitute."*

Gilberto is a multi-agent AI system for analysing contracts governed by Brazilian law. Teams of specialised agents examine the document, review one another's conclusions, are challenged by an adversarial reviewer and are consolidated by a coordinator. The result then passes through mandatory human review gates.

> **Current status.** Gilberto produces **AI-generated drafts for legal review**, not legal opinions. The legal sources the agents cite are **not verified automatically**, and there is not yet a lawyer-reviewed legal benchmark demonstrating the system's accuracy. Every conclusion requires human verification before any use.

The system itself — interface, messages and agent instructions — is in Brazilian Portuguese, because several Brazilian legal concepts have no exact English equivalent. Where this document uses a Portuguese term, it is the term the system uses.

---

## The philosophy behind Gilberto

I built Gilberto for young lawyers who want to use technology intelligently: not to replace their legal judgment, but to sharpen it.

The legal profession demands something no AI system can replicate: understanding context, exercising discretion, assuming professional responsibility and applying ethics under uncertainty. Gilberto does not pretend otherwise. What it offers is a structured, rigorous second opinion, produced by agents guided by Brazilian contract-review checklists, so that nothing slips through the cracks.

**The core belief:** a lawyer who uses AI critically is stronger than any AI system alone.

## Two ways to use Gilberto

### Way 1 — AI as a verification layer (recommended for complex contracts)

```
YOU analyse the contract first
        ↓
Upload it to Gilberto
        ↓
Gilberto runs its multi-agent analysis
        ↓
YOU compare the output with your own analysis
        ↓
Did Gilberto find something you missed?
Did you find something Gilberto missed?
        ↓
The final judgment is YOURS
```

This is the approach I recommend for complex contracts — shareholders' agreements, M&A documents, long-term service agreements — where human judgment is irreplaceable but the number of clauses is large enough that something can always be missed. Use Gilberto as a checklist engine with legal depth, not as your primary analyst.

### Way 2 — AI as a first-pass analyst (useful for high volume)

```
Upload the contract directly
        ↓
Gilberto runs the full analysis loop
        ↓
YOU critically evaluate every output
Question every finding. Disagree where you know better.
        ↓
Submit feedback → Gilberto routes it to the relevant workstream
        ↓
Revised analysis
        ↓
The final judgment is YOURS
```

This works well when you are processing many contracts and need a structured starting point. The key word is **critically**: never accept the output passively. The feedback loop exists precisely for this — to push back on Gilberto's findings and force it to defend or revise them.

### What Gilberto is not

Gilberto is **not a substitute** for legal advice and is **not** a lawyer admitted to the Brazilian bar (OAB). It is **not always right**: it will miss things, and you are the safeguard. It is also **not designed for passive use** — the feedback loop is not optional; it is the point.

---

## How it works

### Agent teams

The analysis is divided into five workstreams (*frentes*), each with four specialists and a coordinator:

| Workstream | Specialists |
|---|---|
| **Fundamentos** (foundation) | Contract classification, document integrity, party qualification, transactional context |
| **Risco financeiro** (financial risk) | Price and payment, penalty clause (*cláusula penal*), guarantees, economic exposure |
| **Mitigação e saída** (mitigation and exit) | Termination rights, force majeure and hardship (*onerosidade excessiva*), dispute resolution, exit strategy |
| **Conformidade** (compliance) | LGPD and data protection, anti-corruption, electronic-signature validity, general provisions |
| **Estratégia** (strategy) | Negotiation leverage, concession limits, counterparty intent, deal structure |

Two coordinating agents work outside the workstreams: a **devil's advocate** (*advogado do diabo*), which challenges every workstream's conclusions, and a **master coordinator**, which produces the final synthesis. When the user submits feedback, a **feedback-advocate agent** is added to the relevant workstream. Each agent's role, goal and instructions are defined in [`backend/agents/cluster_definitions.py`](backend/agents/cluster_definitions.py).

### One round

```
Document uploaded
        │
        ▼
The five workstreams run in parallel
  └─ within each workstream, in sequence:
     specialist analyses → peer votes → coordinator synthesis
        │
        ▼
The devil's advocate audits every workstream
        │
        ▼
The master coordinator consolidates the result
        │
        ▼
Human review gates (when triggered)
        │
        ▼
YOU review ── feedback ──▶ re-analysis of the relevant workstream
        │                  and a new synthesis
        ▼
Final acceptance recorded
```

Peer votes happen **only within a workstream**: an LGPD specialist never scores the analysis of a guarantee clause. Cross-workstream synthesis happens only at the coordination levels.

**Cost per round.** A full review uses about **47 model calls** per round; a focused draft, with one reviewer per workstream, about **12**. Both figures assume all five workstreams are active; the plan screen shows the actual number before anything is sent.

### Risk scoring

Each workstream assigns a risk score from 0 to 10 and a confidence self-rating from 1 to 5. Two things are determined by code, not by the model:

- **Final score:** the confidence-weighted median of the workstream scores ([`backend/scoring.py`](backend/scoring.py)).
- **Classification:** **Crítico** if the score is ≥ 8; **Relevante** if ≥ 5; **Aceitável** below that.

The qualitative *Passo 11* criteria — for example, a critical risk in any workstream, or a blank field in the object, price or term — guide the agents through their instructions but are **not enforced by code**. The model's confidence is **not** a calibrated probability of being correct.

### Human review gates

The analysis stops and requires a reasoned human decision when:

1. any workstream's confidence falls below the configured threshold (`GATE_1_CONFIDENCE_THRESHOLD`);
2. the severity of the gaps found by the devil's advocate exceeds the configured threshold (`GATE_2_DEVIL_ADVOCATE_THRESHOLD`);
3. the final classification is **Crítico**.

The reviewer may approve, override the score or request re-analysis. Every decision requires written reasoning and is recorded in the audit trail. Final acceptance is only possible once every mandatory review is complete.

---

## Security and data handling

- **Authentication is mandatory**, through OIDC or through administrator-issued local accounts (`AUTH_MODE=oidc` or `local`). Session and administration routes do not work without it.
- **Owner isolation:** each session belongs to the user who created it; to any other user it simply does not exist.
- **Brazilian jurisdiction only.**
- **AI provider:** Maritaca (Sabiá-4) is the primary provider. A backup provider is used only if the operator configures one **and** the user explicitly consents to the document transfer. There is no automatic retry or provider switch after an uncertain response.
- **Agent permissions:** every model dispatch is authorised by a capability policy; an agent cannot widen its own permissions.
- **Persistence:** sessions are saved as SQLite checkpoints on a persistent volume (`SESSION_DB_PATH`), with encrypted backups and isolated restore verification.
- **Evidence store (being rolled out):** a PostgreSQL store binds each conclusion to the exact passage of the document or source, with tenant isolation enforced by the database itself. It is **not yet connected** to the analysis flow and stays disabled until `EVIDENCE_DATABASE_URL` is set.

---

## Technology

| Layer | Technology |
|---|---|
| Language model | Maritaca AI Sabiá-4 (OpenAI-compatible API) |
| Agents | CrewAI |
| Backend | FastAPI (Python 3.11) |
| Real time | Server-Sent Events |
| Frontend | React + Vite, Tailwind CSS, served by Nginx |
| Persistence | SQLite (sessions and identities); PostgreSQL + Alembic (evidence store) |
| Deployment | Railway — staging and production environments |

---

## Local development

### Prerequisites

- Python 3.11
- Node.js 22
- A Maritaca API key ([plataforma.maritaca.ai](https://plataforma.maritaca.ai))

### Backend

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env              # never commit this file
# Edit .env: MARITACA_API_KEY and the authentication settings
uvicorn main:app --reload --port 8000
```

Authentication is mandatory locally too. Configure it with one of these guides:

- invite-only local accounts: [`docs/self-hosted-identity-runbook-20261029.md`](docs/self-hosted-identity-runbook-20261029.md);
- an OIDC provider: [`docs/oidc-rollout-and-railway-preflight.md`](docs/oidc-rollout-and-railway-preflight.md).

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

### Tests

The same commands that continuous integration runs:

```bash
# Backend
cd backend
python -m unittest discover -s tests -v
python -m benchmarks.validate

# Frontend
cd frontend
npx playwright install chromium
npm test
npm run test:local
npm run test:br-legal-notice
npm run build
```

The evidence-store tests also run against PostgreSQL when `EVIDENCE_TEST_DATABASE_URL` is set; in continuous integration they cannot be skipped.

---

## Deployment

Gilberto runs on Railway with two services — backend and frontend — in two environments:

| Environment | Deployed branch |
|---|---|
| Staging | `release/brlaw-security-staging-20261029` |
| Production | `main` |

The Nginx frontend proxies `/api` to the backend over Railway's private network (`GILBERTO_API_UPSTREAM`, `GILBERTO_PROXY_SECRET`), so the browser and the API share one origin. The backend needs a persistent volume mounted at `/data`. For the step-by-step setup, required variables and pre-flight checks, see [`docs/oidc-rollout-and-railway-preflight.md`](docs/oidc-rollout-and-railway-preflight.md) and [`docs/self-hosted-identity-runbook-20261029.md`](docs/self-hosted-identity-runbook-20261029.md).

**Release policy:** no change reaches production without the documented release gates, including human legal review of legal content.

---

## API reference

Session and administration routes require authentication. `…` stands for `/api/sessions`.

| Group | Routes |
|---|---|
| Sessions | `POST /api/sessions` · `POST …/{id}/start` · `GET …/{id}/status` · `GET …/{id}/results` · `GET …/{id}/stream` (SSE) |
| Human review | `GET …/{id}/gates` · `POST …/{id}/gate-decision` · `POST …/{id}/human-votes` · `POST …/{id}/feedback` · `POST …/{id}/accept` |
| Run control | `POST …/{id}/pause` · `POST …/{id}/resume` · `POST …/{id}/cancel` |
| Authentication | `POST /api/auth/login` · `POST /api/auth/logout` · `GET /api/auth/me` · `POST /api/auth/change-password` · `GET /api/auth/bootstrap-status` · `POST /api/auth/bootstrap` |
| Administration | `GET /api/admin/users` · `GET /api/admin/backups/status` · `POST /api/admin/backups/run` · `POST /api/admin/backups/verify` · `GET /api/admin/operations/summary` · observability routes |
| Health | `GET /api/health` · `GET /api/ready` |

Interactive API documentation is served at `/docs` when the backend runs locally.

---

## Project structure

```
backend/
  main.py                  FastAPI app and all routes
  config.py                Settings from environment variables
  engines/                 Agent orchestration (debate_engine_v3.py)
  agents/                  Agent definitions, roles and instructions
  legal/                   Brazilian legal-reliability rules
  evidence/                PostgreSQL evidence store (disabled by default)
  security/                Authentication, authorisation and capability policy
  gates/                   Human review gates
  scoring.py               Deterministic risk-score aggregation
  benchmarks/              Synthetic control cases
  tests/                   Backend tests
frontend/
  src/components/          Screens and panels
  src/hooks/               Session state and event stream
  src/auth/                Browser authentication
  tests/, tests-local/     Playwright tests (OIDC and local accounts)
backup_gateway/            Encrypted backup gateway
docs/                      Architecture decisions, audits and runbooks
```

---

## Roadmap

The engineering plan in progress covers, in this order:

- [x] Security reconciliation between staging and production
- [x] PostgreSQL evidence store with tenant isolation
- [ ] Interface, messages and agent instructions in Portuguese
- [ ] Structured document ingestion (pages, clauses, tables)
- [ ] Local OCR for scanned documents
- [ ] Retrieval from official Brazilian sources (Planalto, LexML, STJ, STF, CNJ DataJud)
- [ ] Agents that ground every conclusion in verifiable evidence
- [ ] A workspace to inspect each conclusion beside its source
- [ ] Attributable professional review, bound to the exact evidence version
- [ ] A lawyer-reviewed Brazilian legal benchmark

---

## A final note

Gilberto is a personal project, built without commercial intent, for lawyers who believe the future of legal practice is not AI replacing judgment — it is lawyers using AI to make their judgment sharper, faster and harder to beat.

If you are using this tool passively, you are using it wrong.
