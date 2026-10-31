/**
 * ProductMind AI — MongoDB Connection Lifecycle Manager
 * Establishes, monitors, and gracefully terminates the Mongoose connection pool.
 */
import mongoose from 'mongoose'
import env from '../config/env.js'

let isConnected = false
let connectionPromise = null

/**
 * Mask sensitive credentials from a MongoDB connection URI for safe logging
 */
export function sanitizeMongoUri(uri) {
  if (!uri) return ''
  try {
    return uri.replace(/\/\/([^:]+):([^@]+)@/, '//$1:***@')
  } catch {
    return '[Protected URI]'
  }
}

/**
 * Connect to MongoDB with connection pooling and error resilience
 * @param {string} [customUri] Optional custom URI override for testing
 * @returns {Promise<typeof mongoose>}
 */
export async function connectDatabase(customUri = null) {
  if (isConnected && mongoose.connection.readyState === 1) {
    return mongoose
  }

  if (connectionPromise) {
    return connectionPromise
  }

  const uri = customUri || env.mongo.uri

  if (!uri) {
    throw new Error('[Database Error] MongoDB URI is missing in configuration.')
  }

  const options = {
    maxPoolSize: env.mongo.maxPoolSize,
    minPoolSize: env.mongo.minPoolSize,
    serverSelectionTimeoutMS: env.mongo.serverSelectionTimeoutMS,
    socketTimeoutMS: env.mongo.socketTimeoutMS,
    autoIndex: true, // Build defined schema indexes automatically in non-prod
  }

  connectionPromise = mongoose.connect(uri, options)
    .then((m) => {
      isConnected = true
      connectionPromise = null
      const safeUri = sanitizeMongoUri(uri)
      console.log(`[Database] Successfully connected to MongoDB at ${safeUri}`)
      return m
    })
    .catch((err) => {
      isConnected = false
      connectionPromise = null
      console.error(`[Database Error] Failed to connect to MongoDB: ${err.message}`)
      throw err
    })

  return connectionPromise
}

/**
 * Disconnect from MongoDB cleanly
 */
export async function disconnectDatabase() {
  if (!isConnected && mongoose.connection.readyState === 0) {
    return
  }

  try {
    await mongoose.disconnect()
    isConnected = false
    connectionPromise = null
    console.log('[Database] MongoDB connection closed gracefully.')
  } catch (err) {
    console.error(`[Database Error] Error during disconnection: ${err.message}`)
    throw err
  }
}

/**
 * Check current MongoDB health state
 */
export function getDatabaseStatus() {
  const states = {
    0: 'disconnected',
    1: 'connected',
    2: 'connecting',
    3: 'disconnecting',
  }
  const stateCode = mongoose.connection.readyState
  return {
    state: states[stateCode] || 'unknown',
    readyState: stateCode,
    isConnected: stateCode === 1,
    host: mongoose.connection.host || null,
    port: mongoose.connection.port || null,
    name: mongoose.connection.name || null,
  }
}

// Global Mongoose event listeners
mongoose.connection.on('error', (err) => {
  console.error(`[Database Event] MongoDB connection error: ${err.message}`)
})

mongoose.connection.on('disconnected', () => {
  isConnected = false
  console.warn('[Database Event] MongoDB disconnected.')
})

mongoose.connection.on('reconnected', () => {
  isConnected = true
  console.log('[Database Event] MongoDB reconnected successfully.')
})

// Graceful process exit handling
const handleProcessTermination = async (signal) => {
  console.log(`\n[Database] Process received ${signal}. Initiating graceful MongoDB shutdown...`)
  try {
    await disconnectDatabase()
    process.exit(0)
  } catch {
    process.exit(1)
  }
}

process.once('SIGINT', () => handleProcessTermination('SIGINT'))
process.once('SIGTERM', () => handleProcessTermination('SIGTERM'))

export default {
  connectDatabase,
  disconnectDatabase,
  getDatabaseStatus,
  sanitizeMongoUri,
}
