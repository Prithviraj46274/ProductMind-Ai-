
import mongoose from 'mongoose'

const AnalyticsBatchSchema = new mongoose.Schema(
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
    fileName: {
      type: String,
      trim: true,
      maxlength: 255,
      required: true,
    },
    fileSize: {
      type: Number,
      default: 0,
      min: 0,
    },
    fileHash: {
      type: String,
      trim: true,
      index: true,
      default: null,
    },
    sourceType: {
      type: String,
      enum: ['csv', 'json', 'api_stream'],
      default: 'csv',
    },
    status: {
      type: String,
      enum: ['pending', 'processing', 'completed', 'failed'],
      default: 'pending',
      index: true,
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
    detectedColumns: {
      type: [String],
      default: [],
    },
    mappedColumns: {
      type: Map,
      of: String,
      default: () => new Map(),
    },
    errorSummary: {
      type: [
        new mongoose.Schema(
          { rowNumber: Number, field: String, message: String },
          { _id: false }
        ),
      ],
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
    collection: 'analytics_batches',
  }
)

AnalyticsBatchSchema.index({ workspaceId: 1, createdAt: -1 })

export const AnalyticsBatch = mongoose.model('AnalyticsBatch', AnalyticsBatchSchema)
export default AnalyticsBatch
