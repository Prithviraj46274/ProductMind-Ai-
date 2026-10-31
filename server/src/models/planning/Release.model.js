/**
 * ProductMind AI — Release Model
 * Enforces gated quality governance and release readiness checks before production shipping.
 */
import mongoose from 'mongoose'
import { ReleaseStatusesList, ReleaseStatus } from '../../constants/enums.js'

const ReleaseChecklistItemSchema = new mongoose.Schema(
  {
    title: { type: String, required: true, trim: true },
    completed: { type: Boolean, default: false },
    required: { type: Boolean, default: true },
  },
  { _id: true }
)

const ReleaseSchema = new mongoose.Schema(
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
    name: {
      type: String,
      required: [true, 'Release name is required'],
      trim: true,
      maxlength: 150,
    },
    version: {
      type: String,
      required: [true, 'Release version tag is required'],
      trim: true,
      maxlength: 50,
    },
    description: {
      type: String,
      trim: true,
      maxlength: 2000,
      default: '',
    },
    plannedDate: {
      type: String,
      required: true,
      match: [/^\d{4}-\d{2}-\d{2}$/, 'Planned date must follow YYYY-MM-DD'],
      index: true,
    },
    owner: {
      type: String,
      trim: true,
      default: null, // No fabricated owner
    },
    ownerId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'User',
      default: null,
    },
    status: {
      type: String,
      enum: {
        values: ReleaseStatusesList,
        message: '{VALUE} is not a valid release status',
      },
      default: ReleaseStatus.IN_PROGRESS,
      index: true,
    },
    includedFeatureIds: {
      type: [
        {
          type: mongoose.Schema.Types.ObjectId,
          ref: 'Feature',
        },
      ],
      default: [],
    },
    roadmapItemIds: {
      type: [
        {
          type: mongoose.Schema.Types.ObjectId,
          ref: 'RoadmapItem',
        },
      ],
      default: [],
    },
    checklist: {
      type: [ReleaseChecklistItemSchema],
      default: [],
    },
    releaseNotes: {
      type: String,
      trim: true,
      default: '',
    },
  },
  {
    timestamps: true,
    collection: 'releases',
    toJSON: { virtuals: true },
    toObject: { virtuals: true },
  }
)

// Virtual: calculate readiness completion percentage
// An empty checklist has 0 completed checks (returns 0%, not 100%)
ReleaseSchema.virtual('readinessPercent').get(function () {
  if (!this.checklist || this.checklist.length === 0) return 0
  const completed = this.checklist.filter((c) => c.completed).length
  return Math.round((completed / this.checklist.length) * 100)
})

// Virtual: determine if release is BLOCKED by outstanding required quality checks
// An empty checklist has not satisfied required quality gates and is considered gated (blocked)
ReleaseSchema.virtual('isGated').get(function () {
  if (!this.checklist || this.checklist.length === 0) return true
  return this.checklist.some((c) => c.required && !c.completed)
})

// Unique version tag per workspace
ReleaseSchema.index({ workspaceId: 1, version: 1 }, { unique: true })

export const Release = mongoose.model('Release', ReleaseSchema)
export default Release
