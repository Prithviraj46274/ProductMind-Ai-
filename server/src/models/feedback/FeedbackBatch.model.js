/**
 * ProductMind AI — Feedback Batch Model
 * Tracks ingestion jobs, metadata, column mappings, and validation summaries.
 */
import mongoose from 'mongoose'
import { FeedbackSourceTypesList, FeedbackSourceType } from '../../constants/enums.js'

const RowErrorSampleSchema = new mongoose.Schema(
  {
    rowNumber: { type: Number, required: true },
    field: { type: String, default: 'general' },
    message: { type: String, required: true, maxlength: 200 },
  },
  { _id: false }
)

const FeedbackBatchSchema = new mongoose.Schema(
  {
    workspaceId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Workspace',
      required: [true, 'Workspace reference is required'],
      index: true,
    },
    uploadedBy: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'User',
      required: [true, 'User reference is required'],
    },
    sourceType: {
      type: String,
      enum: {
        values: FeedbackSourceTypesList,
        message: '{VALUE} is not a supported feedback source',
      },
      default: FeedbackSourceType.CSV,
    },
    fileName: {
      type: String,
      trim: true,
      maxlength: 255,
      default: 'import.csv',
    },
    fileHash: {
      type: String,
      trim: true,
      index: true,
      default: null,
    },
    status: {
      type: String,
      enum: ['pending', 'processing', 'completed', 'failed'],
      default: 'pending',
      index: true,
    },
    fieldMappings: {
      type: Map,
      of: String,
      default: () => new Map(),
    },
    totalRows: {
      type: Number,
      default: 0,
      min: 0,
    },
    acceptedRows: {
      type: Number,
      default: 0,
      min: 0,
    },
    rejectedRows: {
      type: Number,
      default: 0,
      min: 0,
    },
    duplicateRows: {
      type: Number,
      default: 0,
      min: 0,
    },
    errorSummary: {
      type: [RowErrorSampleSchema],
      default: [],
      validate: [
        (val) => val.length <= 50,
        'Error summary is capped at 50 samples to prevent unbounded document growth',
      ],
    },
    startedAt: {
      type: Date,
      default: Date.now,
    },
    completedAt: {
      type: Date,
      default: null,
    },
  },
  {
    timestamps: true,
    collection: 'feedback_batches',
  }
)

// Index for listing recent import batches per workspace
FeedbackBatchSchema.index({ workspaceId: 1, createdAt: -1 })

export const FeedbackBatch = mongoose.model('FeedbackBatch', FeedbackBatchSchema)
export default FeedbackBatch
