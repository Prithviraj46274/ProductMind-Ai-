import { describe, it, expect } from 'vitest'
import mongoose from 'mongoose'
import { Feature } from '../../src/models/planning/Feature.model.js'
import { PrioritizationScenario } from '../../src/models/planning/PrioritizationScenario.model.js'
import { PRD } from '../../src/models/planning/PRD.model.js'
import { RoadmapItem } from '../../src/models/planning/RoadmapItem.model.js'
import { Release } from '../../src/models/planning/Release.model.js'
import { ProductExperiment } from '../../src/models/planning/ProductExperiment.model.js'
import { CustomerJourney } from '../../src/models/planning/CustomerJourney.model.js'
import { calculatePriorityScore, getPriorityTier } from '../../src/constants/enums.js'

describe('Planning, Prioritization & Roadmap Models', () => {
  const workspaceId = new mongoose.Types.ObjectId()
  const featureId = new mongoose.Types.ObjectId()

  describe('Feature Model & Prioritization Mathematical Formula', () => {
    it('calculates the exact priority score: (0.35 * Impact) + (0.30 * Urgency) + (0.20 * Demand) + (0.15 * Value)', () => {
      // Input from seedData feat-1: Impact=9, Urgency=9, Demand=8, Value=8
      // (0.35 * 9) + (0.30 * 9) + (0.20 * 8) + (0.15 * 8) = 3.15 + 2.70 + 1.60 + 1.20 = 8.65
      const calculated = calculatePriorityScore({
        customerImpact: 9,
        urgency: 9,
        demand: 8,
        businessValue: 8,
      })
      expect(calculated).toBe(8.65)
      expect(getPriorityTier(calculated)).toBe('Critical')
    })

    it('calculates the score dynamically in pre-validate hook', async () => {
      const feature = new Feature({
        workspaceId,
        name: 'Dynamic scoring feature',
        description: 'Testing dynamic prioritization calculation',
        customerImpact: 9,
        urgency: 9,
        demand: 8,
        businessValue: 8,
      })
      await feature.validate()
      expect(feature.score).toBe(8.65)
      expect(feature.priorityTier).toBe('Critical')
    })

    it('enforces 1-10 numeric range bounds for prioritization factors', () => {
      const feature = new Feature({
        workspaceId,
        name: 'Out of bounds test',
        description: 'Testing factor bounds',
        customerImpact: 15, // Invalid > 10
        urgency: 0,         // Invalid < 1
      })
      const err = feature.validateSync()
      expect(err).toBeDefined()
      expect(err.errors.customerImpact).toBeDefined()
      expect(err.errors.urgency).toBeDefined()
    })

    it('defaults owner and targetRelease to null instead of fabricated names', () => {
      const feature = new Feature({
        workspaceId,
        name: 'Unassigned Feature',
      })
      expect(feature.owner).toBeNull()
      expect(feature.targetRelease).toBeNull()
      expect(feature.customerImpact).toBe(5)
      expect(feature.urgency).toBe(5)
      expect(feature.demand).toBe(5)
      expect(feature.businessValue).toBe(5)
      // Deterministic default score: 5.0
      expect(feature.score).toBe(5.0)
      expect(feature.priorityTier).toBe('Medium')
    })
  })

  describe('PRD Model', () => {
    it('defaults author to null and allows optional authorId reference', () => {
      const prd = new PRD({
        workspaceId,
        featureId,
        title: 'Draft PRD',
      })
      expect(prd.author).toBeNull()
      expect(prd.authorId).toBeNull()
    })

    it('validates a complete 13-section PRD specification', () => {
      const prd = new PRD({
        workspaceId,
        featureId,
        title: 'High-Performance Virtualized Data Grid Architecture',
        version: '1.2.0',
        status: 'Completed',
        sections: {
          overview: 'Architecture specification for virtualized table',
          problemStatement: 'DOM stutter on 5k+ items',
          targetUsers: 'Product Managers & Support Leads',
          customerPainPoints: 'Render lag during triage',
          proposedSolution: 'Windowing row virtualization',
          goalsAndSuccessMetrics: 'Sub-16ms render times',
          functionalRequirements: 'Virtual row rendering buffer',
          nonFunctionalRequirements: 'Under 15KB bundle footprint',
          userStories: 'As a PM, I want smooth scrolling...',
          acceptanceCriteria: '60fps confirmed in DevTools',
          dependenciesAndConstraints: 'Browser ResizeObserver support',
          risksAndMitigations: 'Row jumping prevented via cache',
          releasePlan: 'Ship in v2.4.0',
        },
      })
      const err = prd.validateSync()
      expect(err).toBeUndefined()
      expect(prd.sections.overview).toBeDefined()
      expect(prd.sections.releasePlan).toBeDefined()
    })
  })

  describe('RoadmapItem Model', () => {
    it('defaults owner and milestone to null', () => {
      const item = new RoadmapItem({
        workspaceId,
        title: 'Quarterly Initiative',
        startDate: '2026-10-01',
        targetDate: '2026-12-31',
      })
      expect(item.owner).toBeNull()
      expect(item.ownerId).toBeNull()
      expect(item.milestone).toBeNull()
    })

    it('validates roadmap item and progress bounds (0-100)', () => {
      const item = new RoadmapItem({
        workspaceId,
        featureId,
        title: 'High-Performance Virtual Grid',
        startDate: '2026-10-01',
        targetDate: '2026-11-15',
        milestone: 'Q4 Core Platform',
        progress: 75,
      })
      const err = item.validateSync()
      expect(err).toBeUndefined()
    })

    it('rejects progress outside 0-100', () => {
      const item = new RoadmapItem({
        workspaceId,
        title: 'Invalid Progress',
        startDate: '2026-10-01',
        targetDate: '2026-11-15',
        progress: 150,
      })
      const err = item.validateSync()
      expect(err).toBeDefined()
      expect(err.errors.progress).toBeDefined()
    })
  })

  describe('Release Model & Gated Quality Verification', () => {
    it('treats an empty checklist as unverified (readiness 0% and isGated true)', () => {
      const rel = new Release({
        workspaceId,
        name: 'Empty Checklist Release',
        version: 'v3.0.0',
        plannedDate: '2026-12-01',
        checklist: [],
      })
      expect(rel.readinessPercent).toBe(0)
      expect(rel.isGated).toBe(true)
      expect(rel.owner).toBeNull()
      expect(rel.ownerId).toBeNull()
    })

    it('computes readinessPercent and isGated virtual properties correctly', () => {
      const rel = new Release({
        workspaceId,
        name: 'Spring Intelligence Release',
        version: 'v2.4.0',
        plannedDate: '2026-11-15',
        checklist: [
          { title: 'Requirements signed off', completed: true, required: true },
          { title: 'E2E tests passing', completed: true, required: true },
          { title: 'Zero P0 blockers', completed: false, required: true }, // Uncompleted REQUIRED check
          { title: 'Release notes written', completed: false, required: false }, // Uncompleted OPTIONAL check
        ],
      })

      // 2 out of 4 completed = 50%
      expect(rel.readinessPercent).toBe(50)
      // Because 'Zero P0 blockers' is required and not completed, isGated must be true!
      expect(rel.isGated).toBe(true)

      // Mark the required check as completed
      rel.checklist[2].completed = true
      expect(rel.readinessPercent).toBe(75)
      // Now all required checks are done, isGated must be false!
      expect(rel.isGated).toBe(false)
    })
  })

  describe('ProductExperiment Model', () => {
    it('validates experiment with hypothesis and baseline/target metrics', () => {
      const exp = new ProductExperiment({
        workspaceId,
        name: '1-Click Guided Product Tour Adoption',
        hypothesis: 'Interactive tour will increase Day-1 activation by 35%',
        successMetric: 'Activation Rate (%)',
        baseline: 28,
        target: 50,
        observedValue: 54.2,
        startDate: '2026-09-15',
        endDate: '2026-10-15',
        conclusion: 'Roll Out',
      })
      const err = exp.validateSync()
      expect(err).toBeUndefined()
    })
  })

  describe('CustomerJourney Model', () => {
    it('validates journey stage with touchpoints', () => {
      const journey = new CustomerJourney({
        workspaceId,
        name: 'Discovery',
        order: 1,
        touchpoints: [
          { name: 'Marketing Landing Page', sentiment: 'Positive', painPoints: 'Pricing unclear' },
        ],
      })
      const err = journey.validateSync()
      expect(err).toBeUndefined()
    })
  })
})
