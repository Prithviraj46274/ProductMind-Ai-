/**
 * ProductMind AI — Feedback Item Model
 * Stores individual customer feedback records, source metadata, sentiment, and feature links.
 * Distinguishes source-provided data from AI-classified themes and predictions.
 */
import mongoose from 'mongoose'
import {
  FeedbackCategoriesList,
  FeedbackCategory,
  FeedbackSentimentsList,
  FeedbackSentiment,
  FeedbackPrioritiesList,
  FeedbackSourceTypesList,
  FeedbackSourceType,
  FeedbackProcessingStatusesList,
  FeedbackProcessingStatus,
} from '../../constants/enums.js'

const FeedbackItemSchema = new mongoose.Schema(
  {
    workspaceId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Workspace',
      required: [true, 'Workspace reference is required'],
      index: true,
    },
    batchId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'FeedbackBatch',
      default: null,
      index: true,
    },
    externalId: {
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
    sourceType: {
      type: String,
      enum: {
        values: FeedbackSourceTypesList,
        message: '{VALUE} is not a valid feedback source',
      },
      default: FeedbackSourceType.MANUAL,
    },
    sourceUrl: {
      type: String,
      trim: true,
      maxlength: 500,
      default: null,
    },
    title: {
      type: String,
      required: [true, 'Feedback title is required'],
      trim: true,
      minlength: [3, 'Feedback title must be at least 3 characters'],
      maxlength: [300, 'Feedback title cannot exceed 300 characters'],
    },
    description: {
      type: String,
      required: [true, 'Feedback description is required'],
      trim: true,
      maxlength: [5000, 'Feedback description cannot exceed 5000 characters'],
    },
    customerName: {
      type: String,
      trim: true,
      maxlength: 120,
      default: null, // Null when unknown from source; never fabricated
    },
    customerEmail: {
      type: String,
      trim: true,
      lowercase: true,
      maxlength: 150,
      default: null,
    },
    companyName: {
      type: String,
      trim: true,
      maxlength: 150,
      default: null, // Null when unknown from source; never fabricated
    },
    category: {
      type: String,
      enum: {
        values: [...FeedbackCategoriesList, null],
        message: '{VALUE} is not a valid feedback category',
      },
      default: null,
      index: true,
    },
    sentiment: {
      type: String,
      enum: {
        values: [...FeedbackSentimentsList, null],
        message: '{VALUE} is not a valid sentiment classification',
      },
      default: null,
      index: true,
    },
    // Priority explicitly stated by external source/customer
    sourcePriority: {
      type: String,
      enum: {
        values: [...FeedbackPrioritiesList, null],
        message: '{VALUE} is not a valid feedback priority',
      },
      default: null,
      index: true,
    },
    // AI-predicted priority (distinct from customer-stated priority)
    aiPredictedPriority: {
      type: String,
      enum: {
        values: [...FeedbackPrioritiesList, null],
        message: '{VALUE} is not a valid predicted priority',
      },
      default: null,
    },
    // Source-provided tags (e.g. from Zendesk / GitHub / CSV)
    sourceTags: {
      type: [String],
      default: [],
      validate: [(tags) => tags.length <= 20, 'Cannot exceed 20 source tags'],
    },
    // AI-inferred domain themes (e.g. #performance, #integrations)
    aiThemes: {
      type: [String],
      default: [],
      validate: [(themes) => themes.length <= 20, 'Cannot exceed 20 AI themes'],
    },
    // General tags (backward compatible with frontend tags array)
    tags: {
      type: [String],
      default: [],
      validate: [(tags) => tags.length <= 20, 'Cannot exceed 20 tags per feedback record'],
    },
    feedbackDate: {
      type: Date,
      default: Date.now,
      index: true,
    },
    // Authoritative Group Membership: FeedbackItem points to FeatureGroup
    featureGroupId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'FeatureGroup',
      default: null,
      index: true,
    },
    promotedFeatureId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Feature',
      default: null,
      index: true,
    },
    // Null until an actual AI classification job executes
    classificationConfidence: {
      type: Number,
      min: 0,
      max: 1,
      default: null,
    },
    processingStatus: {
      type: String,
      enum: {
        values: FeedbackProcessingStatusesList,
        message: '{VALUE} is not a valid processing status',
      },
      default: FeedbackProcessingStatus.RAW,
      index: true,
    },
    // Vector embedding support for future Atlas Vector Search
    embedding: {
      type: [Number],
      select: false, // Don't return vectors in normal queries
      default: undefined,
    },
  },
  {
    timestamps: true,
    collection: 'feedback_items',
  }
)

// Compound index: workspace-scoped table sorting by date
FeedbackItemSchema.index({ workspaceId: 1, feedbackDate: -1 })

// Compound index: workspace-scoped filtering by category, sentiment, and source priority
FeedbackItemSchema.index({ workspaceId: 1, category: 1, sentiment: 1, sourcePriority: 1 })

// Workspace + Source + ExternalID deduplication rule:
// Allows GitHub issue #1 and Jira ticket #1 in the same workspace to coexist without collision
FeedbackItemSchema.index(
  { workspaceId: 1, sourceType: 1, externalId: 1 },
  { unique: true, partialFilterExpression: { externalId: { $type: 'string' } } }
)

// Text index for keyword search across title and description
FeedbackItemSchema.index({ title: 'text', description: 'text' })

export const FeedbackItem = mongoose.model('FeedbackItem', FeedbackItemSchema)
export default FeedbackItem
