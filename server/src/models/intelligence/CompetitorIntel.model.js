/**
 * ProductMind AI — Competitor Intelligence Model
 * Stores competitive benchmark parity, strengths, weaknesses, and key differentiators.
 */
import mongoose from 'mongoose'

const CompetitorIntelSchema = new mongoose.Schema(
  {
    workspaceId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Workspace',
      required: [true, 'Workspace reference is required'],
      index: true,
    },
    name: {
      type: String,
      required: [true, 'Competitor name is required'],
      trim: true,
      maxlength: 120,
    },
    legacyId: {
      type: String,
      trim: true,
      maxlength: 120,
      default: null,
      index: true,
    },
    productDescription: {
      type: String,
      trim: true,
      maxlength: 2000,
      default: '',
    },
    website: {
      type: String,
      trim: true,
      maxlength: 300,
      default: '',
    },
    targetAudience: {
      type: String,
      trim: true,
      maxlength: 200,
      default: null,
    },
    keyFeatures: {
      type: [String],
      default: [],
    },
    strengths: {
      type: [String],
      default: [],
    },
    weaknesses: {
      type: [String],
      default: [],
    },
    differentiators: {
      type: [String],
      default: [],
    },
    researchNotes: {
      type: String,
      trim: true,
      maxlength: 3000,
      default: '',
    },
    lastReviewed: {
      type: Date,
      default: Date.now,
    },
  },
  {
    timestamps: true,
    collection: 'competitor_intel',
  }
)

CompetitorIntelSchema.index({ workspaceId: 1, name: 1 })

export const CompetitorIntel = mongoose.model('CompetitorIntel', CompetitorIntelSchema)
export default CompetitorIntel
