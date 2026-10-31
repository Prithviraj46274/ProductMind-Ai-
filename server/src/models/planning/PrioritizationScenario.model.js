/**
 * ProductMind AI — Prioritization Scenario Model
 * Stores What-If hypothetical parameter adjustments and simulated ranking delta sets.
 */
import mongoose from 'mongoose'
import { calculatePriorityScore } from '../../constants/enums.js'

const AdjustedFeatureSchema = new mongoose.Schema(
  {
    featureId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Feature',
      required: true,
    },
    customerImpact: { type: Number, required: true, min: 1, max: 10 },
    urgency: { type: Number, required: true, min: 1, max: 10 },
    demand: { type: Number, required: true, min: 1, max: 10 },
    businessValue: { type: Number, required: true, min: 1, max: 10 },
    simulatedScore: { type: Number, min: 1.0, max: 10.0 },
  },
  { _id: false }
)

AdjustedFeatureSchema.pre('validate', function (next) {
  if (
    this.customerImpact !== undefined &&
    this.urgency !== undefined &&
    this.demand !== undefined &&
    this.businessValue !== undefined
  ) {
    this.simulatedScore = calculatePriorityScore({
      customerImpact: this.customerImpact,
      urgency: this.urgency,
      demand: this.demand,
      businessValue: this.businessValue,
    })
  }
  next()
})

const PrioritizationScenarioSchema = new mongoose.Schema(
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
      required: [true, 'Scenario name is required'],
      trim: true,
      maxlength: [150, 'Scenario name cannot exceed 150 characters'],
    },
    description: {
      type: String,
      trim: true,
      maxlength: 1500,
      default: '',
    },
    createdBy: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'User',
      default: null,
    },
    adjustedFeatures: {
      type: [AdjustedFeatureSchema],
      default: [],
      validate: [
        (list) => list.length <= 50,
        'Cannot simulate more than 50 adjusted features per scenario',
      ],
    },
  },
  {
    timestamps: true,
    collection: 'prioritization_scenarios',
  }
)

PrioritizationScenarioSchema.index({ workspaceId: 1, createdAt: -1 })

export const PrioritizationScenario = mongoose.model('PrioritizationScenario', PrioritizationScenarioSchema)
export default PrioritizationScenario
