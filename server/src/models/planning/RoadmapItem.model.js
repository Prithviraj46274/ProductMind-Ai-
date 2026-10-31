/**
 * ProductMind AI — Roadmap Item Model
 * Represents milestone schedule items, timelines, progress, and dependencies.
 */
import mongoose from 'mongoose'
import {
  RoadmapStatusesList,
  RoadmapStatus,
  FeedbackPrioritiesList,
  FeedbackPriority,
} from '../../constants/enums.js'

const RoadmapItemSchema = new mongoose.Schema(
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
    releaseId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Release',
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
      required: [true, 'Roadmap item title is required'],
      trim: true,
      minlength: [3, 'Title must be at least 3 characters'],
      maxlength: [200, 'Title cannot exceed 200 characters'],
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
        values: RoadmapStatusesList,
        message: '{VALUE} is not a valid roadmap status',
      },
      default: RoadmapStatus.PLANNED,
      index: true,
    },
    priority: {
      type: String,
      enum: {
        values: FeedbackPrioritiesList,
        message: '{VALUE} is not a valid priority',
      },
      default: FeedbackPriority.MEDIUM,
    },
    owner: {
      type: String,
      trim: true,
      default: null,
    },
    ownerId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'User',
      default: null,
    },
    startDate: {
      type: String,
      required: true,
      match: [/^\d{4}-\d{2}-\d{2}$/, 'Start date must follow YYYY-MM-DD'],
    },
    targetDate: {
      type: String,
      required: true,
      match: [/^\d{4}-\d{2}-\d{2}$/, 'Target date must follow YYYY-MM-DD'],
      index: true,
    },
    milestone: {
      type: String,
      trim: true,
      default: null,
      index: true,
    },
    progress: {
      type: Number,
      min: [0, 'Progress cannot be below 0%'],
      max: [100, 'Progress cannot exceed 100%'],
      default: 0,
    },
    dependencies: {
      type: [
        {
          type: mongoose.Schema.Types.ObjectId,
          ref: 'RoadmapItem',
        },
      ],
      default: [],
    },
    notes: {
      type: String,
      trim: true,
      maxlength: 1500,
      default: '',
    },
  },
  {
    timestamps: true,
    collection: 'roadmap_items',
  }
)

// Index for quarterly Gantt and milestone views
RoadmapItemSchema.index({ workspaceId: 1, milestone: 1, targetDate: 1 })

// Compound index for status board filtering
RoadmapItemSchema.index({ workspaceId: 1, status: 1 })

export const RoadmapItem = mongoose.model('RoadmapItem', RoadmapItemSchema)
export default RoadmapItem
