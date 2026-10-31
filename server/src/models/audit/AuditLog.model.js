/**
 * ProductMind AI — Audit Log Model
 * Persists activity history, before/after JSON diffs, and supports 1-click reversible undo.
 * Does not store sensitive tokens, hashes, or passwords.
 */
import mongoose from 'mongoose'
import {
  AuditEntityTypesList,
  AuditActionsList,
} from '../../constants/enums.js'

const AuditLogSchema = new mongoose.Schema(
  {
    workspaceId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Workspace',
      required: [true, 'Workspace reference is required'],
      index: true,
    },
    actor: {
      type: String,
      trim: true,
      required: [true, 'Actor attribution is required'],
      maxlength: 120,
      default: 'System',
    },
    userId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'User',
      default: null,
    },
    entityType: {
      type: String,
      enum: {
        values: AuditEntityTypesList,
        message: '{VALUE} is not an auditable entity type',
      },
      required: true,
      index: true,
    },
    entityId: {
      type: String,
      required: [true, 'Audited entity identifier is required'],
      trim: true,
      index: true,
    },
    action: {
      type: String,
      enum: {
        values: AuditActionsList,
        message: '{VALUE} is not a valid audit action',
      },
      required: true,
      index: true,
    },
    description: {
      type: String,
      required: [true, 'Audit description is required'],
      trim: true,
      maxlength: 1000,
    },
    // Sensitive data (passwords, tokens) must never be passed to previousState or newState
    previousState: {
      type: mongoose.Schema.Types.Mixed,
      default: null,
    },
    newState: {
      type: mongoose.Schema.Types.Mixed,
      default: null,
    },
    canUndo: {
      type: Boolean,
      default: false, // Default false; only enabled if reversible criteria are met
      index: true,
    },
    // Automatic document retention via TTL (180 days default)
    expiresAt: {
      type: Date,
      default: () => {
        const d = new Date()
        d.setDate(d.getDate() + 180)
        return d
      },
      index: { expires: 0 },
    },
  },
  {
    timestamps: true,
    collection: 'audit_logs',
  }
)

// Validate undo eligibility before saving
AuditLogSchema.pre('validate', function (next) {
  // Undo is only eligible if action is reversible and state snapshot exists
  const reversibleActions = ['created', 'updated', 'deleted']
  if (reversibleActions.includes(this.action)) {
    if (this.action === 'created' || this.previousState !== null) {
      if (this.canUndo === undefined) {
        this.canUndo = true
      }
    } else {
      this.canUndo = false
    }
  } else {
    this.canUndo = false
  }
  next()
})

// Primary timeline index for workspace activity log
AuditLogSchema.index({ workspaceId: 1, createdAt: -1 })

// Compound index for entity-specific audit history lookup
AuditLogSchema.index({ workspaceId: 1, entityType: 1, entityId: 1, createdAt: -1 })

export const AuditLog = mongoose.model('AuditLog', AuditLogSchema)
export default AuditLog
