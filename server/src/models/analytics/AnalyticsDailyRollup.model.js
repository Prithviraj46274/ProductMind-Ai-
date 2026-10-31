/**
 * ProductMind AI — Analytics Daily Rollup Model
 * Precomputed daily metric aggregations powering instantaneous dashboard visualizations.
 */
import mongoose from 'mongoose'

const FeatureMetricSchema = new mongoose.Schema(
  {
    name: { type: String, required: true },
    eventCount: { type: Number, default: 0, min: 0 },
    uniqueUsers: { type: Number, default: 0, min: 0 },
    adoptionPercent: { type: Number, default: 0, min: 0, max: 100 },
    avgDurationSec: { type: Number, default: 0, min: 0 },
    completionRate: { type: Number, default: 0, min: 0, max: 100 },
  },
  { _id: false }
)

const FunnelStepMetricSchema = new mongoose.Schema(
  {
    step: { type: String, required: true },
    users: { type: Number, default: 0, min: 0 },
    conversionRate: { type: Number, default: 0, min: 0, max: 100 },
    dropOffRate: { type: Number, default: 0, min: 0, max: 100 },
  },
  { _id: false }
)

const AnalyticsDailyRollupSchema = new mongoose.Schema(
  {
    workspaceId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Workspace',
      required: [true, 'Workspace reference is required'],
      index: true,
    },
    date: {
      type: String,
      required: [true, 'Partition date YYYY-MM-DD is required'],
      match: [/^\d{4}-\d{2}-\d{2}$/, 'Date must follow YYYY-MM-DD format'],
      index: true,
    },
    activeUsers: {
      type: Number,
      default: 0,
      min: [0, 'Active users cannot be negative'],
    },
    totalSessions: {
      type: Number,
      default: 0,
      min: 0,
    },
    totalEvents: {
      type: Number,
      default: 0,
      min: 0,
    },
    avgSessionDuration: {
      type: Number,
      default: 0,
      min: 0,
    },
    topFeature: {
      type: String,
      default: null,
    },
    featureMetrics: {
      type: [FeatureMetricSchema],
      default: [],
    },
    funnelMetrics: {
      type: [FunnelStepMetricSchema],
      default: [],
    },
    calculatedAt: {
      type: Date,
      default: Date.now,
    },
  },
  {
    timestamps: true,
    collection: 'analytics_daily_rollups',
  }
)

// One authoritative rollup per workspace per day
AnalyticsDailyRollupSchema.index({ workspaceId: 1, date: 1 }, { unique: true })

// Fast range lookup for trend line charts (e.g. 7d, 30d, 90d)
AnalyticsDailyRollupSchema.index({ workspaceId: 1, date: -1 })

export const AnalyticsDailyRollup = mongoose.model('AnalyticsDailyRollup', AnalyticsDailyRollupSchema)
export default AnalyticsDailyRollup
