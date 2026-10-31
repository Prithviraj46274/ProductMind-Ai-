import { describe, it, expect } from 'vitest'
import mongoose from 'mongoose'
import { FeatureGroup } from '../../src/models/intelligence/FeatureGroup.model.js'
import { CustomerPersona } from '../../src/models/intelligence/CustomerPersona.model.js'
import { CompetitorIntel } from '../../src/models/intelligence/CompetitorIntel.model.js'

describe('Intelligence & Aggregation Models', () => {
  const workspaceId = new mongoose.Types.ObjectId()

  describe('FeatureGroup Model', () => {
    it('validates a feature cluster document', () => {
      const group = new FeatureGroup({
        workspaceId,
        title: 'Performance Optimization: Virtual Grid',
        category: 'Performance',
        primaryTag: 'virtual-grid',
        description: 'Cluster of customer tickets requesting 60fps scrolling and latency fixes.',
        feedbackCount: 5,
        sentimentDistribution: { Positive: 0, Neutral: 1, Negative: 4 },
        painPoints: ['Slow dashboard loading', 'Table freeze on 5k items'],
      })
      const err = group.validateSync()
      expect(err).toBeUndefined()
      expect(group.status).toBe('suggested')
    })

    it('rejects painPoints list with more than 10 excerpts', () => {
      const group = new FeatureGroup({
        workspaceId,
        title: 'Too Many Pain Points',
        painPoints: Array.from({ length: 15 }, (_, i) => `Issue ${i + 1}`),
      })
      const err = group.validateSync()
      expect(err).toBeDefined()
      expect(err.errors.painPoints).toBeDefined()
    })
  })

  describe('CustomerPersona Model', () => {
    it('validates an archetype persona', () => {
      const persona = new CustomerPersona({
        workspaceId,
        name: 'Elena Vance',
        role: 'Enterprise IT & Security Director',
        companyType: 'Fortune 500 Enterprise',
        avatar: 'EV',
        goals: ['Maintain 99.99% uptime', 'Automate compliance audit trails'],
        frustrations: ['Vague release readiness checklists without verification gates'],
        needs: ['Strict quality gates on release readiness'],
        featurePreferences: ['Release Readiness Quality Gates'],
        isFavorite: true,
      })
      const err = persona.validateSync()
      expect(err).toBeUndefined()
    })

    it('defaults companyType, avatar, and sentimentSummary to null when not provided', () => {
      const persona = new CustomerPersona({
        workspaceId,
        name: 'Alex Developer',
        role: 'Frontend Architect',
      })
      const err = persona.validateSync()
      expect(err).toBeUndefined()
      expect(persona.companyType).toBeNull()
      expect(persona.avatar).toBeNull()
      expect(persona.sentimentSummary).toBeNull()
    })
  })

  describe('CompetitorIntel Model', () => {
    it('validates competitor benchmark intelligence', () => {
      const comp = new CompetitorIntel({
        workspaceId,
        name: 'ProductBoard Pro',
        productDescription: 'Standard product management suite',
        website: 'https://productboard.example.com',
        strengths: ['Brand awareness'],
        weaknesses: ['Opaque prioritization formulas'],
        differentiators: ['Transparent formulaic scoring with exact weight breakdowns'],
      })
      const err = comp.validateSync()
      expect(err).toBeUndefined()
    })
  })
})
