/**
 * ProductMind AI — Analytics Event Model
 * Ingests raw, granular product usage events with idempotency and query indexing.
 */
import mongoose from 'mongoose'

const AnalyticsEventSchema = new mongoose.Schema(
  {
    workspaceId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Workspace',
      required: [true, 'Workspace reference is required'],
      index: true,
    },
    batchId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'AnalyticsBatch',
      default: null,
      index: true,
    },
    eventId: {
      type: String,
      trim: true,
      maxlength: 120,
      default: null,
    },
    legacyId: {
      type: String,
      trim: true,
      maxlength: 120,
      default: null,
      index: true,
    },
    eventName: {
      type: String,
      required: [true, 'Event name is required'],
      trim: true,
      maxlength: 100,
    },
    eventType: {
      type: String,
      trim: true,
      maxlength: 50,
      default: 'view',
      index: true,
    },
    eventTimestamp: {
      type: Date,
      required: [true, 'Event timestamp is required'],
    },
    date: {
      type: String,
      required: [true, 'Partition date YYYY-MM-DD is required'],
      match: [/^\d{4}-\d{2}-\d{2}$/, 'Date must follow YYYY-MM-DD format'],
      index: true,
    },
    actorId: {
      type: String,
      trim: true,
      maxlength: 100,
      default: null, // No fabricated anonymous ID; null if unauthenticated
      index: true,
    },
    sessionId: {
      type: String,
      trim: true,
      maxlength: 120,
      default: null,
      index: true,
    },
    featureName: {
      type: String,
      required: [true, 'Feature name or module is required'],
      trim: true,
      maxlength: 120,
      index: true,
    },
    durationSeconds: {
      type: Number,
      min: [0, 'Duration cannot be negative'],
      default: null,
    },
    customProperties: {
      type: Map,
      of: mongoose.Schema.Types.Mixed,
      default: () => new Map(),
    },
  },
  {
    timestamps: true,
    collection: 'analytics_events',
  }
)

// Primary timeline query index for workspace events
AnalyticsEventSchema.index({ workspaceId: 1, eventTimestamp: -1 })

// Compound index for feature-level drilldown by date
AnalyticsEventSchema.index({ workspaceId: 1, featureName: 1, date: -1 })

// Idempotent event deduplication per workspace
AnalyticsEventSchema.index(
  { workspaceId: 1, eventId: 1 },
  { unique: true, partialFilterExpression: { eventId: { $type: 'string' } } }
)

// Automatic 90-day retention TTL index on raw events
AnalyticsEventSchema.index({ eventTimestamp: 1 }, { expireAfterSeconds: 90 * 24 * 60 * 60 })

export const AnalyticsEvent = mongoose.model('AnalyticsEvent', AnalyticsEventSchema)
export default AnalyticsEvent
