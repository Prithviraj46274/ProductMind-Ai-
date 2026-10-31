/**
 * ProductMind AI — PRD (Product Requirements Document) Model
 * Implements the comprehensive 13-section specification schema linked to features.
 */
import mongoose from 'mongoose'
import { PRDStatusesList, PRDStatus } from '../../constants/enums.js'

const PRDSectionsSchema = new mongoose.Schema(
  {
    overview: { type: String, default: '', trim: true },
    problemStatement: { type: String, default: '', trim: true },
    targetUsers: { type: String, default: '', trim: true },
    customerPainPoints: { type: String, default: '', trim: true },
    proposedSolution: { type: String, default: '', trim: true },
    goalsAndSuccessMetrics: { type: String, default: '', trim: true },
    functionalRequirements: { type: String, default: '', trim: true },
    nonFunctionalRequirements: { type: String, default: '', trim: true },
    userStories: { type: String, default: '', trim: true },
    acceptanceCriteria: { type: String, default: '', trim: true },
    dependenciesAndConstraints: { type: String, default: '', trim: true },
    risksAndMitigations: { type: String, default: '', trim: true },
    releasePlan: { type: String, default: '', trim: true },
  },
  { _id: false }
)

const PRDSchema = new mongoose.Schema(
  {
    workspaceId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Workspace',
      required: [true, 'Workspace reference is required'],
      index: true,
    },
    featureId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Feature',
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
    title: {
      type: String,
      required: [true, 'PRD title is required'],
      trim: true,
      minlength: [3, 'PRD title must be at least 3 characters'],
      maxlength: [200, 'PRD title cannot exceed 200 characters'],
    },
    version: {
      type: String,
      trim: true,
      default: '1.0.0',
    },
    status: {
      type: String,
      enum: {
        values: PRDStatusesList,
        message: '{VALUE} is not a valid PRD status',
      },
      default: PRDStatus.DRAFT,
      index: true,
    },
    author: {
      type: String,
      trim: true,
      default: null,
    },
    authorId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'User',
      default: null,
    },
    sections: {
      type: PRDSectionsSchema,
      default: () => ({}),
    },
    aiGenerated: {
      type: Boolean,
      default: false,
    },
  },
  {
    timestamps: true,
    collection: 'prds',
  }
)

// Index for locating PRDs by associated feature
PRDSchema.index({ workspaceId: 1, featureId: 1 })

// Index for listing PRDs by recent activity
PRDSchema.index({ workspaceId: 1, updatedAt: -1 })

// Compound index for status filtering
PRDSchema.index({ workspaceId: 1, status: 1 })

export const PRD = mongoose.model('PRD', PRDSchema)
export default PRD
