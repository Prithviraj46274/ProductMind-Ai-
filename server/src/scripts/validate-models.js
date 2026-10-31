/**
 * ProductMind AI — Model Layer Diagnostic Validator
 * Validates that all Mongoose models, schemas, validations, and indexes load cleanly.
 */
import mongoose from 'mongoose'
import * as models from '../models/index.js'

function validateModelLayer() {
  console.log('======================================================================')
  console.log('ProductMind AI — Database Architecture Model Validator')
  console.log('======================================================================\n')

  const expectedModels = [
    'User',
    'Workspace',
    'WorkspaceMembership',
    'AuthSession',
    'FeedbackBatch',
    'FeedbackItem',
    'AnalyticsBatch',
    'AnalyticsEvent',
    'AnalyticsDailyRollup',
    'FeatureGroup',
    'CustomerPersona',
    'CompetitorIntel',
    'Feature',
    'PrioritizationScenario',
    'PRD',
    'RoadmapItem',
    'Release',
    'ProductExperiment',
    'CustomerJourney',
    'CopilotConversation',
    'CopilotMessage',
    'SavedReport',
    'AuditLog',
  ]

  let passed = 0
  let failed = 0

  expectedModels.forEach((name) => {
    const ModelClass = models[name]
    if (!ModelClass) {
      console.error(`❌ [Missing Model] ${name} is not exported in models registry.`)
      failed++
      return
    }

    const schema = ModelClass.schema
    if (!schema) {
      console.error(`❌ [Invalid Schema] ${name} does not possess a valid Mongoose schema.`)
      failed++
      return
    }

    const indexes = schema.indexes()
    const pathCount = Object.keys(schema.paths).length

    console.log(
      `✓ [Model OK] ${name.padEnd(24)} | Paths: ${String(pathCount).padEnd(2)} | Indexes: ${String(indexes.length).padEnd(2)} | Collection: ${ModelClass.collection.name}`
    )
    passed++
  })

  console.log('\n----------------------------------------------------------------------')
  console.log(`Summary: ${passed} models validated successfully. ${failed} failed.`)
  console.log('----------------------------------------------------------------------\n')

  if (failed > 0) {
    process.exit(1)
  }
}

validateModelLayer()
