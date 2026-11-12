import { describe, it, expect, vi, beforeEach } from 'vitest'
import React from 'react'
import { render, screen, waitFor, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { PrioritizationPage } from '../pages/PrioritizationPage'
import { prioritizationService } from '../services/api/prioritizationService'

vi.mock('../context/AppContext', () => ({
  useApp: () => ({
    features: [],
    setFeatures: vi.fn(),
    addToast: vi.fn(),
    feedbacks: [],
    activeWorkspace: 'ws-1',
    selectedFeatureId: null,
    setSelectedFeatureId: vi.fn(),
    isDemoMode: false,
  }),
}))

vi.mock('../context/WorkspaceContext', () => ({
  useWorkspace: () => ({ currentWorkspace: { id: 'ws-1', name: 'Phase34 WS' } }),
}))

describe('PrioritizationPage Phase 3.4 Usage Impact Explainability', () => {
  beforeEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('displays Usage Impact evidence when available and missing-data reweighting when unavailable', async () => {
    vi.spyOn(prioritizationService, 'getPrioritizationResults').mockResolvedValueOnce([
      {
        result_id: 'res-with-usage',
        workspace_id: 'ws-1',
        feature_group_id: 'fg-1',
        group_name: 'SSO Audit Trail',
        final_score: 79.4,
        priority_level: 'High',
        coverage_percentage: 100.0,
        missing_data: [],
        factor_scores: {
          customer_demand: 80,
          urgency: 75,
          business_impact: 85,
          strategic_alignment: 80,
          sentiment: 70,
          usage_impact: 82.5,
        },
        factor_weights: {
          customer_demand: 0.25,
          urgency: 0.2,
          business_impact: 0.2,
          strategic_alignment: 0.15,
          sentiment: 0.1,
          usage_impact: 0.1,
        },
        explanation: 'All 6 factors measured.',
        agent_metadata: {
          usage_analytics_evidence: {
            available: true,
            matched_feature: 'SSO Audit Trail',
            event_count: 130,
            unique_users: 100,
            adoption_rate: 75,
            trend_direction: 'increasing',
            coverage_status: 'complete',
            weight_applied: 0.1,
          },
        },
      },
      {
        result_id: 'res-no-usage',
        workspace_id: 'ws-1',
        feature_group_id: 'fg-2',
        group_name: 'Dark Mode',
        final_score: 74.2,
        priority_level: 'High',
        coverage_percentage: 90.0,
        missing_data: ['usage_impact'],
        factor_scores: {
          customer_demand: 75,
          urgency: 70,
          business_impact: 78,
          strategic_alignment: 72,
          sentiment: 75,
        },
        factor_weights: {
          customer_demand: 0.2778,
          urgency: 0.2222,
          business_impact: 0.2222,
          strategic_alignment: 0.1667,
          sentiment: 0.1111,
        },
        explanation: 'Usage Impact reweighted.',
        agent_metadata: {
          usage_analytics_evidence: {
            available: false,
            missing_reason: 'No matching feature usage telemetry found in workspace MongoDB Atlas rollups; weight reweighted across available factors.',
          },
        },
      },
    ])

    render(
      <MemoryRouter>
        <PrioritizationPage />
      </MemoryRouter>
    )

    await waitFor(() => expect(screen.getByText(/Usage Analytics Evidence \(SSO Audit Trail\)/i)).toBeTruthy())
    expect(screen.getByText(/Events: 130/i)).toBeTruthy()
    expect(screen.getByText(/Unique Users: 100/i)).toBeTruthy()
    expect(screen.getByText(/Adoption: 75%/i)).toBeTruthy()
    expect(screen.getByText(/Trend: increasing/i)).toBeTruthy()
    expect(screen.getByText(/Usage Analytics Unavailable:/i)).toBeTruthy()
    expect(screen.getByText(/Reweighted \(missing: usage_impact\)/i)).toBeTruthy()
  })
})
