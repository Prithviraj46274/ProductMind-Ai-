import { describe, it, expect, vi, beforeEach } from 'vitest'
import React from 'react'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { AnalyticsPage } from '../pages/AnalyticsPage'
import { analyticsService } from '../services/api/analyticsService'

const mockAddToast = vi.fn()
let mockWorkspace = { id: 'ws-alpha', name: 'Alpha Workspace' }

vi.mock('../context/AppContext', () => ({
  useApp: () => ({ addToast: mockAddToast }),
}))

vi.mock('../context/WorkspaceContext', () => ({
  useWorkspace: () => ({ currentWorkspace: mockWorkspace }),
}))

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }) => <div data-testid="recharts-container">{children}</div>,
  AreaChart: ({ data, children }) => <div data-testid="area-chart" data-points={data?.length ?? 0}>{children}</div>,
  Area: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  CartesianGrid: () => null,
  Legend: () => null,
}))

describe('AnalyticsPage Phase 3.2 Dashboard', () => {
  beforeEach(() => {
    cleanup()
    vi.restoreAllMocks()
    mockWorkspace = { id: 'ws-alpha', name: 'Alpha Workspace' }
    vi.spyOn(analyticsService, 'getFeatureAnalyticsFromApi').mockResolvedValue({
      success: true,
      data: { items: [], total: 0 },
    })
    vi.spyOn(analyticsService, 'getFunnelAnalyticsFromApi').mockResolvedValue({
      success: true,
      data: { available: false, reason: 'Funnel step and conversion semantics are not defined for ingested events.', steps: [], availableEvents: [] },
    })
  })

  it('shows loading state then renders real KPIs, unavailable partial metrics, and trend chart', async () => {
    let resolveOverview
    const overviewPromise = new Promise((r) => { resolveOverview = r })
    vi.spyOn(analyticsService, 'getOverviewMetrics').mockReturnValueOnce(overviewPromise)
    vi.spyOn(analyticsService, 'getUsageTrendsFromApi').mockResolvedValueOnce({
      success: true,
      data: {
        items: [
          { date: '2026-11-01', events: 18, activeUsers: 5, sessions: 6 },
          { date: '2026-11-02', events: 24, activeUsers: 8, sessions: 9 },
        ],
        observedDays: 2,
      },
    })

    render(<AnalyticsPage />)
    expect(screen.getByText(/Loading workspace analytics from MongoDB Atlas/i)).toBeTruthy()

    resolveOverview({
      success: true,
      data: {
        totalEvents: 42,
        activeUsers: null,
        sessions: 15,
        avgEventDurationSeconds: 64.4,
        observedDays: 2,
        coverage: { state: 'partial', totalEvents: 42, eventsWithActorId: 30, eventsWithSessionId: 42 },
        dateRange: { startDate: '2026-10-14', endDate: '2026-11-12', capped: false },
      },
    })

    await waitFor(() => expect(screen.getAllByText('42').length).toBeGreaterThanOrEqual(1))
    expect(screen.getByText('15')).toBeTruthy()
    expect(screen.getByText('Unavailable')).toBeTruthy()
    expect(screen.getByText('64s')).toBeTruthy()
    expect(screen.getByTestId('area-chart').getAttribute('data-points')).toBe('2')
  })

  it('triggers fresh backend queries for 7d, 90d, and custom date ranges', async () => {
    const overviewSpy = vi.spyOn(analyticsService, 'getOverviewMetrics').mockResolvedValue({
      success: true,
      data: {
        totalEvents: 10,
        activeUsers: 3,
        sessions: 4,
        avgEventDurationSeconds: null,
        observedDays: 1,
        coverage: { state: 'observed', totalEvents: 10, eventsWithActorId: 10, eventsWithSessionId: 10 },
        dateRange: { startDate: '2026-11-01', endDate: '2026-11-12', capped: false },
      },
    })
    const trendsSpy = vi.spyOn(analyticsService, 'getUsageTrendsFromApi').mockResolvedValue({
      success: true,
      data: { items: [], observedDays: 0 },
    })

    render(<AnalyticsPage />)
    await waitFor(() => expect(overviewSpy).toHaveBeenCalledWith(expect.objectContaining({ workspaceId: 'ws-alpha', timeRange: '30d' })))

    fireEvent.click(screen.getByText('7 Days'))
    await waitFor(() => expect(overviewSpy).toHaveBeenCalledWith(expect.objectContaining({ timeRange: '7d' })))

    fireEvent.click(screen.getByText('90 Days'))
    await waitFor(() => expect(overviewSpy).toHaveBeenCalledWith(expect.objectContaining({ timeRange: '90d' })))

    fireEvent.click(screen.getByText('Custom'))
    fireEvent.change(screen.getByLabelText('Start Date'), { target: { value: '2026-10-01' } })
    fireEvent.change(screen.getByLabelText('End Date'), { target: { value: '2026-10-15' } })
    fireEvent.click(screen.getByText('Apply Range'))

    await waitFor(() => {
      expect(overviewSpy).toHaveBeenCalledWith(
        expect.objectContaining({ timeRange: 'custom', startDate: '2026-10-01', endDate: '2026-10-15' })
      )
      expect(trendsSpy).toHaveBeenCalledWith(
        expect.objectContaining({ timeRange: 'custom', startDate: '2026-10-01', endDate: '2026-10-15' })
      )
    })
  })

  it('refetches data on workspace switch and supports error + retry', async () => {
    const overviewSpy = vi
      .spyOn(analyticsService, 'getOverviewMetrics')
      .mockRejectedValueOnce(new Error('Atlas connection timeout'))
      .mockResolvedValue({
        success: true,
        data: {
          totalEvents: 0,
          activeUsers: 0,
          sessions: 0,
          avgEventDurationSeconds: null,
          observedDays: 0,
          coverage: { state: 'no_data', totalEvents: 0, eventsWithActorId: 0, eventsWithSessionId: 0 },
          dateRange: { startDate: '2026-10-14', endDate: '2026-11-12', capped: false },
        },
      })
    vi.spyOn(analyticsService, 'getUsageTrendsFromApi').mockResolvedValue({
      success: true,
      data: { items: [], observedDays: 0 },
    })

    const { rerender } = render(<AnalyticsPage />)
    await waitFor(() => expect(screen.getByText(/Atlas connection timeout/i)).toBeTruthy())

    fireEvent.click(screen.getByText('Retry Request'))
    await waitFor(() => expect(screen.getByText('No usage events in this window')).toBeTruthy())

    mockWorkspace = { id: 'ws-beta', name: 'Beta Workspace' }
    rerender(<AnalyticsPage />)
    await waitFor(() =>
      expect(overviewSpy).toHaveBeenCalledWith(expect.objectContaining({ workspaceId: 'ws-beta' }))
    )
  })

  it('renders feature analytics comparisons, opens individual feature history, and evaluates ordered funnel', async () => {
    vi.spyOn(analyticsService, 'getOverviewMetrics').mockResolvedValue({
      success: true,
      data: {
        totalEvents: 30,
        activeUsers: 10,
        sessions: 12,
        avgEventDurationSeconds: 45,
        observedDays: 2,
        coverage: { state: 'observed', totalEvents: 30, eventsWithActorId: 30, eventsWithSessionId: 30 },
        dateRange: { startDate: '2026-10-14', endDate: '2026-11-12', capped: false },
      },
    })
    const trendsSpy = vi.spyOn(analyticsService, 'getUsageTrendsFromApi').mockResolvedValue({
      success: true,
      data: { items: [{ date: '2026-11-10', events: 15, activeUsers: 5 }], observedDays: 1 },
    })
    vi.spyOn(analyticsService, 'getFeatureAnalyticsFromApi').mockResolvedValue({
      success: true,
      data: {
        items: [
          { name: 'AI Copilot', eventCount: 20, uniqueUsers: 8, adoptionPercent: 80, trendDeltaPercent: 25, avgEventDurationSeconds: 50 },
          { name: 'CSV Export', eventCount: 10, uniqueUsers: 4, adoptionPercent: 40, trendDeltaPercent: -15, avgEventDurationSeconds: 20 },
        ],
        total: 2,
      },
    })
    const funnelSpy = vi
      .spyOn(analyticsService, 'getFunnelAnalyticsFromApi')
      .mockResolvedValueOnce({
        success: true,
        data: {
          available: false,
          reason: 'Define ordered steps',
          steps: [],
          availableEvents: ['view', 'click', 'complete'],
        },
      })
      .mockResolvedValueOnce({
        success: true,
        data: {
          available: true,
          reason: null,
          availableEvents: ['view', 'click', 'complete'],
          steps: [
            { step: 'view', order: 1, users: 10, conversionRate: 100, stepConversionRate: 100, dropOffCount: 0, dropOffRate: 0 },
            { step: 'complete', order: 2, users: 4, conversionRate: 40, stepConversionRate: 40, dropOffCount: 6, dropOffRate: 60 },
          ],
        },
      })

    render(<AnalyticsPage />)
    await waitFor(() => expect(screen.getAllByText('AI Copilot').length).toBeGreaterThanOrEqual(1))
    expect(screen.getByText('+25%')).toBeTruthy()
    expect(screen.getByText('-15%')).toBeTruthy()

    // Click feature row to open individual feature history modal
    fireEvent.click(screen.getAllByText('AI Copilot')[1])
    await waitFor(() =>
      expect(trendsSpy).toHaveBeenCalledWith(expect.objectContaining({ featureName: 'AI Copilot' }))
    )
    expect(screen.getByText(/Feature Telemetry: AI Copilot/i)).toBeTruthy()
    fireEvent.click(screen.getByText('Close Drill-Down'))

    // Evaluate funnel stages
    fireEvent.change(screen.getByLabelText('Funnel Stages'), { target: { value: 'view, complete' } })
    fireEvent.click(screen.getByText('Evaluate Funnel'))

    await waitFor(() =>
      expect(funnelSpy).toHaveBeenCalledWith(expect.objectContaining({ steps: ['view', 'complete'] }))
    )
    expect(screen.getByText(/Drop-off: 6 users \(60%\)/i)).toBeTruthy()
  })
})

