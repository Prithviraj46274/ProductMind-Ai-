/**
 * ProductMind AI — Feature Group Model
 * Clusters raw feedback items into actionable feature opportunity groups.
 */
import mongoose from 'mongoose'
import {
  FeedbackCategoriesList,
  FeedbackCategory,
  FeatureGroupStatusesList,
  FeatureGroupStatus,
} from '../../constants/enums.js'

const SentimentDistributionSchema = new mongoose.Schema(
  {
    Positive: { type: Number, default: 0, min: 0 },
    Neutral: { type: Number, default: 0, min: 0 },
    Negative: { type: Number, default: 0, min: 0 },
  },
  { _id: false }
)

const FeatureGroupSchema = new mongoose.Schema(
  {
    workspaceId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Workspace',
      required: [true, 'Workspace reference is required'],
      index: true,
    },
    legacyId: {
      type: String,
      trim: true,
      maxlength: 120,
      default: null,
      index: true,
    },
    title: {
      type: String,
      required: [true, 'Feature group title is required'],
      trim: true,
      maxlength: [200, 'Title cannot exceed 200 characters'],
    },
    category: {
      type: String,
      enum: {
        values: FeedbackCategoriesList,
        message: '{VALUE} is not a valid feedback category',
      },
      default: FeedbackCategory.FEATURE_REQUESTS,
      index: true,
    },
    primaryTag: {
      type: String,
      trim: true,
      lowercase: true,
      default: 'general',
      index: true,
    },
    description: {
      type: String,
      trim: true,
      maxlength: 2000,
      default: '',
    },
    status: {
      type: String,
      enum: {
        values: FeatureGroupStatusesList,
        message: '{VALUE} is not a valid feature group status',
      },
      default: FeatureGroupStatus.SUGGESTED,
      index: true,
    },
    sentimentDistribution: {
      type: SentimentDistributionSchema,
      default: () => ({ Positive: 0, Neutral: 0, Negative: 0 }),
    },
    painPoints: {
      type: [String],
      default: [],
      validate: [
        (items) => items.length <= 10,
        'Cannot store more than 10 recurring pain point excerpts',
      ],
    },
    // Cached derived count. Authoritative link is stored on FeedbackItem.featureGroupId
    feedbackCount: {
      type: Number,
      default: 0,
      min: 0,
      index: true,
    },
    promotedFeatureId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Feature',
      default: null,
      index: true,
    },
    mergedIntoGroupId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'FeatureGroup',
      default: null,
    },
    reviewedBy: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'User',
      default: null,
    },
    reviewedAt: {
      type: Date,
      default: null,
    },
  },
  {
    timestamps: true,
    collection: 'feature_groups',
  }
)

// Index for listing feature clusters sorted by feedback volume
FeatureGroupSchema.index({ workspaceId: 1, feedbackCount: -1 })

// Compound index for status filtering
FeatureGroupSchema.index({ workspaceId: 1, status: 1, category: 1 })

export const FeatureGroup = mongoose.model('FeatureGroup', FeatureGroupSchema)
export default FeatureGroup
