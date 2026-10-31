import { describe, it, expect } from 'vitest'
import mongoose from 'mongoose'
import { FeedbackBatch } from '../../src/models/feedback/FeedbackBatch.model.js'
import { FeedbackItem } from '../../src/models/feedback/FeedbackItem.model.js'
import { FeedbackCategory, FeedbackSentiment, FeedbackPriority, FeedbackSourceType } from '../../src/constants/enums.js'

describe('Feedback Ingestion Models', () => {
  const workspaceId = new mongoose.Types.ObjectId()
  const userId = new mongoose.Types.ObjectId()

  describe('FeedbackBatch Model', () => {
    it('validates a valid import batch', () => {
      const batch = new FeedbackBatch({
        workspaceId,
        uploadedBy: userId,
        fileName: 'customer_reviews_october.csv',
        totalRows: 100,
        acceptedRows: 95,
        rejectedRows: 5,
        duplicateRows: 0,
      })
      const err = batch.validateSync()
      expect(err).toBeUndefined()
    })

    it('caps errorSummary at 50 to prevent unbounded document size', () => {
      const excessErrors = Array.from({ length: 55 }, (_, i) => ({
        rowNumber: i + 1,
        message: `Validation failed on row ${i + 1}`,
      }))
      const batch = new FeedbackBatch({
        workspaceId,
        uploadedBy: userId,
        errorSummary: excessErrors,
      })
      const err = batch.validateSync()
      expect(err).toBeDefined()
      expect(err.errors.errorSummary).toBeDefined()
    })
  })

  describe('FeedbackItem Model', () => {
    it('validates a complete feedback item with provenance and null defaults for unknown values', () => {
      const item = new FeedbackItem({
        workspaceId,
        externalId: 'gh-issue-101',
        sourceType: FeedbackSourceType.GITHUB,
        title: 'Slow dashboard loading with large feedback datasets (>5k items)',
        description: 'When switching to the Feedback Explorer with filter queries, the table stutters and takes upwards of 4 seconds to render.',
        category: FeedbackCategory.PERFORMANCE,
        sentiment: FeedbackSentiment.NEGATIVE,
        sourceTags: ['performance', 'latency'],
        aiThemes: ['#ui-ux', '#scalability'],
      })
      const err = item.validateSync()
      expect(err).toBeUndefined()
      // Should NOT invent fake customer or company names
      expect(item.customerName).toBeNull()
      expect(item.companyName).toBeNull()
      // AI confidence should be null until an actual AI job runs
      expect(item.classificationConfidence).toBeNull()
      expect(item.sourcePriority).toBeNull()
    })

    it('defaults category and sentiment to null when not provided from source', () => {
      const rawItem = new FeedbackItem({
        workspaceId,
        title: 'Raw Unclassified Feedback',
        description: 'Customer sent a plain text email without predefined categories or sentiment.',
      })
      const err = rawItem.validateSync()
      expect(err).toBeUndefined()
      expect(rawItem.category).toBeNull()
      expect(rawItem.sentiment).toBeNull()
      expect(rawItem.sourcePriority).toBeNull()
      expect(rawItem.aiPredictedPriority).toBeNull()
    })

    it('requires title, description, and workspaceId', () => {
      const item = new FeedbackItem({})
      const err = item.validateSync()
      expect(err).toBeDefined()
      expect(err.errors.workspaceId).toBeDefined()
      expect(err.errors.title).toBeDefined()
      expect(err.errors.description).toBeDefined()
    })

    it('verifies source-scoped partial unique index on { workspaceId: 1, sourceType: 1, externalId: 1 }', () => {
      const indexes = FeedbackItem.schema.indexes()
      const hasSourceScopedDeduplication = indexes.some(
        ([idx, opts]) =>
          idx.workspaceId === 1 &&
          idx.sourceType === 1 &&
          idx.externalId === 1 &&
          opts?.unique === true &&
          opts?.partialFilterExpression?.externalId
      )
      expect(hasSourceScopedDeduplication).toBe(true)
    })
  })
})
