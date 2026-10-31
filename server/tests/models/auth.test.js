import { describe, it, expect } from 'vitest'
import mongoose from 'mongoose'
import { User } from '../../src/models/auth/User.model.js'
import { Workspace } from '../../src/models/auth/Workspace.model.js'
import { WorkspaceMembership } from '../../src/models/auth/WorkspaceMembership.model.js'
import { AuthSession } from '../../src/models/auth/AuthSession.model.js'
import { UserRole } from '../../src/constants/enums.js'

describe('Auth & Identity Models', () => {
  describe('User Model', () => {
    it('validates a correct user document with normalized email and default platformRole', () => {
      const user = new User({
        name: 'Alex Rivera',
        email: 'Alex.Rivera@ProductMind.AI',
        passwordHash: '$2a$10$abcdefghijklmnopqrstuvwxyz1234567890',
      })
      const err = user.validateSync()
      expect(err).toBeUndefined()
      // Email should be normalized to lowercase
      expect(user.email).toBe('alex.rivera@productmind.ai')
      expect(user.platformRole).toBe('user')
      expect(user.avatar).toBeNull() // No fabricated initials
    })

    it('rejects invalid email formats', () => {
      const user = new User({
        name: 'Alex Rivera',
        email: 'invalid-email-address',
        passwordHash: '$2a$10$abcdefghijklmnopqrstuvwxyz1234567890',
      })
      const err = user.validateSync()
      expect(err).toBeDefined()
      expect(err.errors.email).toBeDefined()
    })

    it('enforces required name, email, and passwordHash', () => {
      const user = new User({})
      const err = user.validateSync()
      expect(err).toBeDefined()
      expect(err.errors.name).toBeDefined()
      expect(err.errors.email).toBeDefined()
      expect(err.errors.passwordHash).toBeDefined()
    })

    it('rejects unsupported platformRole enums', () => {
      const user = new User({
        name: 'Hacker User',
        email: 'hacker@example.com',
        passwordHash: '$2a$10$abcdefghijklmnopqrstuvwxyz1234567890',
        platformRole: 'super_god_mode',
      })
      const err = user.validateSync()
      expect(err).toBeDefined()
      expect(err.errors.platformRole).toBeDefined()
    })
  })

  describe('Workspace Model', () => {
    it('validates a proper workspace document and defaults plan to Starter Tier', () => {
      const ws = new Workspace({
        name: 'Apex Cloud Product Ops',
        slug: 'apex-cloud-product-ops',
        ownerId: new mongoose.Types.ObjectId(),
      })
      const err = ws.validateSync()
      expect(err).toBeUndefined()
      expect(ws.plan).toBe('Starter Tier')
    })

    it('rejects invalid slug characters (spaces or uppercase)', () => {
      const ws = new Workspace({
        name: 'Apex Cloud Product Ops',
        slug: 'Apex Cloud Invalid',
        ownerId: new mongoose.Types.ObjectId(),
      })
      const err = ws.validateSync()
      expect(err).toBeDefined()
      expect(err.errors.slug).toBeDefined()
    })

    it('requires ownerId reference', () => {
      const ws = new Workspace({
        name: 'Apex Cloud Product Ops',
        slug: 'apex-cloud-product-ops',
      })
      const err = ws.validateSync()
      expect(err).toBeDefined()
      expect(err.errors.ownerId).toBeDefined()
    })
  })

  describe('WorkspaceMembership Model', () => {
    it('enforces workspaceId, userId, and validates workspace role', () => {
      const membership = new WorkspaceMembership({
        workspaceId: new mongoose.Types.ObjectId(),
        userId: new mongoose.Types.ObjectId(),
        role: UserRole.LEAD_PRODUCT_ARCHITECT,
      })
      const err = membership.validateSync()
      expect(err).toBeUndefined()
      expect(membership.role).toBe(UserRole.LEAD_PRODUCT_ARCHITECT)
    })

    it('verifies compound unique index on { workspaceId: 1, userId: 1 }', () => {
      const indexes = WorkspaceMembership.schema.indexes()
      const hasCompoundUnique = indexes.some(
        ([idx, opts]) => idx.workspaceId === 1 && idx.userId === 1 && opts?.unique === true
      )
      expect(hasCompoundUnique).toBe(true)
    })
  })

  describe('AuthSession Model', () => {
    it('verifies TTL index configuration on expiresAt', () => {
      const expiresPath = AuthSession.schema.path('expiresAt')
      expect(expiresPath.options.index).toEqual({ expires: 0 })
    })
  })
})
