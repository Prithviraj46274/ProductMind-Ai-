/**
 * ProductMind AI — Workspace Membership Model
 * Connects Users to Workspaces with role-based access control and tenant isolation.
 */
import mongoose from 'mongoose'
import { UserRolesList, UserRole, MembershipStatusesList, MembershipStatus } from '../../constants/enums.js'

const WorkspaceMembershipSchema = new mongoose.Schema(
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
    role: {
      type: String,
      enum: {
        values: UserRolesList,
        message: '{VALUE} is not a valid workspace role',
      },
      default: UserRole.PRODUCT_MANAGER,
    },
    status: {
      type: String,
      enum: {
        values: MembershipStatusesList,
        message: '{VALUE} is not a valid membership status',
      },
      default: MembershipStatus.ACTIVE,
      index: true,
    },
    invitedBy: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'User',
      default: null,
    },
    joinedAt: {
      type: Date,
      default: Date.now,
    },
  },
  {
    timestamps: true,
    collection: 'workspace_memberships',
  }
)

// Ensure each user has at most one membership record per workspace
WorkspaceMembershipSchema.index({ workspaceId: 1, userId: 1 }, { unique: true })

// Compound index for finding all active workspaces for a user
WorkspaceMembershipSchema.index({ userId: 1, status: 1 })

export const WorkspaceMembership = mongoose.model('WorkspaceMembership', WorkspaceMembershipSchema)
export default WorkspaceMembership
