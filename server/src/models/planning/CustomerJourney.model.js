/**
 * ProductMind AI — Customer Journey Model
 * Represents customer lifecycle stages, interactive touchpoints, sentiments, and opportunities.
 */
import mongoose from 'mongoose'
import { FeedbackSentimentsList, FeedbackSentiment } from '../../constants/enums.js'

const TouchpointSchema = new mongoose.Schema(
  {
    name: { type: String, required: true, trim: true },
    sentiment: {
      type: String,
      enum: FeedbackSentimentsList,
      default: FeedbackSentiment.POSITIVE,
    },
    painPoints: { type: String, trim: true, default: '' },
    opportunity: { type: String, trim: true, default: '' },
  },
  { _id: true }
)

const CustomerJourneySchema = new mongoose.Schema(
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
      required: [true, 'Journey stage name is required'],
      trim: true,
      maxlength: 100,
    },
    order: {
      type: Number,
      required: true,
      min: 1,
      max: 10,
    },
    description: {
      type: String,
      trim: true,
      maxlength: 1500,
      default: '',
    },
    touchpoints: {
      type: [TouchpointSchema],
      default: [],
    },
  },
  {
    timestamps: true,
    collection: 'customer_journeys',
  }
)

CustomerJourneySchema.index({ workspaceId: 1, order: 1 }, { unique: true })

export const CustomerJourney = mongoose.model('CustomerJourney', CustomerJourneySchema)
export default CustomerJourney
