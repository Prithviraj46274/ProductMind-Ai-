# ProductMind AI — Database Schema Catalog

This catalog documents all persistent MongoDB collections, fields, types, constraints, and provenance for the ProductMind AI architecture.

---

## 1. Module 1: User Authentication & Workspace Management

### Collection: `users`
- **Purpose**: Global user identity, credential hashes, and personal workspace preferences.
- **Owning Module**: Module 1 — User Authentication and Workspace Management.

| Field Name | Type | Status | Default | Validation & Constraints | References | Indexes | Provenance |
|---|---|---|---|---|---|---|---|
| `_id` | ObjectId | Required | Auto | Primary key | None | Unique Primary | System |
| `name` | String | Required | None | Min 2, max 100 chars, trimmed | None | None | User-edited |
| `email` | String | Required | None | Normalized lowercase, valid email regex | None | Unique | User-edited |
| `passwordHash` | String | Required | None | Bcrypt hash, min 8 chars, select: false | None | None | System/Security |
| `platformRole` | String | Optional | `'user'` | Enum: `'user'`, `'platform_admin'` | None | None | System |
| `avatar` | String | Optional | `null` | Max 300 chars | None | None | User-edited |
| `theme` | String | Optional | `'dark'` | Enum: `'dark'`, `'light'`, `'system'` | None | None | User-edited |
| `reducedMotion`| Boolean | Optional | `false` | Boolean | None | None | User-edited |
| `isActive` | Boolean | Optional | `true` | Boolean | None | Indexed | System |
| `emailVerifiedAt`| Date | Optional | `null` | Valid Date | None | None | System |
| `lastLoginAt` | Date | Optional | `null` | Valid Date | None | None | System |
| `createdAt` | Date | Required | Date.now | Auto timestamp | None | None | System |
| `updatedAt` | Date | Required | Date.now | Auto timestamp | None | None | System |

> **Corrected**: Removed duplicate `workspaceName` and `workspacePlan` (workspace data lives in `Workspace` model). Removed hardcoded `avatar: 'AR'` → `null`. Replaced workspace-level `role` with global `platformRole` enum. Workspace-specific roles are authoritative in `WorkspaceMembership`.

---

### Collection: `workspaces`
- **Purpose**: Multi-tenant workspace container enforcing tenant isolation.
- **Owning Module**: Module 1 — User Authentication and Workspace Management.

| Field Name | Type | Status | Default | Validation & Constraints | References | Indexes | Provenance |
|---|---|---|---|---|---|---|---|
| `_id` | ObjectId | Required | Auto | Primary key | None | Unique Primary | System |
| `name` | String | Required | None | Min 2, max 100 chars, trimmed | None | None | User-edited |
| `slug` | String | Required | None | Regex: `^[a-z0-9-]+$` | None | Unique | User-edited |
| `ownerId` | ObjectId | Required | None | Valid User ID | `users._id` | Indexed | System/User |
| `plan` | String | Optional | `'Starter Tier'` | Enum `WorkspacePlansList` | None | None | System |
| `settings` | Subdoc | Optional | `{}` | `WorkspaceSettingsSchema` (theme, reducedMotion, allowGuestViewers) | None | None | User-edited |
| `isArchived` | Boolean | Optional | `false` | Boolean | None | Indexed | System |
| `createdAt` | Date | Required | Date.now | Auto timestamp | None | None | System |
| `updatedAt` | Date | Required | Date.now | Auto timestamp | None | None | System |

> **Corrected**: Removed `settings.factorWeights` — the MVP uses a fixed deterministic 4-factor formula `(0.35×Impact + 0.30×Urgency + 0.20×Demand + 0.15×Value)` that is not configurable per workspace.

---

### Collection: `workspace_memberships`
- **Purpose**: Authoritative many-to-many junction connecting Users to Workspaces with RBAC.
- **Owning Module**: Module 1 — User Authentication and Workspace Management.

| Field Name | Type | Status | Default | Validation & Constraints | References | Indexes | Provenance |
|---|---|---|---|---|---|---|---|
| `_id` | ObjectId | Required | Auto | Primary key | None | Unique Primary | System |
| `workspaceId` | ObjectId | Required | None | Valid Workspace ID | `workspaces._id` | Compound Unique | System |
| `userId` | ObjectId | Required | None | Valid User ID | `users._id` | Compound Unique | System |
| `role` | String | Required | 'Product Manager' | Enum `UserRolesList` | None | None | User-edited |
| `status` | String | Required | 'active' | Enum `MembershipStatusesList` | None | Indexed | System |
| `invitedBy` | ObjectId | Optional | null | Valid User ID | `users._id` | None | System |
| `joinedAt` | Date | Required | Date.now | Valid Date | None | None | System |
| `createdAt` | Date | Required | Date.now | Auto timestamp | None | None | System |
| `updatedAt` | Date | Required | Date.now | Auto timestamp | None | None | System |

---

### Collection: `auth_sessions`
- **Purpose**: Refresh token session storage, token rotation family tracking, and session revocation.
- **Owning Module**: Module 1 — User Authentication and Workspace Management.

| Field Name | Type | Status | Default | Validation & Constraints | References | Indexes | Provenance |
|---|---|---|---|---|---|---|---|
| `_id` | ObjectId | Required | Auto | Primary key | None | Unique Primary | System |
| `userId` | ObjectId | Required | None | Valid User ID | `users._id` | Indexed | System |
| `sessionFamily` | String | Required | None | UUID string | None | Indexed | System |
| `tokenHash` | String | Required | None | Hashed token string, select: false | None | Unique | System |
| `userAgent` | String | Optional | 'Unknown Browser' | Max 300 chars | None | None | Original Source |
| `ipAddress` | String | Optional | '127.0.0.1' | Max 45 chars | None | None | Original Source |
| `expiresAt` | Date | Required | None | Valid Date | None | TTL Index (`expires: 0`) | System |
| `revokedAt` | Date | Optional | null | Valid Date | None | Indexed | System |
| `lastUsedAt` | Date | Required | Date.now | Valid Date | None | None | System |
| `createdAt` | Date | Required | Date.now | Auto timestamp | None | None | System |
| `updatedAt` | Date | Required | Date.now | Auto timestamp | None | None | System |

---

## 2. Module 2: Feedback & Support Ticket Ingestion

### Collection: `feedback_batches`
- **Purpose**: Metadata tracking for bulk CSV/JSON imports without storing unbounded row payloads.
- **Owning Module**: Module 2 — Feedback and Support Ticket Ingestion.

| Field Name | Type | Status | Default | Validation & Constraints | References | Indexes | Provenance |
|---|---|---|---|---|---|---|---|
| `_id` | ObjectId | Required | Auto | Primary key | None | Unique Primary | System |
| `workspaceId` | ObjectId | Required | None | Valid Workspace ID | `workspaces._id` | Compound (`workspaceId`, `createdAt`) | System |
| `uploadedBy` | ObjectId | Required | None | Valid User ID | `users._id` | None | System |
| `sourceType` | String | Required | 'csv' | Enum `FeedbackSourceTypesList` | None | None | Original Source |
| `fileName` | String | Optional | 'import.csv' | Max 255 chars | None | None | Original Source |
| `fileHash` | String | Optional | null | SHA256 string | None | Indexed | Derived |
| `status` | String | Required | 'pending' | Enum: `'pending'`, `'processing'`, `'completed'`, `'failed'` | None | Indexed | System |
| `fieldMappings` | Map<String>| Optional | Empty Map | Key-value column mappings | None | None | User-edited |
| `totalRows` | Number | Required | 0 | Min 0 | None | None | Derived |
| `acceptedRows` | Number | Required | 0 | Min 0 | None | None | Derived |
| `rejectedRows` | Number | Required | 0 | Min 0 | None | None | Derived |
| `duplicateRows`| Number | Required | 0 | Min 0 | None | None | Derived |
| `errorSummary` | Array | Optional | `[]` | Max 50 error sample objects | None | None | Derived |
| `startedAt` | Date | Required | Date.now | Valid Date | None | None | System |
| `completedAt` | Date | Optional | null | Valid Date | None | None | System |

---

### Collection: `feedback_items`
- **Purpose**: Core customer feedback records, sentiment tags, and feature group relationships.
- **Owning Module**: Module 2 — Feedback and Support Ticket Ingestion & Module 4 — Theme Extraction.

| Field Name | Type | Status | Default | Validation & Constraints | References | Indexes | Provenance |
|---|---|---|---|---|---|---|---|
| `_id` | ObjectId | Required | Auto | Primary key | None | Unique Primary | System |
| `workspaceId` | ObjectId | Required | None | Valid Workspace ID | `workspaces._id` | Compound (`workspaceId`, `feedbackDate`) | System |
| `batchId` | ObjectId | Optional | null | Valid Batch ID | `feedback_batches._id` | Indexed | System |
| `externalId` | String | Optional | `null` | Max 120 chars | None | Source-scoped dedup | Original Source |
| `legacyId` | String | Optional | `null` | Max 120 chars | None | Indexed | Original Source |
| `sourceType` | String | Required | `'manual'` | Enum `FeedbackSourceTypesList` | None | Compound dedup | Original Source |
| `sourceUrl` | String | Optional | `null` | Max 500 chars | None | None | Original Source |
| `title` | String | Required | None | Min 3, max 300 chars | None | Text Index | Original Source |
| `description` | String | Required | None | Max 5000 chars | None | Text Index | Original Source |
| `customerName` | String | Optional | `null` | Max 120 chars | None | None | Original Source |
| `customerEmail`| String | Optional | `null` | Normalized email | None | None | Original Source |
| `companyName` | String | Optional | `null` | Max 150 chars | None | None | Original Source |
| `category` | String | Optional | `null` | Enum `[...FeedbackCategoriesList, null]` | None | Compound Indexed | AI-inferred/User |
| `sentiment` | String | Optional | `null` | Enum `[...FeedbackSentimentsList, null]` | None | Compound Indexed | AI-inferred/User |
| `sourcePriority`| String | Optional | `null` | Enum `[...FeedbackPrioritiesList, null]` | None | Compound Indexed | Original Source |
| `aiPredictedPriority`| String | Optional | `null` | Enum `FeedbackPrioritiesList` | None | None | AI-generated |
| `sourceTags` | Array<String> | Optional | `[]` | Max 20 tags from original source | None | None | Original Source |
| `aiThemes` | Array<String> | Optional | `[]` | Max 20 AI-extracted themes | None | None | AI-generated |
| `tags` | Array<String> | Optional | `[]` | Max 20 tags per feedback record | None | None | User-edited |
| `feedbackDate` | Date | Required | Date.now | Valid Date | None | Indexed | Original Source |
| `featureGroupId`| ObjectId | Optional | `null` | Valid Group ID (Authoritative membership!) | `feature_groups._id` | Indexed | AI/User-edited |
| `promotedFeatureId`| ObjectId | Optional | `null` | Valid Feature ID (Cached link) | `features._id` | Indexed | User-edited |
| `classificationConfidence` | Number | Optional | `null` | Float between 0 and 1 | None | None | AI-generated |
| `processingStatus` | String | Required | `'raw'` | Enum `FeedbackProcessingStatusesList` | None | Indexed | System |
| `embedding` | Array<Number>| Optional | undefined | Float vector for Vector Search | None | Vector Index (Atlas) | AI-generated |

> **Corrected**: Removed fabricated defaults `customerName: 'Anonymous User'`, `companyName: 'Enterprise Account'`, `classificationConfidence: 0.85` → all `null`. Separated `sourceTags` (from import) from `aiThemes` (from AI). Added `aiPredictedPriority` distinct from `sourcePriority`. Deduplication index changed from `{ workspaceId, externalId }` to source-scoped `{ workspaceId, sourceType, externalId }`.

---

## 3. Module 3: Product Analytics Data Integration

### Collection: `analytics_batches`
- **Purpose**: Metadata tracking for bulk CSV/JSON analytics dataset uploads, separate from feedback batch tracking.
- **Owning Module**: Module 3 — Product Analytics Data Integration.

| Field Name | Type | Status | Default | Validation & Constraints | References | Indexes | Provenance |
|---|---|---|---|---|---|---|---|
| `_id` | ObjectId | Required | Auto | Primary key | None | Unique Primary | System |
| `workspaceId` | ObjectId | Required | None | Valid Workspace ID | `workspaces._id` | Compound (`workspaceId`, `createdAt`) | System |
| `uploadedBy` | ObjectId | Required | None | Valid User ID | `users._id` | None | System |
| `sourceType` | String | Required | `'csv'` | Enum `AnalyticsSourceTypesList` | None | None | Original Source |
| `fileName` | String | Optional | `'analytics_import.csv'` | Max 255 chars | None | None | Original Source |
| `fileHash` | String | Optional | `null` | SHA256 string | None | Indexed | Derived |
| `status` | String | Required | `'pending'` | Enum: `'pending'`, `'processing'`, `'completed'`, `'failed'` | None | Indexed | System |
| `fieldMappings` | Map<String> | Optional | Empty Map | Key-value column mappings | None | None | User-edited |
| `totalRows` | Number | Required | `0` | Min 0 | None | None | Derived |
| `acceptedRows` | Number | Required | `0` | Min 0 | None | None | Derived |
| `rejectedRows` | Number | Required | `0` | Min 0 | None | None | Derived |
| `duplicateRows` | Number | Required | `0` | Min 0 | None | None | Derived |
| `errorSummary` | Array | Optional | `[]` | Max 50 error sample objects | None | None | Derived |
| `startedAt` | Date | Required | Date.now | Valid Date | None | None | System |
| `completedAt` | Date | Optional | `null` | Valid Date | None | None | System |

---

### Collection: `analytics_events`
- **Purpose**: Granular event stream ingestion for telemetry, feature clicks, and drop-off tracking. **90-day TTL retention**.
- **Owning Module**: Module 3 — Product Analytics Data Integration.

| Field Name | Type | Status | Default | Validation & Constraints | References | Indexes | Provenance |
|---|---|---|---|---|---|---|---|
| `_id` | ObjectId | Required | Auto | Primary key | None | Unique Primary | System |
| `workspaceId` | ObjectId | Required | None | Valid Workspace ID | `workspaces._id` | Compound (`workspaceId`, `eventTimestamp`) | System |
| `batchId` | ObjectId | Optional | `null` | Valid Batch ID | `analytics_batches._id` | Indexed | System |
| `eventId` | String | Optional | `null` | Max 120 chars | None | Partial Unique | Original Source |
| `eventName` | String | Required | None | Max 100 chars | None | None | Original Source |
| `eventType` | String | Optional | `'view'` | Max 50 chars | None | Indexed | Original Source |
| `eventTimestamp` | Date | Required | None | Valid Date | None | TTL Index (90d) | Original Source |
| `date` | String | Required | None | Regex: `^\d{4}-\d{2}-\d{2}$` | None | Compound Indexed | Derived |
| `actorId` | String | Optional | `null` | Max 100 chars | None | Indexed | Original Source |
| `sessionId` | String | Optional | `null` | Max 120 chars | None | Indexed | Original Source |
| `featureName` | String | Required | None | Max 120 chars | None | Compound Indexed | Original Source |
| `durationSeconds`| Number | Optional | `0` | Min 0 | None | None | Original Source |
| `customProperties`| Map | Optional | Empty Map | Bounded key-value pairs | None | None | Original Source |

> **Corrected**: `batchId` now references `analytics_batches` (not `feedback_batches`). `actorId` defaults to `null` (not `'anon-user'`). Added 90-day TTL index on `eventTimestamp` (`expireAfterSeconds: 7776000`).

---

### Collection: `analytics_daily_rollups`
- **Purpose**: Precomputed daily aggregations for DAU, sessions, and feature adoption.
- **Owning Module**: Module 3 — Product Analytics Data Integration & Module 10 — Reporting Dashboard.

| Field Name | Type | Status | Default | Validation & Constraints | References | Indexes | Provenance |
|---|---|---|---|---|---|---|---|
| `_id` | ObjectId | Required | Auto | Primary key | None | Unique Primary | System |
| `workspaceId` | ObjectId | Required | None | Valid Workspace ID | `workspaces._id` | Compound Unique (`workspaceId`, `date`) | System |
| `date` | String | Required | None | Regex: `^\d{4}-\d{2}-\d{2}$` | None | Compound Unique | Derived |
| `activeUsers` | Number | Required | 0 | Min 0 (Distinct DAU) | None | None | Derived |
| `totalSessions` | Number | Required | 0 | Min 0 | None | None | Derived |
| `totalEvents` | Number | Required | 0 | Min 0 | None | None | Derived |
| `avgSessionDuration`| Number | Required | 0 | Min 0 (Seconds) | None | None | Derived |
| `topFeature` | String | Optional | 'None' | Feature name | None | None | Derived |
| `featureMetrics` | Array<Subdoc> | Optional | `[]` | Adoption & completion metrics | None | None | Derived |
| `funnelMetrics` | Array<Subdoc> | Optional | `[]` | 5-step conversion funnel | None | None | Derived |
| `calculatedAt` | Date | Required | Date.now | Valid Date | None | None | System |

---

## 4. Modules 4 & 5: Feature Request Aggregation & Intelligence

### Collection: `feature_groups`
- **Purpose**: Clusters similar customer feedback into aggregated feature opportunity groups.
- **Owning Module**: Module 5 — Feature Request Aggregation.

| Field Name | Type | Status | Default | Validation & Constraints | References | Indexes | Provenance |
|---|---|---|---|---|---|---|---|
| `_id` | ObjectId | Required | Auto | Primary key | None | Unique Primary | System |
| `workspaceId` | ObjectId | Required | None | Valid Workspace ID | `workspaces._id` | Compound Indexed | System |
| `title` | String | Required | None | Max 200 chars | None | None | AI-generated/User |
| `category` | String | Required | 'Feature Requests' | Enum `FeedbackCategoriesList` | None | Compound Indexed | AI/User-edited |
| `primaryTag` | String | Optional | 'general' | Trimmed, lowercase | None | Indexed | AI/User-edited |
| `description` | String | Optional | '' | Max 2000 chars | None | None | AI-generated/User |
| `status` | String | Required | 'suggested' | Enum `FeatureGroupStatusesList` | None | Compound Indexed | System/User |
| `sentimentDistribution`| Subdoc | Required | 0s | `{ Positive, Neutral, Negative }` | None | None | Derived |
| `painPoints` | Array<String> | Optional | `[]` | Max 10 recurring pain point excerpts | None | None | Derived |
| `feedbackCount` | Number | Required | 0 | Min 0 (Cached derived count) | None | Indexed | Derived |
| `promotedFeatureId` | ObjectId | Optional | null | Valid Feature ID | `features._id` | Indexed | User-edited |
| `mergedIntoGroupId` | ObjectId | Optional | null | Valid Feature Group ID | `feature_groups._id` | None | User-edited |
| `reviewedBy` | ObjectId | Optional | null | Valid User ID | `users._id` | None | System |
| `reviewedAt` | Date | Optional | null | Valid Date | None | None | System |

---

### Collection: `customer_personas`
- **Purpose**: Archetype profiles synthesized from feedback patterns and user interviews.
- **Owning Module**: Supporting Module — Customer Personas.

| Field Name | Type | Status | Default | Validation & Constraints | References | Indexes | Provenance |
|---|---|---|---|---|---|---|---|
| `_id` | ObjectId | Required | Auto | Primary key | None | Unique Primary | System |
| `workspaceId` | ObjectId | Required | None | Valid Workspace ID | `workspaces._id` | Compound Indexed | System |
| `name` | String | Required | None | Max 100 chars | None | None | AI/User-edited |
| `role` | String | Required | None | Max 120 chars | None | None | AI/User-edited |
| `companyType` | String | Optional | 'Enterprise Client' | Max 120 chars | None | None | AI/User-edited |
| `avatar` | String | Optional | 'CP' | Max 10 chars | None | None | User-edited |
| `description` | String | Optional | '' | Max 2000 chars | None | None | AI/User-edited |
| `goals` | Array<String> | Optional | `[]` | Array of strings | None | None | AI/User-edited |
| `frustrations` | Array<String> | Optional | `[]` | Array of strings | None | None | AI/User-edited |
| `needs` | Array<String> | Optional | `[]` | Array of strings | None | None | AI/User-edited |
| `featurePreferences`| Array<String>| Optional | `[]` | Array of strings | None | None | AI/User-edited |
| `sentimentSummary` | String | Optional | 'Neutral' | Max 100 chars | None | None | Derived |
| `relatedFeedbackCount`| Number | Optional | 0 | Min 0 | None | None | Derived |
| `isFavorite` | Boolean | Optional | false | Boolean | None | Indexed | User-edited |

---

### Collection: `competitor_intel`
- **Purpose**: Competitive benchmarking, parity analysis, and key market differentiators.
- **Owning Module**: Supporting Module — Competitor Intelligence.

| Field Name | Type | Status | Default | Validation & Constraints | References | Indexes | Provenance |
|---|---|---|---|---|---|---|---|
| `_id` | ObjectId | Required | Auto | Primary key | None | Unique Primary | System |
| `workspaceId` | ObjectId | Required | None | Valid Workspace ID | `workspaces._id` | Compound (`workspaceId`, `name`) | System |
| `name` | String | Required | None | Max 120 chars | None | Compound Indexed | User-edited |
| `productDescription` | String | Optional | '' | Max 2000 chars | None | None | User-edited |
| `website` | String | Optional | '' | Max 300 chars | None | None | User-edited |
| `targetAudience` | String | Optional | 'Enterprise Product Teams' | Max 200 chars | None | None | User-edited |
| `keyFeatures` | Array<String> | Optional | `[]` | Array of strings | None | None | User-edited |
| `strengths` | Array<String> | Optional | `[]` | Array of strings | None | None | User-edited |
| `weaknesses` | Array<String> | Optional | `[]` | Array of strings | None | None | User-edited |
| `differentiators` | Array<String> | Optional | `[]` | Array of strings | None | None | User-edited |
| `researchNotes` | String | Optional | '' | Max 3000 chars | None | None | User-edited |
| `lastReviewed` | Date | Optional | Date.now | Valid Date | None | None | User-edited |

---

## 5. Modules 6, 7 & 8: Planning, Prioritization, PRD & Roadmap

### Collection: `features`
- **Purpose**: Prioritized backlog initiatives governed by the deterministic 4-factor scoring formula.
- **Owning Module**: Module 6 — AI-Based Prioritization and Impact Analysis.

| Field Name | Type | Status | Default | Validation & Constraints | References | Indexes | Provenance |
|---|---|---|---|---|---|---|---|
| `_id` | ObjectId | Required | Auto | Primary key | None | Unique Primary | System |
| `workspaceId` | ObjectId | Required | None | Valid Workspace ID | `workspaces._id` | Compound Indexed | System |
| `featureGroupId` | ObjectId | Optional | null | Valid Group ID | `feature_groups._id` | Indexed | User-edited |
| `name` | String | Required | None | Min 3, max 200 chars | None | None | User-edited |
| `description` | String | Required | None | Max 5000 chars | None | None | User-edited |
| `customerImpact` | Number | Required | `5` | Range: 1 to 10 | None | None | User-edited |
| `urgency` | Number | Required | `5` | Range: 1 to 10 | None | None | User-edited |
| `demand` | Number | Required | `5` | Range: 1 to 10 | None | None | User-edited |
| `businessValue` | Number | Required | `5` | Range: 1 to 10 | None | None | User-edited |
| `score` | Number | Required | `5.0` | Continuous 1.00 to 10.00, computed by pre-validate hook | None | Indexed (`score: -1`) | Derived (Calculated) |
| `priorityTier` | String | Required | `'Medium'` | Enum: `'Critical'`, `'High'`, `'Medium'`, `'Low'` | None | Compound Indexed | Derived |
| `status` | String | Required | `'In Planning'`| Enum `FeatureStatusesList` | None | Compound Indexed | User-edited |
| `owner` | String | Optional | `null` | Max 100 chars | None | None | User-edited |
| `targetRelease` | String | Optional | `null` | Max 50 chars | None | Compound Indexed | User-edited |
| `comments` | Array<Subdoc>| Optional | `[]` | Max 100 comment subdocs | None | None | User-edited |
| `aiJustification` | String | Optional | `''` | Max 1500 chars | None | None | AI-generated |
| `isManualOverride`| Boolean | Optional | `false` | Boolean | None | None | User-edited |

> **Corrected**: Factor defaults changed from 7 to neutral midpoint 5 (score defaults to 5.0, tier `'Medium'`). Removed fabricated `owner: 'Alex Rivera'` and `targetRelease: 'v2.4.0'` → both `null`. Score and priorityTier are computed deterministically by `pre('validate')` hook unless `isManualOverride` is set.

---

### Collection: `prioritization_scenarios`
- **Purpose**: What-If sandbox simulations for comparative trade-off analysis.
- **Owning Module**: Module 6 — AI-Based Prioritization and Impact Analysis.

| Field Name | Type | Status | Default | Validation & Constraints | References | Indexes | Provenance |
|---|---|---|---|---|---|---|---|
| `_id` | ObjectId | Required | Auto | Primary key | None | Unique Primary | System |
| `workspaceId` | ObjectId | Required | None | Valid Workspace ID | `workspaces._id` | Compound (`workspaceId`, `createdAt`) | System |
| `name` | String | Required | None | Max 150 chars | None | None | User-edited |
| `description` | String | Optional | '' | Max 1500 chars | None | None | User-edited |
| `createdBy` | ObjectId | Optional | null | Valid User ID | `users._id` | None | System |
| `adjustedFeatures`| Array<Subdoc>| Optional | `[]` | Max 50 simulated feature adjustments | None | None | User-edited |

---

### Collection: `prds`
- **Purpose**: Complete 13-section Product Requirements Documents.
- **Owning Module**: Module 7 — PRD and User Story Generation.

| Field Name | Type | Status | Default | Validation & Constraints | References | Indexes | Provenance |
|---|---|---|---|---|---|---|---|
| `_id` | ObjectId | Required | Auto | Primary key | None | Unique Primary | System |
| `workspaceId` | ObjectId | Required | None | Valid Workspace ID | `workspaces._id` | Compound Indexed | System |
| `featureId` | ObjectId | Optional | null | Valid Feature ID | `features._id` | Compound (`workspaceId`, `featureId`) | User-edited |
| `title` | String | Required | None | Min 3, max 200 chars | None | None | User-edited |
| `version` | String | Optional | '1.0.0' | Version string | None | None | User-edited |
| `status` | String | Required | 'Draft' | Enum `PRDStatusesList` | None | Compound Indexed | User-edited |
| `author` | String | Optional | `null` | Author display name | None | None | User-edited |
| `authorId` | ObjectId | Optional | `null` | Valid User ID | `users._id` | None | System |
| `sections` | Subdoc | Required | 13 sections | `PRDSectionsSchema` | None | None | AI/User-edited |
| `aiGenerated` | Boolean | Optional | `false` | Boolean | None | None | System |

> **Corrected**: Removed fabricated `author: 'Alex Rivera'` → `null`. Added `authorId` ObjectId reference to `users`.

---

### Collection: `roadmap_items`
- **Purpose**: Milestone schedule items, timelines, progress tracking, and Gantt charts.
- **Owning Module**: Module 8 — Roadmap Planning and Visualization.

| Field Name | Type | Status | Default | Validation & Constraints | References | Indexes | Provenance |
|---|---|---|---|---|---|---|---|
| `_id` | ObjectId | Required | Auto | Primary key | None | Unique Primary | System |
| `workspaceId` | ObjectId | Required | None | Valid Workspace ID | `workspaces._id` | Compound Indexed | System |
| `featureId` | ObjectId | Optional | null | Valid Feature ID | `features._id` | Indexed | User-edited |
| `releaseId` | ObjectId | Optional | null | Valid Release ID | `releases._id` | Indexed | User-edited |
| `title` | String | Required | None | Min 3, max 200 chars | None | None | User-edited |
| `description` | String | Optional | '' | Max 2000 chars | None | None | User-edited |
| `status` | String | Required | 'Planned' | Enum `RoadmapStatusesList` | None | Compound Indexed | User-edited |
| `priority` | String | Optional | 'Medium' | Enum `FeedbackPrioritiesList` | None | None | User-edited |
| `owner` | String | Optional | `null` | Owner display name | None | None | User-edited |
| `ownerId` | ObjectId | Optional | `null` | Valid User ID | `users._id` | None | System |
| `startDate` | String | Required | None | Regex: `^\d{4}-\d{2}-\d{2}$` | None | None | User-edited |
| `targetDate` | String | Required | None | Regex: `^\d{4}-\d{2}-\d{2}$` | None | Compound Indexed | User-edited |
| `milestone` | String | Optional | `null` | Milestone tag | None | Compound Indexed | User-edited |

> **Corrected**: Removed fabricated `owner: 'Alex Rivera'` and `milestone: 'Q4 Milestone'` → both `null`. Added `ownerId` ObjectId reference to `users`.
| `progress` | Number | Optional | 0 | Range: 0 to 100 (%) | None | None | User-edited |
| `dependencies` | Array<ObjectId>| Optional | `[]` | Array of RoadmapItem IDs | `roadmap_items._id` | None | User-edited |
| `notes` | String | Optional | '' | Max 1500 chars | None | None | User-edited |

---

### Collection: `releases`
- **Purpose**: Production release governance, Go/No-Go readiness gates, and release candidate tracking.
- **Owning Module**: Module 8 — Roadmap Planning and Visualization.

| Field Name | Type | Status | Default | Validation & Constraints | References | Indexes | Provenance |
|---|---|---|---|---|---|---|---|
| `_id` | ObjectId | Required | Auto | Primary key | None | Unique Primary | System |
| `workspaceId` | ObjectId | Required | None | Valid Workspace ID | `workspaces._id` | Compound Unique (`workspaceId`, `version`) | System |
| `name` | String | Required | None | Max 150 chars | None | None | User-edited |
| `version` | String | Required | None | Max 50 chars | None | Compound Unique | User-edited |
| `description` | String | Optional | '' | Max 2000 chars | None | None | User-edited |
| `plannedDate` | String | Required | None | Regex: `^\d{4}-\d{2}-\d{2}$` | None | Indexed | User-edited |
| `owner` | String | Optional | `null` | Owner name | None | None | User-edited |
| `ownerId` | ObjectId | Optional | `null` | Valid User ID | `users._id` | None | System |

> **Corrected**: Removed fabricated `owner: 'Alex Rivera'` → `null`. Added `ownerId` ObjectId reference. Empty checklist now yields `readinessPercent: 0` and `isGated: true`.
| `status` | String | Required | 'In Progress'| Enum `ReleaseStatusesList` | None | Indexed | User-edited |
| `includedFeatureIds`| Array<ObjectId>| Optional| `[]` | Array of Feature IDs | `features._id` | None | User-edited |
| `roadmapItemIds` | Array<ObjectId>| Optional| `[]` | Array of RoadmapItem IDs | `roadmap_items._id` | None | User-edited |
| `checklist` | Array<Subdoc>| Optional | Standard gates | Quality gate verification items | None | None | User-edited |
| `releaseNotes` | String | Optional | '' | Markdown release notes | None | None | User-edited |
| `readinessPercent`| Virtual | Read-only | Computed | Percentage of completed checks | None | Virtual | Derived |
| `isGated` | Virtual | Read-only | Computed | True if any required check remains incomplete | None | Virtual | Derived |

---

### Collection: `product_experiments`
- **Purpose**: A/B and multivariate hypothesis testing with baseline vs. observed telemetry metrics.
- **Owning Module**: Supporting Module — Product Experimentation Lab.

| Field Name | Type | Status | Default | Validation & Constraints | References | Indexes | Provenance |
|---|---|---|---|---|---|---|---|
| `_id` | ObjectId | Required | Auto | Primary key | None | Unique Primary | System |
| `workspaceId` | ObjectId | Required | None | Valid Workspace ID | `workspaces._id` | Compound Indexed | System |
| `name` | String | Required | None | Max 150 chars | None | None | User-edited |
| `problem` | String | Optional | '' | Max 1500 chars | None | None | User-edited |
| `hypothesis` | String | Required | None | Max 2000 chars | None | None | User-edited |
| `targetAudience` | String | Optional | 'All active users' | Max 200 chars | None | None | User-edited |
| `proposedChange` | String | Optional | '' | Max 1500 chars | None | None | User-edited |
| `successMetric` | String | Required | None | Max 120 chars | None | None | User-edited |
| `baseline` | Number | Required | 0 | Numeric baseline | None | None | User-edited |
| `target` | Number | Required | 0 | Numeric target | None | None | User-edited |
| `observedValue` | Number | Optional | `null` | Numeric observed | None | None | Telemetry/User |
| `startDate` | String | Required | None | Regex: `^\d{4}-\d{2}-\d{2}$` | None | None | User-edited |
| `endDate` | String | Required | None | Regex: `^\d{4}-\d{2}-\d{2}$` | None | None | User-edited |
| `linkedFeatureId`| ObjectId | Optional | `null` | Valid Feature ID | `features._id` | Indexed | User-edited |
| `owner` | String | Optional | `null` | Owner name | None | None | User-edited |

> **Corrected**: Removed fabricated `owner: 'Marcus Chen'` → `null`. Changed `observedValue` default from `0` to `null` (no observation until experiment concludes).
| `status` | String | Required | 'Running' | Enum `ExperimentStatusesList` | None | Compound Indexed | User-edited |
| `conclusion` | String | Optional | 'Continue' | Enum `ExperimentConclusionsList` | None | None | User-edited |
| `notes` | String | Optional | '' | Max 2000 chars | None | None | User-edited |

---

### Collection: `customer_journeys`
- **Purpose**: 5-stage lifecycle touchpoint mapping (Discovery, Onboarding, Activation, Engagement, Retention).
- **Owning Module**: Supporting Module — Customer Journey Mapping.

| Field Name | Type | Status | Default | Validation & Constraints | References | Indexes | Provenance |
|---|---|---|---|---|---|---|---|
| `_id` | ObjectId | Required | Auto | Primary key | None | Unique Primary | System |
| `workspaceId` | ObjectId | Required | None | Valid Workspace ID | `workspaces._id` | Compound Unique (`workspaceId`, `order`) | System |
| `name` | String | Required | None | Max 100 chars | None | None | System/User |
| `order` | Number | Required | None | Range: 1 to 10 | None | Compound Unique | System |
| `description` | String | Optional | '' | Max 1500 chars | None | None | User-edited |
| `touchpoints` | Array<Subdoc>| Optional | `[]` | Touchpoint items with sentiment & opportunity | None | None | User-edited |

---

## 6. Module 9: Conversational Product Intelligence Assistant (Copilot)

### Collection: `copilot_conversations`
- **Purpose**: Persisted chat threads between the product manager and AI Copilot.
- **Owning Module**: Module 9 — Conversational Product Intelligence Assistant.

| Field Name | Type | Status | Default | Validation & Constraints | References | Indexes | Provenance |
|---|---|---|---|---|---|---|---|
| `_id` | ObjectId | Required | Auto | Primary key | None | Unique Primary | System |
| `workspaceId` | ObjectId | Required | None | Valid Workspace ID | `workspaces._id` | Compound Indexed | System |
| `userId` | ObjectId | Required | None | Valid User ID | `users._id` | Compound Indexed | System |
| `title` | String | Required | 'Strategy Session' | Max 150 chars | None | None | User-edited |
| `isArchived` | Boolean | Optional | false | Boolean | None | Indexed | User-edited |
| `lastMessageAt` | Date | Required | Date.now | Valid Date | None | Compound Indexed | System |
| `createdAt` | Date | Required | Date.now | Auto timestamp | None | None | System |
| `updatedAt` | Date | Required | Date.now | Auto timestamp | None | None | System |

---

### Collection: `copilot_messages`
- **Purpose**: Individual conversation turns with role, content, and workspace evidence citations.
- **Owning Module**: Module 9 — Conversational Product Intelligence Assistant.

| Field Name | Type | Status | Default | Validation & Constraints | References | Indexes | Provenance |
|---|---|---|---|---|---|---|---|
| `_id` | ObjectId | Required | Auto | Primary key | None | Unique Primary | System |
| `workspaceId` | ObjectId | Required | None | Valid Workspace ID | `workspaces._id` | Indexed | System |
| `conversationId`| ObjectId | Required | None | Valid Conversation ID | `copilot_conversations._id` | Compound (`conversationId`, `createdAt`) | System |
| `role` | String | Required | 'user' | Enum `CopilotRolesList` (`'user'`, `'assistant'`, `'system'`) | None | None | User/AI |
| `content` | String | Required | None | Max 10,000 chars | None | None | User/AI |
| `evidence` | Array<Subdoc>| Optional | `[]` | Citations referencing feedback, features, PRDs | None | None | AI-generated |
| `modelInfo` | Subdoc | Optional | Default model | Model provider and token tracking | None | None | System |
| `createdAt` | Date | Required | Date.now | Auto timestamp | None | Compound Indexed | System |

---

## 7. Module 10: Reporting, Audit & Saved Views

### Collection: `saved_reports`
- **Purpose**: Persistent user-customized dashboard layouts, filtered reports, and widget preferences.
- **Owning Module**: Module 10 — Reporting and Insights Dashboard.

| Field Name | Type | Status | Default | Validation & Constraints | References | Indexes | Provenance |
|---|---|---|---|---|---|---|---|
| `_id` | ObjectId | Required | Auto | Primary key | None | Unique Primary | System |
| `workspaceId` | ObjectId | Required | None | Valid Workspace ID | `workspaces._id` | Compound (`workspaceId`, `createdAt`) | System |
| `createdBy` | ObjectId | Required | None | Valid User ID | `users._id` | None | System |
| `title` | String | Required | None | Max 150 chars | None | None | User-edited |
| `reportType` | String | Required | 'executive_kpi' | Enum report types | None | Indexed | User-edited |
| `filters` | Mixed | Optional | `{ timeRange: '30d' }` | Query parameters | None | None | User-edited |
| `layoutConfig` | Array<String> | Optional | Default layout | Array of widget IDs | None | None | User-edited |
| `isFavorite` | Boolean | Optional | false | Boolean | None | None | User-edited |
| `createdAt` | Date | Required | Date.now | Auto timestamp | None | None | System |
| `updatedAt` | Date | Required | Date.now | Auto timestamp | None | None | System |

---

### Collection: `audit_logs`
- **Purpose**: Complete activity history, actor attribution, before/after JSON diffs, and 1-click reversible undo.
- **Owning Module**: Cross-Cutting — Provenance, Auditability & Activity History.

| Field Name | Type | Status | Default | Validation & Constraints | References | Indexes | Provenance |
|---|---|---|---|---|---|---|---|
| `_id` | ObjectId | Required | Auto | Primary key | None | Unique Primary | System |
| `workspaceId` | ObjectId | Required | None | Valid Workspace ID | `workspaces._id` | Compound (`workspaceId`, `createdAt`) | System |
| `actor` | String | Required | `'System'` | Max 120 chars | None | None | System/User |
| `userId` | ObjectId | Optional | `null` | Valid User ID | `users._id` | None | System |
| `entityType` | String | Required | None | Enum `AuditEntityTypesList` | None | Compound Indexed | System |
| `entityId` | String | Required | None | ID of changed entity | None | Compound Indexed | System |
| `action` | String | Required | None | Enum `AuditActionsList` | None | Indexed | System |
| `description` | String | Required | None | Max 1000 chars | None | None | System |
| `previousState`| Mixed | Optional | `null` | JSON snapshot before mutation | None | None | System |
| `newState` | Mixed | Optional | `null` | JSON snapshot after mutation | None | None | System |
| `canUndo` | Boolean | Optional | `false` | Boolean, validated by pre-validate hook | None | Indexed | System |
| `expiresAt` | Date | Required | +180 days | TTL Index (`expires: 0`) | None | TTL Index | System |
| `createdAt` | Date | Required | Date.now | Auto timestamp | None | Compound Indexed | System |

> **Corrected**: Removed fabricated `actor: 'Alex Rivera'` → default `'System'`. Changed `canUndo` default from `true` to `false`. Pre-validate hook enforces: only reversible actions (`created`, `updated`, `deleted`) with `previousState` snapshot can have `canUndo: true`.
