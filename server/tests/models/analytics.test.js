import { describe, it, expect } from 'vitest'
import mongoose from 'mongoose'
import { AnalyticsBatch } from '../../src/models/analytics/AnalyticsBatch.model.js'
import { AnalyticsEvent } from '../../src/models/analytics/AnalyticsEvent.model.js'
import { AnalyticsDailyRollup } from '../../src/models/analytics/AnalyticsDailyRollup.model.js'

describe('Product Analytics Models', () => {
  const workspaceId = new mongoose.Types.ObjectId()
  const userId = new mongoose.Types.ObjectId()

  describe('AnalyticsBatch Model', () => {
    it('validates a dataset import batch', () => {
      const batch = new AnalyticsBatch({
        workspaceId,
        uploadedBy: userId,
        fileName: 'mixpanel_events_q3.csv',
        fileSize: 450000,
        sourceType: 'csv',
        totalRows: 5000,
        acceptedRows: 4980,
        rejectedRows: 20,
        detectedColumns: ['user_id', 'event_name', 'timestamp', 'duration'],
      })
      const err = batch.validateSync()
      expect(err).toBeUndefined()
    })
  })

  describe('AnalyticsEvent Model', () => {
    it('validates a proper raw event without fabricated actor ID and defaults unmeasured duration to null', () => {
      const evt = new AnalyticsEvent({
        workspaceId,
        eventId: 'evt-2026-10-18-0',
        eventName: 'export_csv',
        eventType: 'export',
        eventTimestamp: new Date(),
        date: '2026-10-18',
        featureName: 'PRD Generator',
      })
      const err = evt.validateSync()
      expect(err).toBeUndefined()
      // actorId should be null when not provided, never defaulted to 'anon-user'
      expect(evt.actorId).toBeNull()
      // durationSeconds should be null when not measured, never defaulted to a measured 0
      expect(evt.durationSeconds).toBeNull()
    })

    it('enforces 90-day TTL index on eventTimestamp', () => {
      const indexes = AnalyticsEvent.schema.indexes()
      const has90DayTTL = indexes.some(
        ([idx, opts]) => idx.eventTimestamp === 1 && opts?.expireAfterSeconds === 90 * 24 * 60 * 60
      )
      expect(has90DayTTL).toBe(true)
    })

    it('enforces YYYY-MM-DD date format constraint', () => {
      const evt = new AnalyticsEvent({
        workspaceId,
        eventName: 'click',
        eventTimestamp: new Date(),
        date: '18/10/2026', // Invalid format
        featureName: 'Feedback Explorer',
      })
      const err = evt.validateSync()
      expect(err).toBeDefined()
      expect(err.errors.date).toBeDefined()
    })

    it('rejects negative durations', () => {
      const evt = new AnalyticsEvent({
        workspaceId,
        eventName: 'click',
        eventTimestamp: new Date(),
        date: '2026-10-18',
        featureName: 'Feedback Explorer',
        durationSeconds: -50,
      })
      const err = evt.validateSync()
      expect(err).toBeDefined()
      expect(err.errors.durationSeconds).toBeDefined()
    })
  })

  describe('AnalyticsDailyRollup Model', () => {
    it('validates a complete daily rollup document', () => {
      const rollup = new AnalyticsDailyRollup({
        workspaceId,
        date: '2026-10-18',
        activeUsers: 48,
        totalSessions: 112,
        totalEvents: 680,
        avgSessionDuration: 210,
        topFeature: 'PRD Generator',
        featureMetrics: [
          {
            name: 'PRD Generator',
            eventCount: 310,
            uniqueUsers: 42,
            adoptionPercent: 88,
            avgDurationSec: 180,
            completionRate: 75,
          },
        ],
        funnelMetrics: [
          { step: '1. Platform Visit', users: 100, conversionRate: 100, dropOffRate: 0 },
          { step: '2. Feature Discovery', users: 85, conversionRate: 85, dropOffRate: 15 },
        ],
      })
      const err = rollup.validateSync()
      expect(err).toBeUndefined()
    })

    it('verifies unique compound index on { workspaceId: 1, date: 1 }', () => {
      const indexes = AnalyticsDailyRollup.schema.indexes()
      const hasUniqueRollupDate = indexes.some(
        ([idx, opts]) => idx.workspaceId === 1 && idx.date === 1 && opts?.unique === true
      )
      expect(hasUniqueRollupDate).toBe(true)
    })
  })
})
