import { describe, it, expect, vi } from 'vitest'
import * as analyticsModule from '../services/api/analyticsService'
import { analyticsService } from '../services/api/analyticsService'

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

  it('removes demo analytics dataset and queries backend overview and trends APIs with date ranges', async () => {
    expect(analyticsModule.DEMO_ANALYTICS_DATASET).toBeUndefined()

    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          data: {
            totalEvents: 500,
            activeUsers: 42,
            sessions: 120,
            avgEventDurationSeconds: 65,
            coverage: { state: 'observed', totalEvents: 500, eventsWithActorId: 500, eventsWithSessionId: 500 },
            observedDays: 14,
            dateRange: { startDate: '2026-10-01', endDate: '2026-10-30', capped: false },
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          data: {
            items: [{ date: '2026-10-15', events: 25, activeUsers: 10, sessions: 12 }],
            observedDays: 1,
            dateRange: { startDate: '2026-10-01', endDate: '2026-10-15', capped: false },
          },
        }),
      })

    const overviewRes = await analyticsService.getOverviewMetrics({ workspaceId: 'ws-1', timeRange: '30d' })
    expect(overviewRes.success).toBe(true)
    expect(overviewRes.isDemo).toBe(false)
    expect(overviewRes.data.activeUsers).toBe(42)
    expect(overviewRes.data.totalEvents).toBe(500)
    expect(fetchSpy.mock.calls[0][0]).toContain('workspaceId=ws-1')
    expect(fetchSpy.mock.calls[0][0]).toContain('timeRange=30d')

    const trendsRes = await analyticsService.getUsageTrendsFromApi({
      workspaceId: 'ws-1',
      timeRange: 'custom',
      startDate: '2026-10-01',
      endDate: '2026-10-15',
    })
    expect(trendsRes.success).toBe(true)
    expect(trendsRes.data.items).toHaveLength(1)
    expect(fetchSpy.mock.calls[1][0]).toContain('startDate=2026-10-01')
    expect(fetchSpy.mock.calls[1][0]).toContain('endDate=2026-10-15')
    fetchSpy.mockRestore()
  })

  it('parses quoted CSV fields, reports invalid rows, and applies column overrides', () => {
    const quotedCsv = `uid,action,module,ts,dur
u1,feature_click,"Analytics, Pro",2026-10-15T10:00:00Z,45
u2,feature_view,"Analytics, Pro",invalid-ts,30
u3,feature_view,Dashboard,2026-10-16T11:00:00Z,-5
`
    const res = analyticsService.parseAnalyticsFile(quotedCsv, 'quoted.csv', {
      userId: 'uid',
      eventName: 'action',
      featureName: 'module',
      timestamp: 'ts',
      durationSeconds: 'dur',
    })

    expect(res.sourceType).toBe('csv')
    expect(res.totalCount).toBe(3)
    expect(res.validCount).toBe(1)
    expect(res.invalidCount).toBe(2)
    expect(res.records[0].featureName).toBe('Analytics, Pro')
    expect(res.validationErrors[0].rowNumber).toBe(2)
    expect(res.validationErrors[1].rowNumber).toBe(3)
    expect(res.ingestionItems).toHaveLength(1)
    expect(res.ingestionItems[0]).toMatchObject({
      actorId: 'u1',
      eventName: 'feature_click',
      featureName: 'Analytics, Pro',
      eventTimestamp: '2026-10-15T10:00:00.000Z',
      durationSeconds: 45,
    })
  })

  it('uploads validated analytics batches to backend Atlas endpoint with workspaceId', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 201,
      headers: { get: () => 'application/json' },
      json: async () => ({
        id: 'batch-1',
        workspaceId: 'ws-1',
        status: 'completed',
        totalRows: 1,
        acceptedRows: 1,
        rejectedRows: 0,
        duplicateRows: 0,
        results: [{ rowNumber: 1, status: 'accepted', eventId: 'evt-1', errors: [] }],
      }),
    })

    const summary = await analyticsService.uploadDataset({
      workspaceId: 'ws-1',
      fileName: 'events.json',
      sourceType: 'json',
      items: [
        {
          eventId: 'evt-1',
          eventName: 'view',
          eventType: 'view',
          eventTimestamp: '2026-10-15T10:00:00Z',
        },
      ],
    })

    expect(summary.acceptedRows).toBe(1)
    expect(summary.totalRows).toBe(1)
    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(fetchSpy.mock.calls[0][0]).toContain('/api/v1/analytics/datasets/upload?workspaceId=ws-1')
    fetchSpy.mockRestore()
  })

  it('throws error with HTTP status instead of returning empty zeros when backend responds with 401 or 500', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
      headers: { get: () => 'application/json' },
      json: async () => ({ detail: 'Session expired' }),
    })

    await expect(analyticsService.getOverviewMetrics({ workspaceId: 'ws-1', timeRange: '30d' })).rejects.toMatchObject({
      message: 'Session expired',
      status: 401,
    })
    fetchSpy.mockRestore()
  })
})
