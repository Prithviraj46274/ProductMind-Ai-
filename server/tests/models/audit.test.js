import { describe, it, expect } from 'vitest'
import mongoose from 'mongoose'
import { AuditLog } from '../../src/models/audit/AuditLog.model.js'
import { SavedReport } from '../../src/models/reporting/SavedReport.model.js'
import { AuditEntityType, AuditAction } from '../../src/constants/enums.js'

describe('Reporting & Audit Models', () => {
  const workspaceId = new mongoose.Types.ObjectId()
  const userId = new mongoose.Types.ObjectId()

  describe('AuditLog Model', () => {
    it('validates an audit event with previousState and newState for 1-click undo', () => {
      const log = new AuditLog({
        workspaceId,
        actor: 'Admin User',
        userId,
        entityType: AuditEntityType.FEATURE,
        entityId: 'feat-101',
        action: AuditAction.UPDATED,
        description: 'Updated feature: "High-Performance Virtual Grid"',
        previousState: { status: 'In Planning', score: 7.2 },
        newState: { status: 'In Development', score: 8.65 },
        canUndo: true,
      })
      const err = log.validateSync()
      expect(err).toBeUndefined()
      expect(log.canUndo).toBe(true)
    })

    it('sets canUndo to false for non-reversible actions or missing previousState on update', async () => {
      const log = new AuditLog({
        workspaceId,
        userId,
        entityType: AuditEntityType.ANALYTICS,
        entityId: 'import-99',
        action: AuditAction.APPROVED,
        description: 'Approved analytics report',
        canUndo: true, // Should be overridden to false by pre-validate hook
      })
      await log.validate()
      expect(log.actor).toBe('System')
      expect(log.canUndo).toBe(false)
    })

    it('requires workspaceId, entityType, entityId, and action', () => {
      const log = new AuditLog({})
      const err = log.validateSync()
      expect(err).toBeDefined()
      expect(err.errors.workspaceId).toBeDefined()
      expect(err.errors.entityType).toBeDefined()
      expect(err.errors.entityId).toBeDefined()
      expect(err.errors.action).toBeDefined()
    })

    it('verifies TTL index on expiresAt for audit retention', () => {
      const expiresPath = AuditLog.schema.path('expiresAt')
      expect(expiresPath.options.index).toEqual({ expires: 0 })
    })
  })

  describe('SavedReport Model', () => {
    it('validates custom saved report configuration', () => {
      const report = new SavedReport({
        workspaceId,
        createdBy: userId,
        title: 'Executive Stakeholder KPI Deck',
        reportType: 'executive_kpi',
        filters: { timeRange: '30d' },
        layoutConfig: ['kpis', 'trends', 'sentiment', 'priorities'],
        isFavorite: true,
      })
      const err = report.validateSync()
      expect(err).toBeUndefined()
    })
  })
})
