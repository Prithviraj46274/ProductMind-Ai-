/**
 * ProductMind AI — Copilot Conversation Model
 * Manages conversational session threads between product managers and the AI Copilot.
 */
import mongoose from 'mongoose'

const CopilotConversationSchema = new mongoose.Schema(
  {
    workspaceId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Workspace',
      required: [true, 'Workspace reference is required'],
      index: true,
    },
    userId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'User',
      required: [true, 'User reference is required'],
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
      required: [true, 'Conversation title is required'],
      trim: true,
      maxlength: [150, 'Title cannot exceed 150 characters'],
      default: 'Strategy Session',
    },
    isArchived: {
      type: Boolean,
      default: false,
      index: true,
    },
    lastMessageAt: {
      type: Date,
      default: Date.now,
      index: true,
    },
  },
  {
    timestamps: true,
    collection: 'copilot_conversations',
  }
)

// Index for listing active conversations for a user in a workspace
CopilotConversationSchema.index({ workspaceId: 1, userId: 1, lastMessageAt: -1 })

export const CopilotConversation = mongoose.model('CopilotConversation', CopilotConversationSchema)
export default CopilotConversation
