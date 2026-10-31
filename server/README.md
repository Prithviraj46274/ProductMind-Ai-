# ProductMind AI — Backend & Database Layer

This directory houses the MongoDB database architecture, Mongoose schemas and models, relationship models, validation logic, connection management, and automated test suite for **ProductMind AI**.

---

## 🏗️ Architecture Overview

The backend uses a multi-tenant, workspace-isolated architecture centered on MongoDB and Mongoose.
Data is segregated strictly by `workspaceId` across all domain entities, backed by compound and partial indexes designed for sub-second query performance.

### Key Architectural Tenets
1. **Workspace-Level Isolation**: Every persistent entity (except global user identity) carries an indexed `workspaceId` ObjectId reference.
2. **Deterministic Mathematical Formulas**: Feature prioritization uses the verified 4-factor scoring formula:
   $$\text{Score} = (0.35 \times \text{Impact}) + (0.30 \times \text{Urgency}) + (0.20 \times \text{Demand}) + (0.15 \times \text{Value})$$
3. **Embed vs. Reference Discipline**:
   - **Referenced**: Entities with independent lifecycles, unbounded growth, or cross-cutting queries (Users, Workspaces, FeedbackItems, FeatureGroups, Features, PRDs, RoadmapItems, Releases, CopilotMessages, AuditLogs).
   - **Embedded**: Bounded components strictly scoped to a parent document (PRD 13 sections, Release quality gates, Feature comments, Customer Journey touchpoints).
4. **Authoritative Relationships**:
   - Feedback items link to their group via `FeedbackItem.featureGroupId`.
   - Feature groups store a cached `feedbackCount` and top excerpts for instantaneous listing without multi-table joins.
5. **Two-Tier Analytics Architecture**:
   - `analytics_events`: Raw user interaction events with idempotency keys and structured properties.
   - `analytics_daily_rollups`: Precomputed daily rollups (DAU, sessions, feature metrics, funnels) enabling instant dashboard loads.

---

## 📁 Directory Structure

```
server/
├── .env.example              # Environment variables template
├── package.json              # Backend dependencies and test scripts
├── README.md                 # Architecture and operational documentation
├── src/
│   ├── config/
│   │   └── env.js            # Type-safe, validated environment configuration
│   ├── constants/
│   │   └── enums.js          # Shared domain enums, priorities, statuses, tiers
│   ├── database/
│   │   ├── mongodb.js        # Production MongoDB connection lifecycle manager
│   │   └── index.js          # Unified database export module
│   ├── models/
│   │   ├── auth/             # Module 1: User, Workspace, Membership, Session
│   │   ├── feedback/         # Module 2: FeedbackBatch, FeedbackItem
│   │   ├── analytics/        # Module 3: AnalyticsEvent, AnalyticsDailyRollup
│   │   ├── intelligence/     # Modules 4 & 5: FeatureGroup, CustomerPersona, CompetitorIntel
│   │   ├── planning/         # Modules 6, 7 & 8: Feature, Scenario, PRD, RoadmapItem, Release, Experiment, Journey
│   │   ├── copilot/          # Module 9: CopilotConversation, CopilotMessage
│   │   ├── reporting/        # Module 10: SavedReport
│   │   ├── audit/            # Cross-cutting: AuditLog
│   │   └── index.js          # Centralized model registry
│   └── scripts/
│       └── validate-models.js# Standalone model schema & index verification runner
└── tests/
    └── models/               # Comprehensive automated test suites
```

---

## 🚀 Getting Started

### Prerequisites
- Node.js v18+ (tested on Node v22)
- MongoDB v6.0+ (Local standalone, replica set, or MongoDB Atlas)

### Setup
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run model validation:
   ```bash
   npm run validate
   ```
4. Run automated test suite:
   ```bash
   npm test
   ```
