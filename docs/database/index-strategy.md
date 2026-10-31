# ProductMind AI — Indexing Strategy & Optimization Guide

This document defines the indexing strategy across all MongoDB collections in ProductMind AI, explaining query access patterns, compound index field ordering (ESR rule: Equality, Sort, Range), partial indexes, and automatic TTL expiration.

---

## 1. Indexing Principles & Governance

1. **Workspace Multi-Tenancy Prefix**:
   In a multi-tenant SaaS application, almost every operational query filters first by `workspaceId`. Therefore, tenant-owned collection indexes consistently start with `workspaceId` as the leading equality key.
2. **Global Identity Collections**:
   Identity collections like `users` and `auth_sessions` do not use `workspaceId` as the leading index key because authentication precedes workspace resolution.
3. **ESR Ordering Discipline**:
   Compound indexes follow the **Equality -> Sort -> Range** principle to ensure that MongoDB query plans can fulfill both filtering and sorting without relying on in-memory blocking sort operations.
4. **Partial Unique Indexes**:
   Optional identifiers (such as `externalId` on feedback items or `eventId` on analytics events) use partial unique indexes to enforce deduplication when the field is populated, while allowing multiple records with null or absent values.
5. **Write Cost vs. Read Performance**:
   Excessive indexes penalize write latency and consume RAM working set memory. Only indexes supporting verified UI filters, sorting orders, or uniqueness guarantees are created.

---

## 2. Comprehensive Index Inventory

| Collection | Index Fields | Type / Options | Target Query / Workflow Supported |
|---|---|---|---|
| **users** | `{ email: 1 }` | Unique, normalized | Authentication login lookup by normalized email. |
| **users** | `{ isActive: 1 }` | Standard | Admin filter for active accounts. |
| **workspaces** | `{ slug: 1 }` | Unique | Direct URL workspace routing (e.g. `/app/apex-cloud-ops`). |
| **workspaces** | `{ ownerId: 1 }` | Standard | Workspace ownership listing. |
| **workspace_memberships** | `{ workspaceId: 1, userId: 1 }` | Compound Unique | Prevents duplicate user memberships within the same workspace. |
| **workspace_memberships** | `{ userId: 1, status: 1 }` | Compound | Fast retrieval of all active workspaces a user is authorized to enter. |
| **auth_sessions** | `{ tokenHash: 1 }` | Unique | Refresh token verification during token rotation. |
| **auth_sessions** | `{ expiresAt: 1 }` | TTL Index (`expires: 0`) | Automatic document expiration when session expires. |
| **auth_sessions** | `{ sessionFamily: 1, userId: 1 }` | Compound | Session family revocation on compromised refresh token reuse. |
| **feedback_batches** | `{ workspaceId: 1, createdAt: -1 }` | Compound | Recent import history table in workspace. |
| **feedback_batches** | `{ fileHash: 1 }` | Standard (Accelerator) | Duplicate file detection query accelerator. Does NOT enforce uniqueness constraint (allows intentional re-imports). |
| **feedback_items** | `{ workspaceId: 1, feedbackDate: -1 }` | Compound | Feedback table default chronological sort with pagination. |
| **feedback_items** | `{ workspaceId: 1, category: 1, sentiment: 1, sourcePriority: 1 }` | Compound | Multi-select filters in Feedback Explorer and Dashboard sentiment cards. |
| **feedback_items** | `{ workspaceId: 1, sourceType: 1, externalId: 1 }` | Partial Unique | Source-scoped idempotent deduplication: issue #1 in Jira and #1 in GitHub within the same workspace will not collide. |
| **feedback_items** | `{ workspaceId: 1, legacyId: 1 }` | Compound | Idempotent demo and external ID mapping without duplicate generation. |
| **feedback_items** | `{ workspaceId: 1, featureGroupId: 1 }` | Compound | Retrieval of all supporting feedback items belonging to a feature group. |
| **feedback_items** | `{ workspaceId: 1, promotedFeatureId: 1 }` | Compound | Tracing customer feedback linked to a promoted production feature. |
| **feedback_items** | `{ title: "text", description: "text" }` | Text Index | Global search bar across customer feedback text. |
| **analytics_batches** | `{ workspaceId: 1, createdAt: -1 }` | Compound | Recent analytics import history table in workspace. |
| **analytics_batches** | `{ fileHash: 1 }` | Standard (Accelerator) | Duplicate analytics file detection accelerator (non-unique). |
| **analytics_events** | `{ workspaceId: 1, eventTimestamp: -1 }` | Compound | Timeline event stream queries and rolling time window filters. |
| **analytics_events** | `{ eventTimestamp: 1 }` | TTL (`expireAfterSeconds: 7776000`) | Automatic 90-day retention. Raw events expire after rollup into daily aggregates (MongoDB 60s background cycle). |
| **analytics_events** | `{ workspaceId: 1, featureName: 1, date: -1 }` | Compound | Feature-level adoption drilldown and usage trends over time. |
| **analytics_events** | `{ workspaceId: 1, eventId: 1 }` | Partial Unique | Telemetry event idempotency key deduplication. |
| **analytics_daily_rollups**| `{ workspaceId: 1, date: 1 }` | Compound Unique | Enforces single authoritative rollup per workspace per calendar day. |
| **analytics_daily_rollups**| `{ workspaceId: 1, date: -1 }` | Compound | Fast range lookup for trend line charts (7d, 30d, 90d, All). |
| **feature_groups** | `{ workspaceId: 1, feedbackCount: -1 }` | Compound | Feature Aggregation page sorted by customer request volume. |
| **feature_groups** | `{ workspaceId: 1, status: 1, category: 1 }` | Compound | Filtering feature clusters by status ('suggested', 'approved', 'merged'). |
| **features** | `{ workspaceId: 1, score: -1 }` | Compound | Prioritization matrix ranking from Critical to Low priority. |
| **features** | `{ workspaceId: 1, status: 1, priorityTier: 1 }` | Compound | Kanban delivery pipeline boards and status columns. |
| **features** | `{ workspaceId: 1, targetRelease: 1, status: 1 }` | Compound | Release planning board grouping features by target release candidate. |
| **prioritization_scenarios**| `{ workspaceId: 1, createdAt: -1 }` | Compound | What-If sandbox scenario selector dropdown. |
| **prds** | `{ workspaceId: 1, featureId: 1 }` | Compound | 1-click navigation from feature row to its generated PRD specification. |
| **prds** | `{ workspaceId: 1, updatedAt: -1 }` | Compound | PRD studio recent document selector. |
| **roadmap_items** | `{ workspaceId: 1, milestone: 1, targetDate: 1 }` | Compound | Roadmap timeline Gantt view and quarterly milestone grouping. |
| **roadmap_items** | `{ workspaceId: 1, status: 1 }` | Compound | Roadmap Kanban board columns. |
| **releases** | `{ workspaceId: 1, version: 1 }` | Compound Unique | Enforces unique version tags (e.g. `v2.4.0`) within a workspace. |
| **releases** | `{ workspaceId: 1, plannedDate: 1 }` | Compound | Release candidate timeline sorting. |
| **copilot_conversations** | `{ workspaceId: 1, userId: 1, lastMessageAt: -1 }` | Compound | Copilot sidebar chat session list sorted by recent activity. |
| **copilot_messages** | `{ conversationId: 1, createdAt: 1 }` | Compound | Chronological pagination of conversation turns within a chat session. |
| **saved_reports** | `{ workspaceId: 1, createdAt: -1 }` | Compound | Saved views dropdown in Executive Dashboard. |
| **audit_logs** | `{ workspaceId: 1, createdAt: -1 }` | Compound | Chronological activity history timeline feed. |
| **audit_logs** | `{ workspaceId: 1, entityType: 1, entityId: 1, createdAt: -1 }` | Compound | Audit trail for a specific entity (e.g. changes made to PRD-1). |
| **audit_logs** | `{ expiresAt: 1 }` | TTL Index (`expires: 0`) | Automatic compliance data retention (default 180 days). |

---

## 3. Storage & Operational Considerations

1. **RAM Working Set**:
   All compound indexes are designed so the index keys fit comfortably in RAM even at 500,000+ customer feedback records per workspace.
2. **Text Index Trade-Off**:
   `feedback_items` uses a single text index over `{ title: "text", description: "text" }`. In production Atlas environments, this can seamlessly transition to Atlas Search (Lucene) without modifying application code.
3. **Vector Index Preparation**:
   The `embedding` field in `feedback_items` is configured with `select: false` so that multi-hundred-dimensional vectors are never transferred across the wire during regular table queries.
