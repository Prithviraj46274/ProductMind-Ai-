# ProductMind AI — Data Retention & Persistence Policy

This document defines the lifecycle, persistence guarantees, deletion semantics, and automated time-to-live (TTL) policies across all collections in ProductMind AI.

---

## 1. Classification of Data Types

| Category | Collections | Retention Policy | Purge / Expiry Mechanism | Recomputability |
|---|---|---|---|---|
| **Core Strategic Assets** | `workspaces`, `users`, `features`, `prds`, `roadmap_items`, `releases` | **Indefinite Persistence** | Soft deletion / Archiving flag | Authoritative source of truth. Cannot be recomputed if destroyed. |
| **Operational Customer Data** | `feedback_items`, `feedback_batches`, `feature_groups`, `customer_personas` | **Indefinite Persistence** (while workspace is active) | Explicit user deletion or account closure | Original customer voice. Must not be arbitrarily expired by TTL. |
| **Aggregated Metrics** | `analytics_daily_rollups` | **Indefinite Persistence** (permanent historical records) | Kept permanently for multi-year trend analysis | Derived from raw events, but preserved indefinitely so raw events can be purged safely. |
| **High-Volume Telemetry** | `analytics_events` | **Rolling 90-Day Retention** | Configurable TTL index / background archival job | Rolled into `analytics_daily_rollups` before raw event expiration. |
| **Compliance & Audit Logs** | `audit_logs` | **Rolling 180-Day Retention** | MongoDB TTL Index on `expiresAt` (`expires: 0`) | Immutable event log with before/after state diffs for 1-click undo. |
| **Authentication Sessions** | `auth_sessions` | **Rolling 30-Day Retention** | MongoDB TTL Index on `expiresAt` (`expires: 0`) | Session invalidation occurs on logout, expiry, or token reuse detection. |
| **Conversational Context** | `copilot_conversations`, `copilot_messages` | **User-Managed Persistence** | Soft deletion via `isArchived` or explicit user clear | Can be cleared per session from Copilot UI. |

---

## 2. Deletion Semantics

### A. Soft Deletion vs. Hard Deletion
1. **Workspaces & Users**:
   - Workspaces use `isArchived: true`. Deactivating a workspace prevents new logins and freezes member access without corrupting relational references.
   - Hard deletion is restricted to tenant offboarding procedures where GDPR "Right to be Forgotten" mandates complete database purging.
2. **Customer Feedback**:
   - Feedback records are soft-deleted or removed with an associated entry in `audit_logs`.
   - The frontend's "1-Click Reversible Undo" retrieves the `previousState` from `audit_logs` within the active session to restore deleted records instantaneously.
3. **Features & PRDs**:
   - Deletion generates a snapshot in `audit_logs`.
   - Historical versions of PRDs remain referenced in the audit history.

---

## 3. Two-Tier Analytics Retention & Historical Ingestion Strategy

A common failure in analytics platforms is attaching a TTL index to raw events that destroys historical data before aggregations are computed, resulting in blank dashboard charts after 90 days.

ProductMind AI solves this with a **Two-Tier Architecture**:
1. **Tier 1 (Raw Events - `analytics_events`)**:
   - Captures granular event payloads (`actorId`, `sessionId`, `featureName`, `durationSeconds`).
   - Retained for **90 days** from `eventTimestamp` via a MongoDB TTL index (`expireAfterSeconds: 7776000`).
   - **Operational Delay**: MongoDB runs a background thread every 60 seconds to purge expired TTL documents; actual document deletion occurs within 60-120 seconds of expiration.
2. **Tier 2 (Daily Rollups - `analytics_daily_rollups`)**:
   - Precomputes distinct DAU, total sessions, feature adoption rates, and 5-step funnel drop-offs.
   - Daily rollups are stored with `{ workspaceId, date }` as a unique compound key.
   - **Rollups are permanent historical records and are never expired by TTL**.
   - Result: Executive dashboards and trendlines display multi-year historical growth smoothly without scanning millions of raw rows.

### Historical Dataset Imports (e.g. Kaggle Datasets)
- When importing historical telemetry where `eventTimestamp` is older than 90 days:
  - If raw events are inserted with their historical timestamp, MongoDB's TTL thread will delete them within 60-120 seconds of insertion!
  - **Strategy**: The ingestion worker must calculate or ingest `AnalyticsDailyRollup` aggregates first. For raw events, the system preserves rollups permanently, while raw historical events are processed as temporary transient records or imported with an ingestion-time TTL.
  - **Reprocessing & Idempotency**: If a daily rollup already exists, re-aggregating uses an idempotent upsert (`$set` with updated metrics) to prevent double-counting.

---

## 4. Audit Log Persistence & Reversible Undo Guarantees

The architecture clearly distinguishes between **audit persistence**, **snapshot availability**, **undo eligibility**, and **actual state restoration**:
1. **Audit Persistence**: Every significant change is logged in `audit_logs` with actor attribution, entity type, action, and timestamp. Audit logs are retained for **180 days** via a TTL index on `expiresAt`.
2. **Snapshot Availability**: For reversible actions (`created`, `updated`, `deleted`), `previousState` and `newState` are stored as JSON/BSON snapshots.
3. **Undo Eligibility (`canUndo`)**: The pre-validate hook on `AuditLog` assigns `canUndo = true` only when the action is reversible and a sufficient state snapshot exists. Once an undo operation is executed, `canUndo` is set to `false` to prevent duplicate rollbacks. If an audit log entry reaches its 180-day retention limit, it is purged by MongoDB TTL and its undo eligibility ceases.
4. **State Restoration**: Reversible undo is currently supported within the client session and activity history UI. Dedicated backend REST undo endpoints (`POST /api/v1/audit/:id/undo`) and concurrency version-conflict checks are scheduled for subsequent backend phases.

---

## 5. Lifecycle Policies for Additional Collections

| Collection | Retention Period | Lifecycle Policy |
|---|---|---|
| `auth_sessions` | 30 days | Automatic TTL purge on `expiresAt`. Immediate revocation on logout or token reuse. |
| `feedback_batches` | Indefinite | Retained as operational import history while workspace is active. |
| `analytics_batches` | Indefinite | Retained as operational telemetry import history while workspace is active. |
| `copilot_conversations` | Indefinite | User-managed archiving (`isArchived: true`) or deletion. |
| `copilot_messages` | Indefinite | Preserved within parent conversation thread until conversation is deleted. |
| `product_experiments` | Indefinite | Historical record of product hypotheses, telemetry baselines, and conclusions. |
| `competitor_intel` | Indefinite | Living benchmark documentation updated periodically (`lastReviewed`). |
| `customer_journeys` | Indefinite | Permanent lifecycle stage mapping per workspace (`order` 1 to 5). |
| `prioritization_scenarios` | Indefinite | User-saved What-If sandbox configurations. |
| `saved_reports` | Indefinite | User-saved executive report templates and widget configurations. |
