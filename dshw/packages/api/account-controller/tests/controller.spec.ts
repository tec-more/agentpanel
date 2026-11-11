/** Account Remote delegation preserves provider results, failures, and stream lifetime. */
import { Context } from '@deepseek-ai/cordis'
import type { AgentPanelAccount } from '@deepseek-ai/dsh-agentpanel-account'
import type { AccountBonusBatch, AccountBonusOrderId, AccountClientMetadata, AccountUserId } from '@deepseek-ai/dsh-deepseek-account/types'
import type { AccountView, SignInAttemptId } from '../src/types.ts'
import { afterEach, expect, it, vi } from 'vitest'
import AccountController from '../src/index.ts'

declare module '@deepseek-ai/cordis' {
  interface Events {
    /** Server rejection or renewal failure removed the current lease credential. */
    'agentpanel-account/session-expired'(): void
  }
}

const roots: Context[] = []
afterEach(async () => { await Promise.all(roots.splice(0).map(ctx => ctx.fiber.dispose())) })
const state: AccountView = { status: 'signed-out', links: { usageUrl: 'https://platform.example/usage', topUpUrl: 'https://platform.example/top_up' }, attempt: null }
const client: AccountClientMetadata = { version: '0.0.0-test', locale: 'zh-CN', timezoneOffsetSeconds: 28_800 }

function fixture() {
  const ctx = new Context()
  roots.push(ctx)
  const provider = {
    getState: vi.fn<AgentPanelAccount['getState']>().mockResolvedValue(state),
    getProfile: vi.fn<AgentPanelAccount['getProfile']>().mockResolvedValue({ status: 'failed' }),
    getBalance: vi.fn<AgentPanelAccount['getBalance']>().mockResolvedValue(null),
    getUnnotifiedBonuses: vi.fn<AgentPanelAccount['getUnnotifiedBonuses']>().mockResolvedValue(null),
    ackBonusNotified: vi.fn<AgentPanelAccount['ackBonusNotified']>().mockResolvedValue(false),
    startSignIn: vi.fn<AgentPanelAccount['startSignIn']>().mockResolvedValue(state),
    cancelSignIn: vi.fn<AgentPanelAccount['cancelSignIn']>().mockResolvedValue(state),
    signOut: vi.fn<AgentPanelAccount['signOut']>().mockResolvedValue(state),
    importSession: vi.fn<AgentPanelAccount['importSession']>().mockResolvedValue(state),
    clearSession: vi.fn<AgentPanelAccount['clearSession']>().mockResolvedValue(state),
    getAuthMode: vi.fn<AgentPanelAccount['getAuthMode']>().mockResolvedValue('customer'),
    sendCode: vi.fn<AgentPanelAccount['sendCode']>().mockResolvedValue({ ok: true, message: '' }),
    register: vi.fn<AgentPanelAccount['register']>().mockResolvedValue({ ok: true, message: '', state }),
    login: vi.fn<AgentPanelAccount['login']>().mockResolvedValue({ ok: true, message: '', state }),
    loginCode: vi.fn<AgentPanelAccount['loginCode']>().mockResolvedValue({ ok: true, message: '', state }),
    watch: vi.fn<AgentPanelAccount['watch']>(),
  }
  ctx.provide('agentpanelAccount', provider as never)
  return { ctx, provider, controller: new AccountController(ctx) }
}

it('delegates account operations without coupling profile and balance queries', async () => {
  const { provider, controller } = fixture()
  expect(await controller.getState()).toBe(state)
  expect(await controller.getProfile(client)).toEqual({ status: 'failed' })
  expect(provider.getBalance).not.toHaveBeenCalled()
  expect(await controller.getBalance(client)).toBeNull()
  expect(await controller.startSignIn(client, 'http://127.0.0.1:8080', 'desktop')).toBe(state)
  expect(provider.startSignIn).toHaveBeenCalledExactlyOnceWith(client, 'http://127.0.0.1:8080', 'desktop')
  const id = 'attempt' as SignInAttemptId
  expect(await controller.cancelSignIn(id)).toBe(state)
  expect(provider.cancelSignIn).toHaveBeenCalledExactlyOnceWith(id)
  expect(await controller.signOut(client)).toBe(state)
  expect(provider.signOut).toHaveBeenCalledExactlyOnceWith(client)
  const session = { leaseId: 'lease-cus', virtualKey: 'dgw.lease-cus.secret', expiresAtMs: Date.now() + 900_000 }
  expect(await controller.importSession(session)).toBe(state)
  expect(provider.importSession).toHaveBeenCalledExactlyOnceWith(session)
  expect(await controller.clearSession()).toBe(state)
  expect(provider.clearSession).toHaveBeenCalledExactlyOnceWith()
  const failure = new Error('storage unavailable')
  provider.signOut.mockRejectedValueOnce(failure)
  await expect(controller.signOut(client)).rejects.toBe(failure)
})

it('delegates the customer sign-in surface to the provider', async () => {
  const { provider, controller } = fixture()
  const denied = { ok: false, message: '密码错误', state: null }
  expect(await controller.getAuthMode()).toBe('customer')
  expect(provider.getAuthMode).toHaveBeenCalledExactlyOnceWith()
  expect(await controller.customerSendCode('user@example.com', 'login')).toEqual({ ok: true, message: '' })
  expect(provider.sendCode).toHaveBeenCalledExactlyOnceWith('user@example.com', 'login')
  expect(await controller.customerLogin('user@example.com', 'secret')).toEqual({ ok: true, message: '', state })
  expect(provider.login).toHaveBeenCalledExactlyOnceWith('user@example.com', 'secret')
  expect(await controller.customerLoginCode('user@example.com', '123456')).toEqual({ ok: true, message: '', state })
  expect(provider.loginCode).toHaveBeenCalledExactlyOnceWith('user@example.com', '123456')
  expect(await controller.customerRegister('user@example.com', '123456', 'secret')).toEqual({ ok: true, message: '', state })
  expect(provider.register).toHaveBeenCalledExactlyOnceWith('user@example.com', '123456', 'secret')
  provider.login.mockResolvedValueOnce(denied)
  expect(await controller.customerLogin('user@example.com', 'wrong')).toBe(denied)
})

it('delegates bonus reads and acknowledgements without altering their values', async () => {
  const { provider, controller } = fixture()
  const accountId = 'account' as AccountUserId
  const orderId = 'order' as AccountBonusOrderId
  const batch: AccountBonusBatch = { accountId, bonuses: [{ orderId, expiresAt: '2026-10-21T12:00:00Z', message: '已赠送您 5.00 元 DSH 体验赠金。' }] }
  provider.getUnnotifiedBonuses.mockResolvedValueOnce(batch)
  expect(await controller.getUnnotifiedBonuses(client)).toBe(batch)
  expect(provider.getUnnotifiedBonuses).toHaveBeenCalledExactlyOnceWith(client)
  provider.ackBonusNotified.mockResolvedValueOnce(true)
  expect(await controller.ackBonusNotified(accountId, orderId, client)).toBe(true)
  expect(provider.ackBonusNotified).toHaveBeenCalledExactlyOnceWith(accountId, orderId, client)
  const failure = new Error('unavailable')
  provider.getUnnotifiedBonuses.mockRejectedValueOnce(failure)
  await expect(controller.getUnnotifiedBonuses(client)).rejects.toBe(failure)
})

it('passes the subscriber lifetime to the provider and returns its state stream', async () => {
  const { provider, controller } = fixture()
  const lifetime = new AbortController()
  const stream: AsyncIterable<AccountView> = { async *[Symbol.asyncIterator]() { yield state } }
  provider.watch.mockReturnValue(stream)
  expect(controller.watch(lifetime.signal)).toBe(stream)
  expect(provider.watch).toHaveBeenCalledExactlyOnceWith(lifetime.signal)
  const received: AccountView[] = []
  for await (const value of stream) received.push(value)
  expect(received).toEqual([state])
})

it('delivers expiry only to current subscribers and stops on disconnect', async () => {
  const { ctx, controller } = fixture()
  ctx.emit('agentpanel-account/session-expired')
  const lifetime = new AbortController()
  const iterator = controller.watchExpiry(lifetime.signal)[Symbol.asyncIterator]()
  const first = iterator.next()
  ctx.emit('agentpanel-account/session-expired')
  expect(await first).toEqual({ done: false, value: 'session-expired' })
  const next = iterator.next()
  lifetime.abort()
  expect(await next).toEqual({ done: true, value: undefined })
  const reconnect = new AbortController()
  const reopened = controller.watchExpiry(reconnect.signal)[Symbol.asyncIterator]().next()
  reconnect.abort()
  expect(await reopened).toEqual({ done: true, value: undefined })
})
