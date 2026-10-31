/**
 * ProductMind AI — Auth Session Model
 * Stores persistent refresh tokens (hashed) and supports session revocation with TTL expiry.
 */
import mongoose from 'mongoose'

const AuthSessionSchema = new mongoose.Schema(
  {
    userId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'User',
      required: [true, 'User reference is required for session'],
      index: true,
    },
    sessionFamily: {
      type: String,
      required: [true, 'Session family identifier is required'],
      index: true,
    },
    tokenHash: {
      type: String,
      required: [true, 'Hashed token is required'],
      unique: true,
      select: false,
    },
    userAgent: {
      type: String,
      trim: true,
      maxlength: 300,
      default: 'Unknown Browser',
    },
    ipAddress: {
      type: String,
      trim: true,
      maxlength: 45,
      default: '127.0.0.1',
    },
    expiresAt: {
      type: Date,
      required: [true, 'Session expiry date is required'],
      // Automatic TTL index: MongoDB will expire documents when expiresAt is reached
      index: { expires: 0 },
    },
    revokedAt: {
      type: Date,
      default: null,
      index: true,
    },
    lastUsedAt: {
      type: Date,
      default: Date.now,
    },
  },
  {
    timestamps: true,
    collection: 'auth_sessions',
  }
)

export const AuthSession = mongoose.model('AuthSession', AuthSessionSchema)
export default AuthSession
