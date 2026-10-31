/**
 * ProductMind AI — User Model
 * Represents global user identity and authentication credentials.
 * Workspace-specific roles and permissions are authoritatively stored in WorkspaceMembership.
 */
import mongoose from 'mongoose'
import bcrypt from 'bcryptjs'

const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const UserSchema = new mongoose.Schema(
  {
    name: {
      type: String,
      required: [true, 'User display name is required'],
      trim: true,
      minlength: [2, 'Name must be at least 2 characters'],
      maxlength: [100, 'Name cannot exceed 100 characters'],
    },
    legacyId: {
      type: String,
      trim: true,
      maxlength: 120,
      default: null,
      index: true,
    },
    email: {
      type: String,
      required: [true, 'Normalized email address is required'],
      unique: true,
      trim: true,
      lowercase: true,
      match: [emailRegex, 'Please provide a valid email address'],
      index: true,
    },
    passwordHash: {
      type: String,
      required: [true, 'Password hash is required'],
      minlength: [8, 'Password hash is invalid'],
      select: false, // Never return passwordHash by default in queries
    },
    // Global platform role (distinct from workspace-specific roles in WorkspaceMembership)
    platformRole: {
      type: String,
      enum: ['user', 'platform_admin'],
      default: 'user',
    },
    avatar: {
      type: String,
      trim: true,
      maxlength: [300, 'Avatar URL cannot exceed 300 characters'],
      default: null,
    },
    theme: {
      type: String,
      enum: ['dark', 'light', 'system'],
      default: 'dark',
    },
    reducedMotion: {
      type: Boolean,
      default: false,
    },
    isActive: {
      type: Boolean,
      default: true,
      index: true,
    },
    emailVerifiedAt: {
      type: Date,
      default: null,
    },
    lastLoginAt: {
      type: Date,
      default: null,
    },
  },
  {
    timestamps: true,
    collection: 'users',
    toJSON: {
      virtuals: true,
      transform: (doc, ret) => {
        delete ret.passwordHash
        delete ret.__v
        return ret
      },
    },
  }
)

// Pre-save hook: lowercase & trim email
UserSchema.pre('save', async function (next) {
  if (this.isModified('email') && this.email) {
    this.email = this.email.toLowerCase().trim()
  }
  next()
})

// Instance method to check password against hash
UserSchema.methods.comparePassword = async function (plainPassword) {
  if (!this.passwordHash) return false
  return bcrypt.compare(plainPassword, this.passwordHash)
}

// Static method to create a password hash safely
UserSchema.statics.hashPassword = async function (plainPassword) {
  const salt = await bcrypt.genSalt(10)
  return bcrypt.hash(plainPassword, salt)
}

export const User = mongoose.model('User', UserSchema)
export default User
