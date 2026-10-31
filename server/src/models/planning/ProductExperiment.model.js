/**
 * ProductMind AI — Product Experiment Model
 * Models hypothesis-driven experimentation, baseline vs observed metrics, and conclusion governance.
 */
import mongoose from 'mongoose'
import {
  ExperimentStatusesList,
  ExperimentStatus,
  ExperimentConclusionsList,
  ExperimentConclusion,
} from '../../constants/enums.js'

const ProductExperimentSchema = new mongoose.Schema(
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
      required: [true, 'Experiment name is required'],
      trim: true,
      maxlength: 150,
    },
    problem: {
      type: String,
      trim: true,
      maxlength: 1500,
      default: '',
    },
    hypothesis: {
      type: String,
      required: [true, 'Experiment hypothesis is required'],
      trim: true,
      maxlength: 2000,
    },
    targetAudience: {
      type: String,
      trim: true,
      maxlength: 200,
      default: 'All active users',
    },
    proposedChange: {
      type: String,
      trim: true,
      maxlength: 1500,
      default: '',
    },
    successMetric: {
      type: String,
      required: [true, 'Primary success metric name is required'],
      trim: true,
      maxlength: 120,
    },
    baseline: {
      type: Number,
      required: true,
      default: 0,
    },
    target: {
      type: Number,
      required: true,
      default: 0,
    },
    observedValue: {
      type: Number,
      default: null, // Null until telemetry observation occurs
    },
    startDate: {
      type: String,
      required: true,
      match: [/^\d{4}-\d{2}-\d{2}$/, 'Start date must follow YYYY-MM-DD'],
    },
    endDate: {
      type: String,
      required: true,
      match: [/^\d{4}-\d{2}-\d{2}$/, 'End date must follow YYYY-MM-DD'],
    },
    linkedFeatureId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Feature',
      default: null,
      index: true,
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
    status: {
      type: String,
      enum: {
        values: ExperimentStatusesList,
        message: '{VALUE} is not a valid experiment status',
      },
      default: ExperimentStatus.RUNNING,
      index: true,
    },
    conclusion: {
      type: String,
      enum: {
        values: ExperimentConclusionsList,
        message: '{VALUE} is not a valid experiment conclusion',
      },
      default: ExperimentConclusion.CONTINUE,
    },
    notes: {
      type: String,
      trim: true,
      maxlength: 2000,
      default: '',
    },
  },
  {
    timestamps: true,
    collection: 'product_experiments',
  }
)

ProductExperimentSchema.index({ workspaceId: 1, status: 1, createdAt: -1 })

export const ProductExperiment = mongoose.model('ProductExperiment', ProductExperimentSchema)
export default ProductExperiment
