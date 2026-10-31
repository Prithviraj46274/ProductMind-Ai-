/**
 * ProductMind AI — Safe, Repeatable Database Seed Script
 * Connects to MongoDB, upserts demo workspace & user, transforms source demo data into
 * relational MongoDB documents, resolves cross-collection references, and verifies counts.
 */
import mongoose from 'mongoose'
import bcrypt from 'bcryptjs'
import { connectDatabase, disconnectDatabase } from '../mongodb.js'
import * as models from '../../models/index.js'

import {
  initialUser,
  initialFeedback,
  initialFeatures,
  initialPersonas,
  initialPRDs,
  initialRoadmap,
  initialExperiments,
  initialReleases,
  initialCompetitors,
  initialCustomerJourneys,
  initialScenarios,
} from '../../../../src/data/seedData.js'

export async function seedDatabase() {
  console.log('======================================================================')
  console.log('ProductMind AI — Database Seeder & Data Ingestion Layer')
  console.log('======================================================================\n')

  const report = []

  try {
    await connectDatabase()
    console.log('[Seed] Database connected successfully.\n')

    // -------------------------------------------------------------------------
    // 1. Demo User
    // -------------------------------------------------------------------------
    const normalizedEmail = (initialUser.email || 'alex.rivera@productmind.ai').toLowerCase().trim()
    const passwordHash = await bcrypt.hash('demo123', 10)

    const userDoc = await models.User.findOneAndUpdate(
      { email: normalizedEmail },
      {
        $set: {
          name: initialUser.name || 'Alex Rivera',
          email: normalizedEmail,
          passwordHash,
          platformRole: 'user',
          avatar: initialUser.avatar || null,
          theme: initialUser.theme || 'dark',
          reducedMotion: Boolean(initialUser.reducedMotion),
          isActive: true,
          legacyId: initialUser.id || 'usr-1',
          emailVerifiedAt: new Date('2026-01-01'),
        },
      },
      { upsert: true, new: true, setDefaultsOnInsert: true }
    )
    console.log(`✓ User verified: ${userDoc.name} (${userDoc.email}) [ID: ${userDoc._id}]`)

    // -------------------------------------------------------------------------
    // 2. Demo Workspace
    // -------------------------------------------------------------------------
    const workspaceSlug = 'apex-saas-product-operations'
    const workspaceDoc = await models.Workspace.findOneAndUpdate(
      { slug: workspaceSlug },
      {
        $set: {
          name: initialUser.workspaceName || 'Apex SaaS Product Operations',
          slug: workspaceSlug,
          ownerId: userDoc._id,
          plan: 'Enterprise Tier', // Explicit Enterprise plan for demo workspace
          legacyId: 'ws-apex-01',
          isArchived: false,
          settings: {
            defaultTheme: 'dark',
            reducedMotion: false,
            allowGuestViewers: true,
          },
        },
      },
      { upsert: true, new: true, setDefaultsOnInsert: true }
    )
    console.log(`✓ Workspace verified: ${workspaceDoc.name} (${workspaceDoc.slug}) [ID: ${workspaceDoc._id}]`)

    const workspaceId = workspaceDoc._id

    // -------------------------------------------------------------------------
    // 3. Workspace Membership
    // -------------------------------------------------------------------------
    const membershipDoc = await models.WorkspaceMembership.findOneAndUpdate(
      { workspaceId, userId: userDoc._id },
      {
        $set: {
          workspaceId,
          userId: userDoc._id,
          role: initialUser.role || 'Lead Product Architect',
          status: 'active',
          joinedAt: new Date('2026-01-01'),
        },
      },
      { upsert: true, new: true, setDefaultsOnInsert: true }
    )
    console.log(`✓ Membership verified: ${membershipDoc.role} (status: ${membershipDoc.status})\n`)

    // -------------------------------------------------------------------------
    // 4. Features (initialFeatures: 10 items)
    // -------------------------------------------------------------------------
    const featureMap = {} // legacyId -> MongoDB ObjectId
    let featuresUpserted = 0

    for (const feat of initialFeatures) {
      const doc = await models.Feature.findOneAndUpdate(
        { workspaceId, legacyId: feat.id },
        {
          $set: {
            workspaceId,
            legacyId: feat.id,
            name: feat.name,
            description: feat.description,
            customerImpact: feat.customerImpact,
            urgency: feat.urgency,
            demand: feat.demand,
            businessValue: feat.businessValue,
            score: feat.score,
            priorityTier: feat.priorityTier,
            status: feat.status,
            owner: feat.owner || null,
            targetRelease: feat.targetRelease || null,
            aiJustification: feat.aiJustification || '',
            comments: (feat.comments || []).map((c) => ({
              author: c.author,
              text: c.text,
              createdAt: c.createdAt ? new Date(c.createdAt) : new Date(),
            })),
          },
        },
        { upsert: true, new: true, setDefaultsOnInsert: true }
      )
      featureMap[feat.id] = doc._id
      featuresUpserted++
    }
    console.log(`✓ Features processed: ${featuresUpserted} items`)

    // -------------------------------------------------------------------------
    // 5. Feature Groups (Clustered Opportunity Groups)
    // -------------------------------------------------------------------------
    // Create meaningful feature request clusters representing the initial feedback
    const groupDefinitions = [
      {
        legacyId: 'grp-performance-latency',
        title: 'Performance Optimization: Data Grid Latency',
        category: 'Performance',
        primaryTag: 'latency',
        description: 'Customer requests for sub-16ms rendering and virtualization on large 5,000+ row feedback datasets.',
        status: 'approved',
        promotedLegacyFeatureId: 'feat-1',
        painPoints: ['Slow dashboard loading (>5k items)', 'Table stutter during triage filter queries'],
        sentimentDistribution: { Positive: 1, Neutral: 1, Negative: 1 },
      },
      {
        legacyId: 'grp-integrations-jira-linear',
        title: 'Ecosystem Integrations: Bi-directional Jira & Linear Sync',
        category: 'Integrations',
        primaryTag: 'jira',
        description: 'Two-way synchronization for engineering handoff, PRD stories, and real-time status updates.',
        status: 'approved',
        promotedLegacyFeatureId: 'feat-2',
        painPoints: ['Manual transcribing PRD stories into tickets', 'Missing acceptance criteria during implementation'],
        sentimentDistribution: { Positive: 0, Neutral: 2, Negative: 0 },
      },
      {
        legacyId: 'grp-usability-release-gating',
        title: 'Reliability & Governance: Quality Release Readiness Checklist',
        category: 'Reliability',
        primaryTag: 'release-readiness',
        description: 'Enforcing strict Go/No-Go quality gates, compliance checks, and security blockers before release.',
        status: 'approved',
        promotedLegacyFeatureId: 'feat-10',
        painPoints: ['PMs accidentally marking releases ready with failed compliance', 'No blocking gates on urgent bugs'],
        sentimentDistribution: { Positive: 0, Neutral: 0, Negative: 2 },
      },
      {
        legacyId: 'grp-pricing-viewer-seats',
        title: 'Pricing & Licensing: Free Stakeholder Viewer Tier',
        category: 'Pricing',
        primaryTag: 'pricing',
        description: 'Transparent seat tiers for guest viewers across sales, marketing, and executives.',
        status: 'suggested',
        promotedLegacyFeatureId: 'feat-8',
        painPoints: ['Pricing for small startups is steep', 'Lack of clarity on viewer-only seat limits'],
        sentimentDistribution: { Positive: 0, Neutral: 0, Negative: 2 },
      },
    ]

    const groupMap = {} // legacyId -> MongoDB ObjectId
    let groupsUpserted = 0

    for (const grp of groupDefinitions) {
      const promotedFeatureId = grp.promotedLegacyFeatureId ? featureMap[grp.promotedLegacyFeatureId] : null
      const doc = await models.FeatureGroup.findOneAndUpdate(
        { workspaceId, legacyId: grp.legacyId },
        {
          $set: {
            workspaceId,
            legacyId: grp.legacyId,
            title: grp.title,
            category: grp.category,
            primaryTag: grp.primaryTag,
            description: grp.description,
            status: grp.status,
            painPoints: grp.painPoints,
            sentimentDistribution: grp.sentimentDistribution,
            promotedFeatureId,
            feedbackCount: 0, // will be updated when feedback is linked
          },
        },
        { upsert: true, new: true, setDefaultsOnInsert: true }
      )
      groupMap[grp.legacyId] = doc._id
      groupsUpserted++

      // Synchronize back-reference on Feature if promoted
      if (promotedFeatureId) {
        await models.Feature.findByIdAndUpdate(promotedFeatureId, { featureGroupId: doc._id })
      }
    }
    console.log(`✓ Feature Groups processed: ${groupsUpserted} items`)

    // -------------------------------------------------------------------------
    // 6. Customer Feedback (initialFeedback: 20 items)
    // -------------------------------------------------------------------------
    let feedbackUpserted = 0
    const groupCounts = {}

    for (const fb of initialFeedback) {
      const promotedFeatureId = fb.linkedFeatureId ? featureMap[fb.linkedFeatureId] : null

      // Associate with appropriate feature group based on tags / linked feature
      let assignedGroupId = null
      if (fb.linkedFeatureId === 'feat-1') assignedGroupId = groupMap['grp-performance-latency']
      else if (fb.linkedFeatureId === 'feat-2') assignedGroupId = groupMap['grp-integrations-jira-linear']
      else if (fb.linkedFeatureId === 'feat-10') assignedGroupId = groupMap['grp-usability-release-gating']
      else if (fb.linkedFeatureId === 'feat-8') assignedGroupId = groupMap['grp-pricing-viewer-seats']
      else if (fb.category === 'Performance') assignedGroupId = groupMap['grp-performance-latency']
      else if (fb.category === 'Integrations') assignedGroupId = groupMap['grp-integrations-jira-linear']
      else if (fb.category === 'Pricing') assignedGroupId = groupMap['grp-pricing-viewer-seats']
      else if (fb.category === 'Reliability') assignedGroupId = groupMap['grp-usability-release-gating']

      if (assignedGroupId) {
        groupCounts[assignedGroupId.toString()] = (groupCounts[assignedGroupId.toString()] || 0) + 1
      }

      await models.FeedbackItem.findOneAndUpdate(
        { workspaceId, legacyId: fb.id },
        {
          $set: {
            workspaceId,
            legacyId: fb.id,
            externalId: fb.id,
            sourceType: 'manual',
            title: fb.title,
            description: fb.description,
            customerName: fb.customer || null,
            companyName: fb.company || null,
            customerEmail: fb.email || null,
            category: fb.category || null,
            sentiment: fb.sentiment || null,
            sourcePriority: fb.priority || null,
            tags: fb.tags || [],
            sourceTags: fb.tags || [],
            feedbackDate: fb.date ? new Date(fb.date) : new Date(),
            featureGroupId: assignedGroupId || null,
            promotedFeatureId: promotedFeatureId || null,
            processingStatus: 'processed',
          },
        },
        { upsert: true, new: true, setDefaultsOnInsert: true }
      )
      feedbackUpserted++
    }

    // Update cached feedbackCount on feature groups
    for (const [groupId, count] of Object.entries(groupCounts)) {
      await models.FeatureGroup.findByIdAndUpdate(groupId, { feedbackCount: count })
    }
    console.log(`✓ Feedback items processed: ${feedbackUpserted} items`)

    // -------------------------------------------------------------------------
    // 7. Customer Personas (initialPersonas: 4 items)
    // -------------------------------------------------------------------------
    let personasUpserted = 0
    for (const p of initialPersonas) {
      await models.CustomerPersona.findOneAndUpdate(
        { workspaceId, legacyId: p.id },
        {
          $set: {
            workspaceId,
            legacyId: p.id,
            name: p.name,
            role: p.role,
            companyType: p.companyType || null,
            avatar: p.avatar || null,
            description: p.description || '',
            goals: p.goals || [],
            frustrations: p.frustrations || [],
            needs: p.needs || [],
            featurePreferences: p.featurePreferences || [],
            sentimentSummary: p.sentimentSummary || null,
            relatedFeedbackCount: p.relatedFeedbackCount || 0,
            isFavorite: Boolean(p.isFavorite),
          },
        },
        { upsert: true, new: true, setDefaultsOnInsert: true }
      )
      personasUpserted++
    }
    console.log(`✓ Customer Personas processed: ${personasUpserted} items`)

    // -------------------------------------------------------------------------
    // 8. PRDs (initialPRDs: 2 items)
    // -------------------------------------------------------------------------
    let prdsUpserted = 0
    for (const prd of initialPRDs) {
      const linkedFeatureId = prd.featureId ? featureMap[prd.featureId] : null
      await models.PRD.findOneAndUpdate(
        { workspaceId, legacyId: prd.id },
        {
          $set: {
            workspaceId,
            legacyId: prd.id,
            title: prd.title,
            version: prd.version || '1.0.0',
            status: prd.status || 'Draft',
            author: prd.author || null,
            featureId: linkedFeatureId,
            sections: prd.sections || {},
            aiGenerated: false,
          },
        },
        { upsert: true, new: true, setDefaultsOnInsert: true }
      )
      prdsUpserted++
    }
    console.log(`✓ PRDs processed: ${prdsUpserted} items`)

    // -------------------------------------------------------------------------
    // 9. Releases (initialReleases: 2 items)
    // -------------------------------------------------------------------------
    const releaseMap = {}
    let releasesUpserted = 0

    for (const rel of initialReleases) {
      const resolvedFeatureIds = (rel.includedFeatureIds || [])
        .map((fid) => featureMap[fid])
        .filter(Boolean)

      const doc = await models.Release.findOneAndUpdate(
        { workspaceId, version: rel.version },
        {
          $set: {
            workspaceId,
            legacyId: rel.id,
            name: rel.name,
            version: rel.version,
            description: rel.description || '',
            plannedDate: rel.plannedDate,
            owner: rel.owner || null,
            status: rel.status || 'In Progress',
            includedFeatureIds: resolvedFeatureIds,
            checklist: (rel.checklist || []).map((c) => ({
              title: c.title,
              completed: Boolean(c.completed),
              required: Boolean(c.required),
            })),
            releaseNotes: rel.releaseNotes || '',
          },
        },
        { upsert: true, new: true, setDefaultsOnInsert: true }
      )
      releaseMap[rel.id] = doc._id
      releasesUpserted++
    }
    console.log(`✓ Releases processed: ${releasesUpserted} items`)

    // -------------------------------------------------------------------------
    // 10. Roadmap Items (initialRoadmap: 8 items)
    // -------------------------------------------------------------------------
    const roadmapMap = {}
    let roadmapUpserted = 0

    for (const rd of initialRoadmap) {
      const linkedFeatureId = rd.featureId ? featureMap[rd.featureId] : null

      // Resolve release target:
      // rd-1, rd-2, rd-4, rd-6 belong to v2.4.0 (rel-1)
      // rd-5, rd-8 belong to v2.5.0 (rel-2)
      let targetReleaseId = null
      if (['rd-1', 'rd-2', 'rd-4', 'rd-6'].includes(rd.id)) {
        targetReleaseId = releaseMap['rel-1'] || null
      } else if (['rd-5', 'rd-8'].includes(rd.id)) {
        targetReleaseId = releaseMap['rel-2'] || null
      }

      const doc = await models.RoadmapItem.findOneAndUpdate(
        { workspaceId, legacyId: rd.id },
        {
          $set: {
            workspaceId,
            legacyId: rd.id,
            title: rd.title,
            description: rd.description || '',
            featureId: linkedFeatureId,
            releaseId: targetReleaseId,
            status: rd.status || 'Planned',
            priority: rd.priority || 'Medium',
            owner: rd.owner || null,
            startDate: rd.startDate,
            targetDate: rd.targetDate,
            milestone: rd.milestone || null,
            progress: typeof rd.progress === 'number' ? rd.progress : 0,
            notes: rd.notes || '',
          },
        },
        { upsert: true, new: true, setDefaultsOnInsert: true }
      )
      roadmapMap[rd.id] = doc._id
      roadmapUpserted++
    }

    // Resolve roadmap dependencies and link release roadmapItemIds
    for (const rd of initialRoadmap) {
      const resolvedDeps = (rd.dependencies || []).map((depId) => roadmapMap[depId]).filter(Boolean)
      if (resolvedDeps.length > 0) {
        await models.RoadmapItem.findOneAndUpdate(
          { workspaceId, legacyId: rd.id },
          { dependencies: resolvedDeps }
        )
      }
    }

    // Sync Release.roadmapItemIds
    if (releaseMap['rel-1']) {
      const r1Ids = ['rd-1', 'rd-2', 'rd-4', 'rd-6'].map((id) => roadmapMap[id]).filter(Boolean)
      await models.Release.findByIdAndUpdate(releaseMap['rel-1'], { roadmapItemIds: r1Ids })
    }
    if (releaseMap['rel-2']) {
      const r2Ids = ['rd-5', 'rd-8'].map((id) => roadmapMap[id]).filter(Boolean)
      await models.Release.findByIdAndUpdate(releaseMap['rel-2'], { roadmapItemIds: r2Ids })
    }
    console.log(`✓ Roadmap Items processed: ${roadmapUpserted} items`)

    // -------------------------------------------------------------------------
    // 11. Product Experiments (initialExperiments: 3 items)
    // -------------------------------------------------------------------------
    let experimentsUpserted = 0
    for (const exp of initialExperiments) {
      const linkedFeatureId = exp.linkedFeatureId ? featureMap[exp.linkedFeatureId] : null
      await models.ProductExperiment.findOneAndUpdate(
        { workspaceId, legacyId: exp.id },
        {
          $set: {
            workspaceId,
            legacyId: exp.id,
            name: exp.name,
            problem: exp.problem || '',
            hypothesis: exp.hypothesis,
            targetAudience: exp.targetAudience || 'All active users',
            proposedChange: exp.proposedChange || '',
            successMetric: exp.successMetric,
            baseline: exp.baseline || 0,
            target: exp.target || 0,
            observedValue: exp.observedValue !== undefined ? exp.observedValue : null,
            startDate: exp.startDate,
            endDate: exp.endDate,
            linkedFeatureId,
            owner: exp.owner || null,
            status: exp.status || 'Running',
            conclusion: exp.conclusion || 'Continue',
            notes: exp.notes || '',
          },
        },
        { upsert: true, new: true, setDefaultsOnInsert: true }
      )
      experimentsUpserted++
    }
    console.log(`✓ Product Experiments processed: ${experimentsUpserted} items`)

    // -------------------------------------------------------------------------
    // 12. Competitor Intel (initialCompetitors: 3 items)
    // -------------------------------------------------------------------------
    let competitorsUpserted = 0
    for (const comp of initialCompetitors) {
      await models.CompetitorIntel.findOneAndUpdate(
        { workspaceId, legacyId: comp.id },
        {
          $set: {
            workspaceId,
            legacyId: comp.id,
            name: comp.name,
            productDescription: comp.productDescription || '',
            website: comp.website || '',
            targetAudience: comp.targetAudience || null,
            keyFeatures: comp.keyFeatures || [],
            strengths: comp.strengths || [],
            weaknesses: comp.weaknesses || [],
            differentiators: comp.differentiators || [],
            researchNotes: comp.researchNotes || '',
            lastReviewed: comp.lastReviewed ? new Date(comp.lastReviewed) : new Date(),
          },
        },
        { upsert: true, new: true, setDefaultsOnInsert: true }
      )
      competitorsUpserted++
    }
    console.log(`✓ Competitor Intel processed: ${competitorsUpserted} items`)

    // -------------------------------------------------------------------------
    // 13. Customer Journeys (initialCustomerJourneys: 5 stages)
    // -------------------------------------------------------------------------
    let journeysUpserted = 0
    for (const stage of initialCustomerJourneys) {
      await models.CustomerJourney.findOneAndUpdate(
        { workspaceId, order: stage.order },
        {
          $set: {
            workspaceId,
            legacyId: stage.id,
            name: stage.name,
            order: stage.order,
            description: stage.description || '',
            touchpoints: (stage.touchpoints || []).map((tp) => ({
              name: tp.name,
              sentiment: tp.sentiment || 'Positive',
              painPoints: tp.painPoints || '',
              opportunity: tp.opportunity || '',
            })),
          },
        },
        { upsert: true, new: true, setDefaultsOnInsert: true }
      )
      journeysUpserted++
    }
    console.log(`✓ Customer Journeys processed: ${journeysUpserted} stages`)

    // -------------------------------------------------------------------------
    // 14. Prioritization Scenarios (initialScenarios: 1 item)
    // -------------------------------------------------------------------------
    let scenariosUpserted = 0
    for (const scen of initialScenarios) {
      const adjustedFeatures = (scen.adjustedFeatures || []).map((item) => ({
        featureId: featureMap[item.featureId] || new mongoose.Types.ObjectId(),
        customerImpact: item.customerImpact,
        urgency: item.urgency,
        demand: item.demand,
        businessValue: item.businessValue,
      }))

      await models.PrioritizationScenario.findOneAndUpdate(
        { workspaceId, legacyId: scen.id },
        {
          $set: {
            workspaceId,
            legacyId: scen.id,
            name: scen.name,
            description: scen.description || '',
            createdBy: userDoc._id,
            adjustedFeatures,
          },
        },
        { upsert: true, new: true, setDefaultsOnInsert: true }
      )
      scenariosUpserted++
    }
    console.log(`✓ Prioritization Scenarios processed: ${scenariosUpserted} items`)

    // -------------------------------------------------------------------------
    // 15. Copilot Conversation & Messages
    // -------------------------------------------------------------------------
    const chatDoc = await models.CopilotConversation.findOneAndUpdate(
      { workspaceId, legacyId: 'chat-1' },
      {
        $set: {
          workspaceId,
          userId: userDoc._id,
          legacyId: 'chat-1',
          title: 'Initial Product Strategy Discussion',
          isArchived: false,
          lastMessageAt: new Date(),
        },
      },
      { upsert: true, new: true, setDefaultsOnInsert: true }
    )

    await models.CopilotMessage.findOneAndUpdate(
      { conversationId: chatDoc._id, legacyId: 'msg-seed-1' },
      {
        $set: {
          workspaceId,
          conversationId: chatDoc._id,
          legacyId: 'msg-seed-1',
          role: 'assistant',
          content:
            'Hello! I am your **Product Mind AI Copilot**. I analyze your customer feedback, calculate algorithmic priority scores, and synthesize roadmap recommendations in real time. How can I help you today?',
          modelInfo: {
            provider: 'google',
            modelName: 'gemini-1.5-pro',
            tokensUsed: 42,
          },
        },
      },
      { upsert: true, new: true, setDefaultsOnInsert: true }
    )
    console.log(`✓ Copilot Session initialized: conversation ID [${chatDoc._id}]`)

    // -------------------------------------------------------------------------
    // 16. Analytics Daily Rollups (14 days of realistic trends)
    // -------------------------------------------------------------------------
    const dates = [
      '2026-10-05', '2026-10-06', '2026-10-07', '2026-10-08', '2026-10-09',
      '2026-10-10', '2026-10-11', '2026-10-12', '2026-10-13', '2026-10-14',
      '2026-10-15', '2026-10-16', '2026-10-17', '2026-10-18',
    ]

    let rollupsUpserted = 0
    for (let i = 0; i < dates.length; i++) {
      const d = dates[i]
      const baseActive = 38 + i
      const baseEvents = 520 + i * 22
      const baseSessions = 85 + i * 4

      await models.AnalyticsDailyRollup.findOneAndUpdate(
        { workspaceId, date: d },
        {
          $set: {
            workspaceId,
            date: d,
            activeUsers: baseActive,
            totalSessions: baseSessions,
            totalEvents: baseEvents,
            avgSessionDuration: 195 + (i % 5) * 10,
            topFeature: 'PRD Generator',
            featureMetrics: [
              {
                name: 'PRD Generator',
                eventCount: Math.round(baseEvents * 0.42),
                uniqueUsers: Math.round(baseActive * 0.85),
                adoptionPercent: 85,
                avgDurationSec: 210,
                completionRate: 88,
              },
              {
                name: 'Feedback Explorer',
                eventCount: Math.round(baseEvents * 0.32),
                uniqueUsers: Math.round(baseActive * 0.78),
                adoptionPercent: 78,
                avgDurationSec: 140,
                completionRate: 92,
              },
              {
                name: 'What-If Simulator',
                eventCount: Math.round(baseEvents * 0.26),
                uniqueUsers: Math.round(baseActive * 0.65),
                adoptionPercent: 65,
                avgDurationSec: 165,
                completionRate: 74,
              },
            ],
            funnelMetrics: [
              { step: '1. Visit Workspace', users: baseActive, conversionRate: 100, dropOffRate: 0 },
              { step: '2. Review Feedback', users: Math.round(baseActive * 0.9), conversionRate: 90, dropOffRate: 10 },
              { step: '3. Triage & Prioritize', users: Math.round(baseActive * 0.75), conversionRate: 75, dropOffRate: 15 },
              { step: '4. Draft PRD Specs', users: Math.round(baseActive * 0.58), conversionRate: 58, dropOffRate: 17 },
              { step: '5. Release Quality Gate', users: Math.round(baseActive * 0.42), conversionRate: 42, dropOffRate: 16 },
            ],
          },
        },
        { upsert: true, new: true, setDefaultsOnInsert: true }
      )
      rollupsUpserted++
    }
    console.log(`✓ Analytics Daily Rollups processed: ${rollupsUpserted} days`)

    // -------------------------------------------------------------------------
    // 17. Sample Raw Analytics Events (20 items in retention window)
    // -------------------------------------------------------------------------
    let rawEventsUpserted = 0
    for (let i = 0; i < 20; i++) {
      const evtId = `evt-seed-20261018-${i + 1}`
      await models.AnalyticsEvent.findOneAndUpdate(
        { workspaceId, eventId: evtId },
        {
          $set: {
            workspaceId,
            eventId: evtId,
            eventName: i % 2 === 0 ? 'view_page' : 'click_action',
            eventType: 'telemetry',
            eventTimestamp: new Date(Date.now() - i * 3600000), // recent hours
            date: '2026-10-18',
            actorId: `usr-actor-${(i % 5) + 1}`,
            sessionId: `sess-${Math.floor(i / 3) + 1}`,
            featureName: i % 3 === 0 ? 'PRD Generator' : (i % 3 === 1 ? 'Feedback Explorer' : 'What-If Simulator'),
            durationSeconds: (i + 1) * 15,
          },
        },
        { upsert: true, new: true, setDefaultsOnInsert: true }
      )
      rawEventsUpserted++
    }
    console.log(`✓ Analytics Raw Events processed: ${rawEventsUpserted} items`)

    // -------------------------------------------------------------------------
    // 18. Audit Log Entry
    // -------------------------------------------------------------------------
    await models.AuditLog.create({
      workspaceId,
      actor: userDoc.name,
      userId: userDoc._id,
      entityType: 'workspace',
      entityId: workspaceDoc._id.toString(),
      action: 'created',
      description: 'Initialized ProductMind AI demonstration workspace and seeded baseline product intelligence.',
      canUndo: false, // Baseline initialization event cannot be rolled back
    })
    console.log('✓ Seed Audit Log record created.\n')

    // -------------------------------------------------------------------------
    // Verification & Exact Document Counts
    // -------------------------------------------------------------------------
    console.log('======================================================================')
    console.log('Database Verification — MongoDB Document Counts')
    console.log('======================================================================')

    const collectionsToVerify = [
      { name: 'users', model: models.User, expected: 1 },
      { name: 'workspaces', model: models.Workspace, expected: 1 },
      { name: 'workspace_memberships', model: models.WorkspaceMembership, expected: 1 },
      { name: 'feedback_items', model: models.FeedbackItem, expected: 20 },
      { name: 'feature_groups', model: models.FeatureGroup, expected: 4 },
      { name: 'features', model: models.Feature, expected: 10 },
      { name: 'customer_personas', model: models.CustomerPersona, expected: 4 },
      { name: 'prds', model: models.PRD, expected: 2 },
      { name: 'releases', model: models.Release, expected: 2 },
      { name: 'roadmap_items', model: models.RoadmapItem, expected: 8 },
      { name: 'product_experiments', model: models.ProductExperiment, expected: 3 },
      { name: 'competitor_intel', model: models.CompetitorIntel, expected: 3 },
      { name: 'customer_journeys', model: models.CustomerJourney, expected: 5 },
      { name: 'prioritization_scenarios', model: models.PrioritizationScenario, expected: 1 },
      { name: 'copilot_conversations', model: models.CopilotConversation, expected: 1 },
      { name: 'copilot_messages', model: models.CopilotMessage, expected: 1 },
      { name: 'analytics_daily_rollups', model: models.AnalyticsDailyRollup, expected: 14 },
      { name: 'analytics_events', model: models.AnalyticsEvent, expected: 20 },
    ]

    let allPassed = true
    for (const item of collectionsToVerify) {
      const actualCount = await item.model.countDocuments({
        ...(item.model.schema.paths.workspaceId ? { workspaceId } : {}),
      })
      const isPass = actualCount >= item.expected
      if (!isPass) allPassed = false

      report.push({
        collection: item.name,
        expected: item.expected,
        actual: actualCount,
        status: isPass ? 'PASS' : 'FAIL',
      })

      console.log(
        `${item.name.padEnd(26)} | Expected: ${String(item.expected).padEnd(2)} | Actual in DB: ${String(actualCount).padEnd(2)} | [${isPass ? 'PASS' : 'FAIL'}]`
      )
    }

    console.log('\n======================================================================')
    console.log(allPassed ? '✓ ALL COLLECTIONS SEEDED AND VERIFIED SUCCESSFULLY' : '❌ SOME COUNTS FAILED VERIFICATION')
    console.log('======================================================================\n')

    return { success: allPassed, report }
  } catch (err) {
    console.error(`[Seed Error] Fatal error during database seeding: ${err.message}`, err)
    throw err
  } finally {
    await disconnectDatabase()
  }
}

// Direct CLI invocation
if (process.argv[1] && process.argv[1].replace(/\\/g, '/').includes('seedDatabase')) {
  seedDatabase()
    .then(() => process.exit(0))
    .catch((err) => {
      console.error(err)
      process.exit(1)
    })
}

export default seedDatabase
