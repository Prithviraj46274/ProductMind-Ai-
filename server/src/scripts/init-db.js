/**
 * ProductMind AI — Database Initialization and Index Creation Script
 * Connects to MongoDB, registers all models, and synchronizes indexes to create collections.
 */
import dotenv from 'dotenv'
dotenv.config()

import { connectDatabase, disconnectDatabase, sanitizeMongoUri } from '../database/mongodb.js'
import * as models from '../models/index.js'

async function initDb() {
  console.log('Connecting to MongoDB...')
  try {
    const mongooseInstance = await connectDatabase()
    console.log(`Connected to: ${sanitizeMongoUri(process.env.MONGODB_URI)}`)
    console.log(`Database name: ${mongooseInstance.connection.name}`)

    const modelNames = Object.keys(models)
    console.log(`\nInitializing indexes for ${modelNames.length} models...`)

    for (const name of modelNames) {
      const Model = models[name]
      if (Model) {
        try {
          if (Model.syncIndexes) {
            await Model.syncIndexes()
          } else if (Model.init) {
            await Model.init()
          }
          console.log(`✓ Synchronized collection & indexes: ${Model.collection.name} (${name})`)
        } catch (err) {
          // If options changed, attempt to drop index and recreate
          try {
            await Model.init()
            console.log(`✓ Re-initialized indexes: ${Model.collection.name} (${name})`)
          } catch (initErr) {
            console.warn(`⚠️ Warning initializing ${name}: ${initErr.message}`)
          }
        }
      }
    }

    const collections = await mongooseInstance.connection.db.listCollections().toArray()
    console.log('\nActive collections in database:')
    collections.forEach((c) => console.log(` - ${c.name}`))

    console.log('\nDatabase synchronization completed successfully.')
  } catch (err) {
    console.error(`Database connection or synchronization error: ${err.message}`)
  } finally {
    await disconnectDatabase()
  }
}

initDb()
