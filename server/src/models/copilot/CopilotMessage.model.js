/**
 * ProductMind AI — Copilot Message Model
 * Stores individual turns of conversation with role, content, and workspace evidence citations.
 */
import mongoose from 'mongoose'
import { CopilotRolesList, CopilotRole } from '../../constants/enums.js'

const CopilotEvidenceSchema = new mongoose.Schema(
  {
    type: { type: String, required: true }, // 'feedback', 'prioritization', 'prd', 'roadmap', 'analytics'
    label: { type: String, required: true },
    path: { type: String, required: true },
    count: { type: Number, default: 0 },
    entityId: { type: String, default: null },
  },
  { _id: false }
)

const CopilotMessageSchema = new mongoose.Schema(
  {
    workspaceId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Workspace',
      required: [true, 'Workspace reference is required'],
      index: true,
    },
    conversationId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'CopilotConversation',
      required: [true, 'Conversation reference is required'],
      index: true,
    },
    legacyId: {
      type: String,
      trim: true,
      maxlength: 120,
      default: null,
      index: true,
    },
    role: {
      type: String,
      enum: {
        values: CopilotRolesList,
        message: '{VALUE} is not a valid message role',
      },
      default: CopilotRole.USER,
      required: true,
    },
    content: {
      type: String,
      required: [true, 'Message content cannot be empty'],
      trim: true,
      maxlength: [10000, 'Message content cannot exceed 10,000 characters'],
    },
    evidence: {
      type: [CopilotEvidenceSchema],
      default: [],
    },
    modelInfo: {
      provider: { type: String, default: 'deterministic-nlp' },
      modelName: { type: String, default: 'productmind-core-v1' },
      tokensUsed: { type: Number, default: 0 },
    },
  },
  {
    timestamps: true,
    collection: 'copilot_messages',
  }
)

// Efficient chronological message pagination within a conversation
CopilotMessageSchema.index({ conversationId: 1, createdAt: 1 })

export const CopilotMessage = mongoose.model('CopilotMessage', CopilotMessageSchema)
export default CopilotMessage
