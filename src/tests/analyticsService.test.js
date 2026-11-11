import { describe, it, expect, vi } from 'vitest'
import { analyticsService, DEMO_ANALYTICS_DATASET } from '../services/api/analyticsService'

describe('Product Analytics Ingestion and KPI Service', () => {
  const sampleCSV = `user_id,event_name,feature_name,timestamp,session_id
u1,feature_view,Search Bar,2026-10-15T10:00:00Z,s1
u1,feature_click,Search Bar,2026-10-15T10:05:00Z,s1
u2,feature_view,Export CSV,2026-10-16T11:00:00Z,s2
u3,login,Dashboard,2026-10-18T09:00:00Z,s3
u2,feature_click,Export CSV,2026-10-19T14:00:00Z,s4
`

  const sampleJSON = JSON.stringify([
    { userId: 'u1', eventType: 'view', featureName: 'AI Copilot', timestamp: '2026-10-15T10:00:00Z', sessionId: 's1' },
    { userId: 'u2', eventType: 'click', featureName: 'AI Copilot', timestamp: '2026-10-16T10:00:00Z', sessionId: 's2' },
    { userId: 'u3', eventType: 'view', featureName: 'PRD Export', timestamp: '2026-10-17T10:00:00Z', sessionId: 's3' },
  ])

  it('correctly parses and auto-maps CSV data', () => {
    const result = analyticsService.parseAnalyticsFile(sampleCSV, 'events.csv')
    expect(result.success).toBe(true)
    expect(result.records.length).toBe(5)
    expect(result.detectedColumns).toContain('user_id')
    expect(result.detectedColumns).toContain('event_name')
    expect(result.detectedColumns).toContain('feature_name')
    expect(result.mappedColumns.userId).toBe('user_id')
    expect(result.mappedColumns.featureName).toBe('feature_name')
    expect(result.missingRequired).toHaveLength(0)
  })

  it('flags missing required fields when columns are insufficient', () => {
    const invalidCSV = `col_a,col_b\nval1,val2\nval3,val4`
    const result = analyticsService.parseAnalyticsFile(invalidCSV, 'invalid.csv')
    expect(result.success).toBe(false)
    expect(result.missingRequired).toContain('userId or featureName')
  })

  it('correctly parses JSON array records', () => {
    const result = analyticsService.parseAnalyticsFile(sampleJSON, 'data.json')
    expect(result.success).toBe(true)
    expect(result.records.length).toBe(3)
    expect(result.detectedColumns).toContain('userId')
    expect(result.detectedColumns).toContain('featureName')
  })

  it('computes accurate KPIs, features, trends, and funnel from records', () => {
    const parsed = analyticsService.parseAnalyticsFile(sampleCSV, 'events.csv')
    const kpis = analyticsService.calculateKPIs(parsed.records)

    expect(kpis.totalEvents).toBe(5)
    expect(kpis.activeUsers).toBe(3) // u1, u2, u3
    expect(kpis.totalSessions).toBe(4) // s1, s2, s3, s4
    expect(kpis.featureCounts['Search Bar']).toBe(2)
    expect(kpis.featureCounts['Export CSV']).toBe(2)

    // Feature Analytics
    const featureBreakdown = analyticsService.getFeatureAnalytics(parsed.records)
    expect(featureBreakdown.length).toBe(3)
    const searchBar = featureBreakdown.find(f => f.name === 'Search Bar')
    expect(searchBar.eventCount).toBe(2)
    expect(searchBar.uniqueUsers).toBe(1)

    // Usage Trends
    const trends = analyticsService.getUsageTrends(parsed.records)
    expect(trends.length).toBeGreaterThan(0)
    expect(trends[0]).toHaveProperty('date')
    expect(trends[0]).toHaveProperty('events')

    // Funnel Analytics
    const funnel = analyticsService.getFunnelAnalytics(parsed.records)
    expect(funnel.length).toBe(5)
    expect(funnel[0].step).toBe('1. Active Session Start')
    expect(funnel[0].users).toBe(3)
  })

  it('filters datasets by relative time range properly', () => {
    const dataset = [
      { date: '2020-01-01', userId: 'uOld' },
      { date: new Date().toISOString().split('T')[0], userId: 'uNew' },
    ]
    const filtered7d = analyticsService.filterByTimeRange(dataset, '7d')
    expect(filtered7d.length).toBe(1)
    expect(filtered7d[0].userId).toBe('uNew')

    const all = analyticsService.filterByTimeRange(dataset, 'all')
    expect(all.length).toBe(2)
  })

  it('uses backend analytics overview when configured and computes demo dataset KPIs accurately', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: { get: () => 'application/json' },
      json: async () => ({
        activeUsers: 42,
        totalEvents: 500,
        totalSessions: 120,
      }),
    })

    const res = await analyticsService.getOverviewMetrics({ timeRange: '30d' })
    expect(res.success).toBe(true)
    expect(res.isDemo).toBe(false)
    expect(res.data.activeUsers).toBeGreaterThan(0)
    expect(res.data.activeUsers).toBe(42)
    fetchSpy.mockRestore()

    const filteredDemo = analyticsService.filterByTimeRange(DEMO_ANALYTICS_DATASET, '30d')
    const demoKpis = analyticsService.calculateKPIs(filteredDemo)
    expect(DEMO_ANALYTICS_DATASET.length).toBeGreaterThan(0)
    expect(demoKpis.activeUsers).toBeGreaterThan(0)
  })
})
