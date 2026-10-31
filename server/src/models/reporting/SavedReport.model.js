/**
 * ProductMind AI — Saved Report Model
 * Stores customized dashboard layouts, filtered report views, and export configurations.
 */
import mongoose from 'mongoose'

const SavedReportSchema = new mongoose.Schema(
  {
    workspaceId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Workspace',
      required: [true, 'Workspace reference is required'],
      index: true,
    },
    createdBy: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'User',
      required: [true, 'User creator reference is required'],
    },
    title: {
      type: String,
      required: [true, 'Report title is required'],
      trim: true,
      maxlength: [150, 'Report title cannot exceed 150 characters'],
    },
    reportType: {
      type: String,
      enum: ['executive_kpi', 'sentiment_distribution', 'feature_prioritization', 'analytics_funnel', 'custom_dashboard'],
      default: 'executive_kpi',
      index: true,
    },
    filters: {
      type: mongoose.Schema.Types.Mixed,
      default: () => ({ timeRange: '30d' }),
    },
    layoutConfig: {
      type: [String],
      default: ['kpis', 'trends', 'sentiment', 'priorities'],
    },
    isFavorite: {
      type: Boolean,
      default: false,
    },
  },
  {
    timestamps: true,
    collection: 'saved_reports',
  }
)

SavedReportSchema.index({ workspaceId: 1, createdAt: -1 })

export const SavedReport = mongoose.model('SavedReport', SavedReportSchema)
export default SavedReport
