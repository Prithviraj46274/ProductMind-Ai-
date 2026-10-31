/**
 * ProductMind AI — Feature Model
 * Represents prioritized product backlog initiatives with 4-factor mathematical scoring.
 * Formula: (0.35 * Impact) + (0.30 * Urgency) + (0.20 * Demand) + (0.15 * Value)
 */
import mongoose from 'mongoose'
import {
  FeatureStatusesList,
  FeatureStatus,
  PriorityTiersList,
  PriorityTier,
  calculatePriorityScore,
  getPriorityTier,
} from '../../constants/enums.js'

const FeatureCommentSchema = new mongoose.Schema(
  {
    author: { type: String, required: true, trim: true },
    authorId: { type: mongoose.Schema.Types.ObjectId, ref: 'User', default: null },
    text: { type: String, required: true, trim: true, maxlength: 1000 },
    createdAt: { type: Date, default: Date.now },
  },
  { _id: true }
)

const FeatureSchema = new mongoose.Schema(
  {
    workspaceId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Workspace',
      required: [true, 'Workspace reference is required'],
      index: true,
    },
    featureGroupId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'FeatureGroup',
      default: null,
      index: true,
    },
    legacyId: {
      type: String,
      trim: true,
      maxlength: 120,
      default: null,
      index: true,
    },
    name: {
      type: String,
      required: [true, 'Feature name is required'],
      trim: true,
      minlength: [3, 'Feature name must be at least 3 characters'],
      maxlength: [200, 'Feature name cannot exceed 200 characters'],
    },
    description: {
      type: String,
      required: [true, 'Feature description is required'],
      trim: true,
      maxlength: [5000, 'Feature description cannot exceed 5000 characters'],
    },
    customerImpact: {
      type: Number,
      required: true,
      min: [1, 'Customer Impact must be between 1 and 10'],
      max: [10, 'Customer Impact must be between 1 and 10'],
      default: 5, // Neutral midpoint; not a fabricated high score
    },
    urgency: {
      type: Number,
      required: true,
      min: [1, 'Urgency must be between 1 and 10'],
      max: [10, 'Urgency must be between 1 and 10'],
      default: 5,
    },
    demand: {
      type: Number,
      required: true,
      min: [1, 'Customer Demand must be between 1 and 10'],
      max: [10, 'Customer Demand must be between 1 and 10'],
      default: 5,
    },
    businessValue: {
      type: Number,
      required: true,
      min: [1, 'Business Value must be between 1 and 10'],
      max: [10, 'Business Value must be between 1 and 10'],
      default: 5,
    },
    score: {
      type: Number,
      min: 1.0,
      max: 10.0,
      default: 5.0,
      index: true,
    },
    priorityTier: {
      type: String,
      enum: {
        values: PriorityTiersList,
        message: '{VALUE} is not a valid priority tier',
      },
      default: PriorityTier.MEDIUM,
      index: true,
    },
    status: {
      type: String,
      enum: {
        values: FeatureStatusesList,
        message: '{VALUE} is not a valid feature status',
      },
      default: FeatureStatus.IN_PLANNING,
      index: true,
    },
    owner: {
      type: String,
      trim: true,
      maxlength: 100,
      default: null, // No fabricated owner name; null until assigned
    },
    ownerId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'User',
      default: null,
    },
    targetRelease: {
      type: String,
      trim: true,
      maxlength: 50,
      default: null, // Null until mapped to an actual release candidate
      index: true,
    },
    comments: {
      type: [FeatureCommentSchema],
      default: [],
      validate: [
        (c) => c.length <= 100,
        'Comments cannot exceed 100 items per feature',
      ],
    },
    aiJustification: {
      type: String,
      trim: true,
      maxlength: 1500,
      default: '',
    },
    isManualOverride: {
      type: Boolean,
      default: false,
    },
  },
  {
    timestamps: true,
    collection: 'features',
  }
)

// Pre-validate middleware: guarantees score and tier are computed deterministically before validation
FeatureSchema.pre('validate', function (next) {
  if (
    this.customerImpact !== undefined &&
    this.urgency !== undefined &&
    this.demand !== undefined &&
    this.businessValue !== undefined
  ) {
    if (!this.isManualOverride) {
      this.score = calculatePriorityScore({
        customerImpact: this.customerImpact,
        urgency: this.urgency,
        demand: this.demand,
        businessValue: this.businessValue,
      })
    }
    this.priorityTier = getPriorityTier(this.score)
  }
  next()
})

// Index for priority-ranked backlog listing
FeatureSchema.index({ workspaceId: 1, score: -1 })

// Compound index for Kanban boards and status pipelines
FeatureSchema.index({ workspaceId: 1, status: 1, priorityTier: 1 })

// Compound index for release planning
FeatureSchema.index({ workspaceId: 1, targetRelease: 1, status: 1 })

export const Feature = mongoose.model('Feature', FeatureSchema)
export default Feature
