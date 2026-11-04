# ProductMind AI — AI Product Manager Copilot
### *Enterprise Product Intelligence & Strategic Prioritization Workspace*

[![React 19](https://img.shields.io/badge/Frontend-React_19-61DAFB?logo=react&logoColor=white)](https://react.dev/)
[![Python 3.10+](https://img.shields.io/badge/Backend_Driver-Python_3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Pydantic v2](https://img.shields.io/badge/Data_Validation-Pydantic_v2-E92063?logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![MongoDB](https://img.shields.io/badge/Database-MongoDB_8.0-47A248?logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![Pytest](https://img.shields.io/badge/DB_Tests-20_Passed-green.svg)](https://docs.pytest.org/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> **ProductMind AI** is an enterprise-grade AI Product Manager Copilot that bridges the gap between raw customer feedback and strategic execution. It combines **multi-tenant workspace data models**, **4-factor deterministic priority scoring**, **13-section PRD generation**, **interactive What-If roadmapping**, and **strict Go/No-Go release governance**.

---

## 🏗️ Architecture & Implementation Status

ProductMind AI follows a four-phase enterprise architecture:

```mermaid
flowchart LR
    A[Phase 1: Python Database Layer<br/><b>COMPLETED & VERIFIED</b>] --> B[Phase 2: FastAPI REST API<br/><b>NEXT UP</b>]
    B --> C[Phase 3: LangChain AI Copilot<br/><b>PLANNED</b>]
    C --> D[Phase 4: Full React + Live API Integration<br/><b>PLANNED</b>]
```

### Phase Status Overview

| Phase | Component | Technology | Status | Key Deliverables |
|:---:|:---|:---|:---:|:---|
| **Phase 1** | **Database & Data Layer** | Python 3.10+, PyMongo, Motor, Pydantic v2, MongoDB | ✅ **Completed** | • 23 Collections with full Pydantic v2 schemas<br/>• 12 Domain Repositories with tenant isolation<br/>• 20/20 Pytest verification suite (100% pass)<br/>• Python index synchronizer & idempotent seeder<br/>• 104 MongoDB documents verified intact |
| **Phase 2** | **Main Backend API** | Python, FastAPI, Pydantic DTOs | ⏳ **Upcoming** | • REST endpoints matching React `apiClient.js`<br/>• JWT authentication & workspace middleware<br/>• OpenAPI / Swagger documentation |
| **Phase 3** | **AI Intelligence** | LangChain, Google Gemini / LLM | ⏳ **Planned** | • Real-time Copilot chat & evidence citation<br/>• AI PRD generation & automatic sentiment triage |
| **Phase 4** | **Frontend Integration**| React 19, Vite, Tailwind CSS, Recharts | ⏳ **Planned** | • Connect React frontend to live FastAPI backend<br/>• Preserve client-side demo fallback |

---

## 📁 Project Directory Structure

```text
ProductMind-Ai-/
│
├── backend/                                # 🐍 PYTHON BACKEND & DATABASE LAYER
│   ├── app/
│   │   ├── core/                           # Domain Enums, Priority Algorithms & Config
│   │   │   ├── config.py                   # Environment settings & connection pool parameters
│   │   │   └── enums.py                    # Domain Enums & 4-Factor Weighted Priority Formula
│   │   ├── database/                       # MongoDB Connection & Driver Infrastructure
│   │   │   ├── collections.py              # Central registry of all 23 collection names
│   │   │   ├── connection.py               # Motor (async) & PyMongo (sync) Connection Manager
│   │   │   └── objectid.py                 # PyObjectId Pydantic v2 validator & BSON serializer
│   │   ├── models/                         # Pydantic v2 Domain Models (Matching MongoDB BSON)
│   │   │   ├── base.py                     # BaseMongoModel with timestamps, _id & to_mongo/from_mongo
│   │   │   ├── analytics.py                # AnalyticsBatch, AnalyticsEvent, AnalyticsDailyRollup
│   │   │   ├── audit.py                    # AuditLog (reversible actions & TTL retention)
│   │   │   ├── auth.py                     # User, Workspace, WorkspaceMembership, AuthSession
│   │   │   ├── copilot.py                  # CopilotConversation, CopilotMessage, Evidence citations
│   │   │   ├── feedback.py                 # FeedbackBatch, FeedbackItem (with 'processed' status)
│   │   │   ├── intelligence.py             # FeatureGroup, CustomerPersona, CompetitorIntel
│   │   │   ├── planning.py                 # Feature, PRD, RoadmapItem, Release, Experiment, Journey
│   │   │   └── reporting.py                # SavedReport
│   │   ├── schemas/                        # Pydantic Request/Response DTOs (FastAPI Ready)
│   │   │   ├── analytics.py
│   │   │   ├── audit_log.py
│   │   │   ├── copilot.py
│   │   │   ├── feature.py
│   │   │   ├── feedback.py
│   │   │   ├── prd.py
│   │   │   ├── roadmap.py
│   │   │   ├── user.py
│   │   │   └── workspace.py
│   │   └── repositories/                   # Data Access Layer (Tenant-Isolated Operations)
│   │       ├── base.py                     # BaseRepository[T] with workspace filtering & CRUD
│   │       ├── analytics_repository.py     # AnalyticsDailyRollup & Event repositories
│   │       ├── audit_log_repository.py     # Workspace audit history & event logging
│   │       ├── copilot_repository.py       # Conversation sessions & chronological message retrieval
│   │       ├── feature_repository.py       # Priority-ranked backlog & release targeting
│   │       ├── feedback_repository.py      # Category/sentiment filtering & full-text search
│   │       ├── intelligence_repository.py  # FeatureGroup clusters, Personas & Competitors
│   │       ├── prd_repository.py           # 13-section PRD specification queries
│   │       ├── release_repository.py       # Release versioning & readiness governance gates
│   │       ├── reporting_repository.py     # Saved dashboards & executive KPIs
│   │       ├── roadmap_repository.py       # Milestone timelines & dependency tracking
│   │       ├── user_repository.py          # User lookups & session tracking
│   │       └── workspace_repository.py     # Tenant workspaces & membership checks
│   ├── data/
│   │   └── seed_data.json                  # Canonical demonstration data payload
│   ├── scripts/
│   │   ├── init_db.py                      # MongoDB index verification & synchronization
│   │   └── seed_db.py                      # Idempotent Python database seeder & ingestion
│   ├── .env.example                        # Template environment variables
│   └── requirements.txt                    # Python dependencies (motor, pymongo, pydantic, bcrypt)
│
├── tests/                                  # 🧪 PYTHON TEST SUITE (DATABASE VERIFICATION)
│   └── database/
│       ├── conftest.py                     # Async (Motor) & sync (PyMongo) test fixtures
│       ├── test_connection.py              # Driver connectivity & collection presence checks
│       ├── test_data_compatibility.py      # Verification of all 104 existing MongoDB records
│       ├── test_models.py                  # Pydantic v2 serialization, PyObjectId & scoring tests
│       └── test_repositories.py            # Isolated CRUD, tenant isolation & text search tests
│
├── src/                                    # ⚛️ REACT 19 FRONTEND
│   ├── components/                         # UI Components & Modules
│   ├── services/                           # Frontend Services (apiClient.js, storage, simulation)
│   ├── data/
│   │   └── seedData.js                     # Standalone client-side demo dataset
│   └── tests/                              # Frontend Vitest test suite
│
├── package.json                            # Root npm scripts & React dependencies
└── README.md                               # Project documentation & architecture guide
```

---

## 🚀 Getting Started

### 1. Prerequisites
- **Node.js**: v18.x or later
- **Python**: v3.10 or later (tested on Python 3.13)
- **MongoDB**: v6.0+ (Local standalone or MongoDB Atlas cluster)

---

### 2. Frontend Development Setup (React)

```bash
# 1. Install frontend dependencies
npm install

# 2. Run local development server
npm run dev
# Accessible at http://localhost:5173

# 3. Run frontend unit tests
npm test

# 4. Build for production
npm run build
```

---

### 3. Python Database Layer Setup & Verification

```bash
# 1. Install Python dependencies
pip install -r backend/requirements.txt

# 2. Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env if using a remote MongoDB Atlas URI

# 3. Verify database index synchronization (Check mode)
python backend/scripts/init_db.py --check

# 4. Run automated Python database tests
python -m pytest tests/database -v
```

All 20 database tests execute and verify:
- Connection pooling for both Motor (async) and PyMongo (sync).
- All 23 collections exist and are accessible.
- Existing documents validate cleanly through Pydantic v2 models.
- Mathematical priority scoring formula matches exact weights.
- Tenant isolation across workspaces in all repository queries.

---

### 4. Database Seeding & Reset (Python)

To seed a clean MongoDB database or refresh demo intelligence:

```bash
# Seed demo data into target database (safe mode: will not overwrite without --force)
python backend/scripts/seed_db.py

# Force idempotent update of existing records
python backend/scripts/seed_db.py --force

# Reset and seed an isolated test database
python backend/scripts/seed_db.py --db-name productmind_ai_test --reset
```

---

## ⚖️ Prioritization Mathematical Formula

Initiatives are ranked on a continuous **1.0 to 10.0 scale** governed by the exact 4-factor formula:

$$\text{Priority Score} = (0.35 \times \text{Customer Impact}) + (0.30 \times \text{Urgency}) + (0.20 \times \text{Demand}) + (0.15 \times \text{Business Value})$$

* **Priority Tiers**:
  - **Critical Priority**: $8.50 \le \text{Score} \le 10.00$
  - **High Priority**: $7.00 \le \text{Score} < 8.50$
  - **Medium Priority**: $5.00 \le \text{Score} < 7.00$
  - **Low Priority**: $\text{Score} < 5.00$

---

## 🔑 Demo Access

| Profile | Email | Password | Role |
|---|---|---|---|
| **Lead Product Architect** | `alex.rivera@productmind.ai` | `demo123` | Backlog triage, PRD generation & scoring |
| **Workspace Tenant** | `apex-saas-product-operations` | — | Enterprise Tier Demo Workspace |

---

## 📄 License
MIT License. Created for ProductMind AI.
