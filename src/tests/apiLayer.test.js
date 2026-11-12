import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { apiClient } from '../services/api/apiClient'
import { authService } from '../services/api/authService'
import { prioritizationService } from '../services/api/prioritizationService'
import { aggregationService } from '../services/api/aggregationService'

describe('Centralized API Client and Service Layer', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('correctly reports backend configured state', () => {
    const configuredBaseUrl = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
    expect(apiClient.isConfigured()).toBe(Boolean(configuredBaseUrl))
    expect(typeof apiClient.getBaseUrl()).toBe('string')
    expect(apiClient.getBaseUrl()).toBe(configuredBaseUrl)
  })

  it('authenticates PM user against backend auth endpoint and rejects invalid credentials', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          accessToken: 'jwt-access-token',
          refreshToken: 'jwt-refresh-token',
          expiresIn: 3600,
          user: {
            id: 'usr-pm-01',
            name: 'Alex Rivera',
            email: 'alex.rivera@productmind.ai',
            role: 'Lead Product Architect',
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        headers: { get: () => 'application/json' },
        json: async () => ({ detail: 'Invalid email or password' }),
      })

    const res = await authService.login('alex.rivera@productmind.ai', 'valid-pass-123')
    expect(res.success).toBe(true)
    expect(res.isDemo).toBe(false)
    expect(res.data.user.role).toBe('Lead Product Architect')
    expect(res.data.token).toBe('jwt-access-token')

    // Test session retrieval
    const currentSession = authService.getCurrentSession()
    expect(currentSession).not.toBeNull()
    expect(currentSession.user.name).toBe('Alex Rivera')
    expect(currentSession.refreshToken).toBe('jwt-refresh-token')

    // Test rejection of invalid credentials
    const badRes = await authService.login('unknown_guest@productmind.ai', 'wrongpass')
    expect(badRes.success).toBe(false)
    expect(badRes.status).toBe(401)
    expect(fetchSpy).toHaveBeenCalledTimes(2)
  })

  it('handles session expiration and logout correctly', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => 'application/json' },
      json: async () => ({
        accessToken: 'jwt-access-token',
        refreshToken: 'jwt-refresh-token',
        expiresIn: 3600,
        user: {
          id: 'usr-pm-01',
          name: 'Alex Rivera',
          email: 'alex.rivera@productmind.ai',
          role: 'Lead Product Architect',
        },
      }),
    })

    await authService.login('alex.rivera@productmind.ai', 'valid-pass-123')
    expect(authService.getCurrentSession()).not.toBeNull()

    // Simulate expired session (expired 1 hour ago)
    const session = JSON.parse(localStorage.getItem('pmai_mock_auth_session'))
    session.expiresAt = Date.now() - 3600000
    localStorage.setItem('pmai_mock_auth_session', JSON.stringify(session))

    const expiredCheck = authService.getCurrentSession()
    expect(expiredCheck).toBeNull()

    // Logout cleans storage
    await authService.logout()
    expect(localStorage.getItem('pmai_mock_auth_session')).toBeNull()
  })

  it('prioritizationService enforces exact 4-factor formula and tiers', () => {
    const feature = {
      customerImpact: 9, // 9 * 0.35 = 3.15
      urgency: 8,        // 8 * 0.30 = 2.40
      demand: 7,         // 7 * 0.20 = 1.40
      businessValue: 6,  // 6 * 0.15 = 0.90
    } // sum = 7.85

    const score = prioritizationService.calculateScore(feature)
    expect(score).toBe(7.85)

    const breakdown = prioritizationService.getBreakdown(feature)
    expect(breakdown.customerImpactContribution).toBe(3.15)
    expect(breakdown.urgencyContribution).toBe(2.40)
    expect(breakdown.demandContribution).toBe(1.40)
    expect(breakdown.businessValueContribution).toBe(0.90)
    expect(breakdown.totalScore).toBe(7.85)

    const tier = prioritizationService.getTier(score)
    expect(tier.label).toBe('High')

    expect(prioritizationService.FACTOR_WEIGHTS.customerImpact).toBe(0.35)
    expect(prioritizationService.FACTOR_WEIGHTS.urgency).toBe(0.30)
    expect(prioritizationService.FACTOR_WEIGHTS.demand).toBe(0.20)
    expect(prioritizationService.FACTOR_WEIGHTS.businessValue).toBe(0.15)

    const explanation = prioritizationService.getExplanation(feature)
    expect(explanation.summary).toContain('High')
    expect(explanation.totalScore).toBe(7.85)
  })

  it('aggregationService integrates backend feature grouping and supports local clustering fallback', async () => {
    const feedbackList = [
      { id: 'fb-1', title: 'Export to CSV is needed', category: 'Analytics', tags: ['csv-export'], sentiment: 'Neutral' },
      { id: 'fb-2', title: 'Need CSV download button', category: 'Analytics', tags: ['csv-export'], sentiment: 'Negative' },
      { id: 'fb-3', title: 'Dark mode contrast is too low', category: 'Usability', tags: ['contrast'], sentiment: 'Negative' },
    ]

    // 1. Verify local clustering fallback when no active workspace backend groups exist
    const groupsRes = await aggregationService.getGroups(feedbackList, [])
    expect(groupsRes.success).toBe(true)
    expect(groupsRes.isDemo).toBe(true)
    expect(groupsRes.data.length).toBe(2)

    const analyticsGroup = groupsRes.data.find(g => g.category === 'Analytics')
    expect(analyticsGroup).toBeDefined()
    expect(analyticsGroup.feedbackItems.length).toBe(2)
    expect(analyticsGroup.count).toBe(2)

    // 2. Verify Phase 2 backend feature grouping & retrieval API methods
    localStorage.setItem('pmai_active_workspace_id', 'ws-test-123')
    const mockBackendGroups = [
      { feature_group_id: 'fg-1', title: 'CSV Export', total_request_count: 2 },
      { feature_group_id: 'fg-2', title: 'Dark Mode Contrast', total_request_count: 1 },
    ]
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({ groups: mockBackendGroups }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => mockBackendGroups,
      })

    const grouped = await aggregationService.groupFeatures({
      workspaceId: 'ws-test-123',
      feedbackIds: ['fb-1', 'fb-2', 'fb-3'],
    })
    expect(grouped.groups).toHaveLength(2)

    const fetched = await aggregationService.getGroups(feedbackList, [])
    expect(fetched.success).toBe(true)
    expect(fetched.isDemo).toBe(false)
    expect(fetched.data).toHaveLength(2)
    expect(fetched.data[0].feature_group_id).toBe('fg-1')
    expect(fetchSpy).toHaveBeenCalledTimes(2)
  })
})
