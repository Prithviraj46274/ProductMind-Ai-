import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { CopilotPage } from '../pages/CopilotPage'
import { copilotService } from '../services/api/copilotService'
import { useWorkspace } from '../context/WorkspaceContext'
import { useApp } from '../context/AppContext'

vi.mock('../services/api/copilotService', () => ({
  copilotService: {
    getConversations: vi.fn(),
    getConversation: vi.fn(),
    createConversation: vi.fn(),
    sendMessage: vi.fn(),
    archiveConversation: vi.fn(),
  },
}))

vi.mock('../context/WorkspaceContext', () => ({
  useWorkspace: vi.fn(),
}))

vi.mock('../context/AppContext', () => ({
  useApp: vi.fn(),
}))

describe('CopilotPage', () => {
  const addToast = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    window.HTMLElement.prototype.scrollIntoView = vi.fn()
    useApp.mockReturnValue({ addToast })
    useWorkspace.mockReturnValue({
      currentWorkspaceId: 'ws-1',
      currentWorkspace: { id: 'ws-1', name: 'Apex WS' },
    })
  })

  it('loads workspace conversations, sends message, and renders evidence', async () => {
    copilotService.getConversations.mockResolvedValue({
      conversations: [{ id: 'c1', title: 'Session 1', lastMessageAt: '2026-11-12T10:00:00Z' }],
      total: 1,
    })
    copilotService.getConversation.mockResolvedValue({
      conversation: { id: 'c1', title: 'Session 1' },
      messages: [{ id: 'm1', role: 'user', content: 'Prior Q', status: 'completed' }],
      total: 1,
    })
    copilotService.sendMessage.mockResolvedValue({
      conversation: { id: 'c1', title: 'Session 1', lastMessageAt: '2026-11-12T10:01:00Z' },
      userMessage: { id: 'm2', role: 'user', content: 'Top pain?', status: 'completed' },
      assistantMessage: {
        id: 'm3',
        role: 'assistant',
        content: 'Slow CSV export.',
        status: 'completed',
        evidence: [{ type: 'feedback', label: 'Feedback (20)', path: '/feedback', count: 20 }],
      },
      retried: false,
    })

    render(
      <MemoryRouter>
        <CopilotPage />
      </MemoryRouter>
    )

    await waitFor(() => expect(screen.getByText('Prior Q')).toBeInTheDocument())

    const input = screen.getByPlaceholderText(/Ask anything about feedback/i)
    fireEvent.change(input, { target: { value: 'Top pain?' } })
    fireEvent.click(screen.getByRole('button', { name: /send/i }))

    await waitFor(() => expect(screen.getByText('Slow CSV export.')).toBeInTheDocument())
    expect(screen.getByText('Feedback (20)')).toBeInTheDocument()
  })

  it('reuses the same requestId on manual retry after 429 and prevents duplicate submissions', async () => {
    copilotService.getConversations.mockResolvedValue({ conversations: [], total: 0 })
    const err429 = new Error(
      'Copilot is temporarily unavailable because the AI service has reached its request limit. Please try again later.'
    )
    err429.status = 429
    copilotService.sendMessage
      .mockRejectedValueOnce(err429)
      .mockResolvedValueOnce({
        conversation: { id: 'c-new', title: 'Retry test', lastMessageAt: '2026-11-12T10:02:00Z' },
        userMessage: { id: 'u1', role: 'user', content: 'Retry test', status: 'completed' },
        assistantMessage: { id: 'a1', role: 'assistant', content: 'Success on retry', status: 'completed', evidence: [] },
        retried: true,
      })

    render(
      <MemoryRouter>
        <CopilotPage />
      </MemoryRouter>
    )

    await waitFor(() => expect(copilotService.getConversations).toHaveBeenCalledWith('ws-1'))

    const input = screen.getByPlaceholderText(/Ask anything about feedback/i)
    fireEvent.change(input, { target: { value: 'Retry test' } })
    fireEvent.click(screen.getByRole('button', { name: /send/i }))

    await waitFor(() => expect(screen.getByText(/reached its request limit/i)).toBeInTheDocument())

    const firstReqId = copilotService.sendMessage.mock.calls[0][0].requestId
    expect(firstReqId).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /retry/i }))
    await waitFor(() => expect(screen.getByText('Success on retry')).toBeInTheDocument())

    const secondReqId = copilotService.sendMessage.mock.calls[1][0].requestId
    expect(secondReqId).toBe(firstReqId)
  })

  it('clears previous workspace conversations when switching workspaces and archives cleanly', async () => {
    copilotService.getConversations
      .mockResolvedValueOnce({
        conversations: [{ id: 'c-ws1', title: 'WS1 Chat' }],
        total: 1,
      })
      .mockResolvedValueOnce({
        conversations: [],
        total: 0,
      })
    copilotService.getConversation.mockResolvedValue({
      conversation: { id: 'c-ws1', title: 'WS1 Chat' },
      messages: [{ id: 'm-ws1', role: 'assistant', content: 'WS1 Secret', status: 'completed' }],
      total: 1,
    })

    const { rerender } = render(
      <MemoryRouter>
        <CopilotPage />
      </MemoryRouter>
    )

    await waitFor(() => expect(screen.getByText('WS1 Secret')).toBeInTheDocument())

    useWorkspace.mockReturnValue({
      currentWorkspaceId: 'ws-2',
      currentWorkspace: { id: 'ws-2', name: 'Beta WS' },
    })

    rerender(
      <MemoryRouter>
        <CopilotPage />
      </MemoryRouter>
    )

    await waitFor(() => expect(screen.queryByText('WS1 Secret')).not.toBeInTheDocument())
  })
})

