/**
 * ProductMind AI — Customer Persona Model
 * Synthesizes customer feedback archetypes, goals, frustrations, and product needs.
 */
import mongoose from 'mongoose'

const CustomerPersonaSchema = new mongoose.Schema(
  {
    workspaceId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Workspace',
      required: [true, 'Workspace reference is required'],
      index: true,
    },
    name: {
      type: String,
      required: [true, 'Persona name is required'],
      trim: true,
      maxlength: 100,
    },
    role: {
      type: String,
      required: [true, 'Professional role or title is required'],
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
    companyType: {
      type: String,
      trim: true,
      maxlength: 120,
      default: null,
    },
    avatar: {
      type: String,
      trim: true,
      maxlength: 10,
      default: null,
    },
    description: {
      type: String,
      trim: true,
      maxlength: 2000,
      default: '',
    },
    goals: {
      type: [String],
      default: [],
    },
    frustrations: {
      type: [String],
      default: [],
    },
    needs: {
      type: [String],
      default: [],
    },
    featurePreferences: {
      type: [String],
      default: [],
    },
    sentimentSummary: {
      type: String,
      trim: true,
      maxlength: 100,
      default: null,
    },
    relatedFeedbackCount: {
      type: Number,
      default: 0,
      min: 0,
    },
    isFavorite: {
      type: Boolean,
      default: false,
      index: true,
    },
  },
  {
    timestamps: true,
    collection: 'customer_personas',
  }
)

CustomerPersonaSchema.index({ workspaceId: 1, isFavorite: -1, createdAt: -1 })

export const CustomerPersona = mongoose.model('CustomerPersona', CustomerPersonaSchema)
export default CustomerPersona
