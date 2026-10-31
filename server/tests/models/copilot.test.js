import { describe, it, expect } from 'vitest'
import mongoose from 'mongoose'
import { CopilotConversation } from '../../src/models/copilot/CopilotConversation.model.js'
import { CopilotMessage } from '../../src/models/copilot/CopilotMessage.model.js'

describe('AI Copilot Models', () => {
  const workspaceId = new mongoose.Types.ObjectId()
  const userId = new mongoose.Types.ObjectId()
  const conversationId = new mongoose.Types.ObjectId()

  describe('CopilotConversation Model', () => {
    it('validates a conversation session', () => {
      const conv = new CopilotConversation({
        workspaceId,
        userId,
        title: 'Q4 Strategic Prioritization Session',
      })
      const err = conv.validateSync()
      expect(err).toBeUndefined()
      expect(conv.isArchived).toBe(false)
    })

    it('requires workspaceId and userId', () => {
      const conv = new CopilotConversation({})
      const err = conv.validateSync()
      expect(err).toBeDefined()
      expect(err.errors.workspaceId).toBeDefined()
      expect(err.errors.userId).toBeDefined()
    })
  })

  describe('CopilotMessage Model', () => {
    it('validates a user and assistant message with evidence links', () => {
      const msg = new CopilotMessage({
        workspaceId,
        conversationId,
        role: 'assistant',
        content: 'Based on feedback analysis, Sarah Jenkins reported latency issues on 5k+ items.',
        evidence: [
          {
            type: 'feedback',
            label: 'Related Feedback Explorer',
            path: '/feedback',
            count: 4,
          },
        ],
      })
      const err = msg.validateSync()
      expect(err).toBeUndefined()
    })

    it('rejects unsupported role enums', () => {
      const msg = new CopilotMessage({
        workspaceId,
        conversationId,
        role: 'alien_overlord',
        content: 'Greetings',
      })
      const err = msg.validateSync()
      expect(err).toBeDefined()
      expect(err.errors.role).toBeDefined()
    })
  })
})
