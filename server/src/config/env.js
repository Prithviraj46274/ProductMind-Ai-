/**
 * ProductMind AI — Environment Configuration Module
 * Loads, validates, and normalizes environment variables for the backend.
 */
import dotenv from 'dotenv'

dotenv.config()

/**
 * Validate that required environment variables are set and provide safe defaults.
 */
function getEnvConfig() {
  const nodeEnv = process.env.NODE_ENV || 'development'
  const isProd = nodeEnv === 'production'

  const mongoUri = process.env.MONGODB_URI || 'mongodb://127.0.0.1:27017/productmind_ai'

  if (isProd && (!process.env.MONGODB_URI || process.env.MONGODB_URI.includes('127.0.0.1'))) {
    console.warn('[Config Warning] Production environment detected without a remote MongoDB cluster URI.')
  }

  return {
    nodeEnv,
    isProd,
    port: parseInt(process.env.PORT || '5000', 10),
    mongo: {
      uri: mongoUri,
      maxPoolSize: parseInt(process.env.MONGO_MAX_POOL_SIZE || '50', 10),
      minPoolSize: parseInt(process.env.MONGO_MIN_POOL_SIZE || '5', 10),
      serverSelectionTimeoutMS: 5000,
      socketTimeoutMS: 45000,
    },
    jwt: {
      secret: process.env.JWT_SECRET || 'dev_insecure_jwt_secret_productmind_ai_2026',
      expiresIn: process.env.JWT_EXPIRES_IN || '24h',
      refreshExpiresInDays: parseInt(process.env.REFRESH_TOKEN_EXPIRES_IN_DAYS || '30', 10),
    },
    retention: {
      analyticsDays: parseInt(process.env.ANALYTICS_EVENT_RETENTION_DAYS || '90', 10),
      auditDays: parseInt(process.env.AUDIT_LOG_RETENTION_DAYS || '180', 10),
      sessionDays: parseInt(process.env.AUTH_SESSION_RETENTION_DAYS || '30', 10),
    },
    cors: {
      origin: process.env.CLIENT_ORIGIN || 'http://localhost:5173',
    },
  }
}

export const env = getEnvConfig()
export default env
