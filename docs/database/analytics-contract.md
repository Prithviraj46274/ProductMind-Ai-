# Product Analytics API Contract

Phase 4 Step 11 adds authenticated, workspace-scoped analytics ingestion and measured query APIs under `/api/v1/analytics`. The backend accepts JSON only; it does not add multipart CSV upload or change the frontend.

## Ingestion

### Single event

`POST /api/v1/analytics/events?workspaceId=<id>`

Example:

```json
{
  "eventId": "evt-001",
  "eventName": "Feature opened",
  "eventType": "view",
  "eventTimestamp": "2025-03-08T14:30:00-05:00",
  "featureName": "Dashboard",
  "actorId": "user-001",
  "sessionId": "session-001",
  "durationSeconds": 12
}
```

`eventId`, `eventName`, `eventType`, and an RFC3339 timestamp with a timezone are required. The server stores timestamps in UTC and derives `date` in UTC; a supplied date must match. Actor and session identifiers are optional and are never generated. `featureName` is an optional label; if `featureId` is supplied, it must identify a feature in the same workspace and its name must match. `customProperties` must be empty until a property allow-list is approved. Unknown input fields are rejected.

Each single-event request creates an `AnalyticsBatch` record. A new event returns `201`; an identical replay under the same workspace/event ID returns `200` and does not change the original event's batch provenance. Reusing an event ID for different normalized content returns `409`. An event ID already present on a legacy sample record is reserved and cannot be treated as an ingested duplicate.

### JSON batch

`POST /api/v1/analytics/datasets/upload?workspaceId=<id>`

```json
{
  "items": [
    {
      "eventId": "evt-002",
      "eventName": "Report exported",
      "eventType": "export",
      "eventTimestamp": "2025-03-08T19:30:00Z",
      "featureName": "Reports"
    }
  ]
}
```

Batches contain 1–500 rows and are processed synchronously. Each row is reported as `accepted`, `duplicate`, or `rejected`; `acceptedRows`, `duplicateRows`, and `rejectedRows` are separate counters. Row errors are bounded and omit submitted values. Batch statuses are `processing`, `completed`, `partial`, or `failed`.

`GET /api/v1/analytics/datasets/{batch_id}?workspaceId=<id>` reads workspace-scoped batch status. Retry rejected rows with:

`POST /api/v1/analytics/datasets/{batch_id}/retry?workspaceId=<id>`

```json
{
  "items": [
    {
      "rowNumber": 3,
      "item": {
        "eventId": "evt-003",
        "eventName": "Feature opened",
        "eventType": "view",
        "eventTimestamp": "2025-03-08T19:35:00Z"
      }
    }
  ]
}
```

Only previously rejected row numbers may be retried, and each must retain its original event ID. The retry claim is atomic and events retain the original batch ID. A client may correct other row data and resubmit it with that same ID.

## Queries and definitions

All query routes require `workspaceId` and workspace access:

| Method and route | Purpose |
|---|---|
| `GET /api/v1/analytics/overview` | Event totals, active users, sessions, average event duration, data coverage |
| `GET /api/v1/analytics/usage-trends` | Daily event, user, session, and average event-duration rollups |
| `GET /api/v1/analytics/features` | Paginated feature event counts, feature users, adoption, and average event duration |
| `GET /api/v1/analytics/funnel` | Explicitly reports unavailable until funnel steps and conversion semantics are defined |

Queries accept `timeRange=7d|30d|90d|all` or inclusive UTC `startDate` and `endDate` (not both); the default is `30d`. Explicit ranges may not exceed 365 days. `all` is capped to the latest 365 inclusive days and reports `dateRange.capped=true`. Filters are applied to the workspace-scoped event or rollup query.

- `totalEvents` counts accepted ingested events; duplicates and rejected rows are excluded.
- `activeUsers` counts distinct non-empty `actorId` values. `sessions` counts distinct non-empty `sessionId` values. Each is `null` if any event in its scope is missing that identifier or the retained raw event set is incomplete.
- Feature adoption is feature users divided by known active users. Feature-user and adoption values are `null` when any event in the feature scope is missing an actor ID or the retained raw event set is incomplete.
- `avgEventDurationSeconds` is the mean of supplied numeric `durationSeconds` values only. It is not session duration. `avgSessionDurationSeconds` and `accounts` are unavailable (`null`).
- Coverage is `no_data`, `partial`, or `observed`; `observed` does not mean complete. The response includes identifier coverage counts, retained raw-event availability, observed days, last event time, and calculation time.

## Rollups, sample data, and retention

Accepted events carry a `batchId`; production analytics queries filter on it, excluding legacy sample events that have no batch provenance. Ingested daily aggregates are stored in the additive `ingestedMetrics` subdocument. Existing top-level sample rollup values are not overwritten, and the existing unique `(workspaceId, date)` index remains in place.

Raw events retain the existing 90-day TTL on `eventTimestamp`; daily ingested rollups are not TTL-deleted. Event counts, daily active users/sessions, and duration aggregates remain measured in daily rollups. For ranges where raw events have expired, the backend marks coverage partial and withholds range-wide distinct active-user/session counts rather than estimating them. Feature detail counts reflect available raw events and must be interpreted with the coverage state.

No database initialization, migration, or live database operation is performed by this API implementation.
