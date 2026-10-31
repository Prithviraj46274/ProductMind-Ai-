/**
 * ProductMind AI — Workspace Model
 * Represents an isolated organizational tenant containing all domain artifacts.
 */
import mongoose from 'mongoose'
import { WorkspacePlansList, WorkspacePlan } from '../../constants/enums.js'

const WorkspaceSettingsSchema = new mongoose.Schema(
  {
    defaultTheme: {
      type: String,
      enum: ['dark', 'light', 'system'],
      default: 'dark',
    },
    reducedMotion: {
      type: Boolean,
      default: false,
    },
    allowGuestViewers: {
      type: Boolean,
      default: true,
    },
  },
  { _id: false }
)

const WorkspaceSchema = new mongoose.Schema(
  {
    name: {
      type: String,
      required: [true, 'Workspace name is required'],
      trim: true,
      minlength: [2, 'Workspace name must be at least 2 characters'],
      maxlength: [100, 'Workspace name cannot exceed 100 characters'],
    },
    legacyId: {
      type: String,
      trim: true,
      maxlength: 120,
      default: null,
      index: true,
    },
    slug: {
      type: String,
      required: [true, 'Workspace unique slug is required'],
      unique: true,
      trim: true,
      lowercase: true,
      match: [/^[a-z0-9-]+$/, 'Slug may only contain lowercase letters, numbers, and hyphens'],
      index: true,
    },
    ownerId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'User',
      required: [true, 'Workspace must have an owner reference'],
      index: true,
    },
    plan: {
      type: String,
      enum: {
        values: WorkspacePlansList,
        message: '{VALUE} is not a supported workspace plan',
      },
      default: WorkspacePlan.STARTER,
    },
    settings: {
      type: WorkspaceSettingsSchema,
      default: () => ({}),
    },
    isArchived: {
      type: Boolean,
      default: false,
      index: true,
    },
  },
  {
    timestamps: true,
    collection: 'workspaces',
  }
)

export const Workspace = mongoose.model('Workspace', WorkspaceSchema)
export default Workspace
