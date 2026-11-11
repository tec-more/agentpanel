/**
 * Desktop customer account backend: email-code registration / login, JWT → cus-bound
 * lease exchange, persistence and revocation. `fetch` is mocked; the account file is
 * written to a temp dir so no live control plane or Electron runtime is required.
 */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { agentpanelAccountBackend, type AgentpanelAccountConfig } from '../src/agentpanel-account-backend.ts'
import type { AccountClientMetadata } from '@deepseek-ai/dsh-deepseek-account/types'

const CUSTOMER = 'http://cp.test/v1/customer'

function authResponse(): Record<string, unknown> {
  return {
    code: 0,
    msg: 'ok',
    success: true,
    status_code: 200,
    data: {
      access_token: 'jwt.cus.token',
      token_type: 'bearer',
      expires_in: 86400,
      customer: { id: 42, email: 'customer@example.test' },
    },
  }
}

function leaseResponse(): Record<string, unknown> {
  return {
    code: 0,
    msg: 'ok',
    success: true,
    status_code: 200,
    data: {
      lease_id: 'L1',
      virtual_key: 'dgw.L1.s',
      expires_at: new Date(Date.now() + 900_000).toISOString(),
      ttl_seconds: 900,
      renew_after_seconds: 720,
    },
  }
}

let dir: string
beforeEach(() => {
  dir = mkdtempSync(path.join(tmpdir(), 'dsh-ap-'))
  vi.stubGlobal('fetch', vi.fn())
})
afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  rmSync(dir, { recursive: true, force: true })
})

const config = (): AgentpanelAccountConfig => ({
  gatewayUrl: 'http://gw.test',
  customerUrl: CUSTOMER,
  storageDir: dir,
})

const client = (): AccountClientMetadata => ({
  version: '1.0.0',
  locale: 'en_US',
  timezoneOffsetSeconds: 0,
})

function mockControlPlane() {
  const fetchMock = vi.fn(async (input: string | URL | Request, _init?: RequestInit) => {
    const url = String(input)
    const body = url.includes('/auth/') ? authResponse()
      : url.includes('/leases') ? leaseResponse() : {}
    return { ok: true, json: async () => body } as Response
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

it('login exchanges a customer JWT for a cus-bound lease and persists both', async () => {
  const fetchMock = mockControlPlane()
  const backend = agentpanelAccountBackend(config())

  expect((await backend.state()).status).toBe('signed-out')
  const outcome = await backend.login('customer@example.test', 'secret123')
  expect(outcome.ok).toBe(true)
  if (!outcome.ok) return
  expect(outcome.state.status).toBe('credential-stored')
  expect(outcome.state.attempt?.phase).toBe('succeeded')

  expect(fetchMock).toHaveBeenCalledTimes(2)
  const [authUrl, authOpts] = fetchMock.mock.calls[0] as [string, RequestInit]
  expect(authUrl).toBe(`${CUSTOMER}/auth/login`)
  expect(JSON.parse(String(authOpts.body))).toEqual({ email: 'customer@example.test', password: 'secret123' })
  const [leaseUrl, leaseOpts] = fetchMock.mock.calls[1] as [string, RequestInit]
  expect(leaseUrl).toBe(`${CUSTOMER}/leases`)
  expect((leaseOpts.headers as Record<string, string>).Authorization).toBe('Bearer jwt.cus.token')

  const file = path.join(dir, 'account.json')
  expect(existsSync(file)).toBe(true)
  const stored = JSON.parse(readFileSync(file, 'utf8')) as {
    accessToken: string
    customerId: string
    lease: { virtualKey: string }
  }
  expect(stored.accessToken).toBe('jwt.cus.token')
  expect(stored.customerId).toBe('42')
  expect(stored.lease.virtualKey).toBe('dgw.L1.s')
  expect((await backend.state()).status).toBe('credential-stored')
})

it('signOut revokes the lease and clears the persisted account', async () => {
  const fetchMock = mockControlPlane()
  const backend = agentpanelAccountBackend(config())
  await backend.login('customer@example.test', 'secret123')

  const view = await backend.signOut(client())
  expect(view.status).toBe('signed-out')
  expect(existsSync(path.join(dir, 'account.json'))).toBe(false)
  const revoke = fetchMock.mock.calls
    .find((call) => String(call[0]).includes('/leases/L1') && (call[1] as RequestInit).method === 'DELETE')
  expect(revoke).toBeTruthy()
  expect(String(revoke![0])).toBe(`${CUSTOMER}/leases/L1`)
  expect(((revoke![1] as RequestInit).headers as Record<string, string>).Authorization).toBe('Bearer jwt.cus.token')
})

it('sends a register verification code through the customer auth endpoint', async () => {
  const fetchMock = mockControlPlane()
  const backend = agentpanelAccountBackend(config())
  const result = await backend.sendCode('new@example.test', 'register')
  expect(result.ok).toBe(true)
  const [url, opts] = fetchMock.mock.calls[0] as [string, RequestInit]
  expect(url).toBe(`${CUSTOMER}/auth/send-code`)
  expect(JSON.parse(String(opts.body))).toEqual({ email: 'new@example.test', type: 'register' })
})

it('accepts a send-code success whose payload is null', async () => {
  // agentpanel answers send-code with success_response(data=None); only `msg` is set.
  const fetchMock = vi.fn(async () => ({
    ok: true,
    json: async () => ({ code: 0, msg: '验证码已发送', data: null, status_code: 200, success: true }),
  } as Response))
  vi.stubGlobal('fetch', fetchMock)
  const backend = agentpanelAccountBackend(config())
  expect(await backend.sendCode('new@example.test', 'register')).toEqual({ ok: true })
})

it('rejects an invalid verification code before contacting the control plane', async () => {
  const fetchMock = mockControlPlane()
  const backend = agentpanelAccountBackend(config())
  const result = await backend.register('new@example.test', 'abc', 'secret123')
  expect(result.ok).toBe(false)
  expect(fetchMock).not.toHaveBeenCalled()
})

it('start without a stored JWT stays signed out instead of issuing an anonymous lease', async () => {
  const fetchMock = mockControlPlane()
  const backend = agentpanelAccountBackend(config())
  expect((await backend.start(client())).status).toBe('signed-out')
  expect(fetchMock).not.toHaveBeenCalled()
})

it('session exposes the lease snapshot for workspace import and null when signed out', async () => {
  mockControlPlane()
  const backend = agentpanelAccountBackend(config())
  expect(backend.session()).toBeNull()

  await backend.login('customer@example.test', 'secret123')
  const session = backend.session()
  expect(session).not.toBeNull()
  expect(session!.leaseId).toBe('L1')
  expect(session!.virtualKey).toBe('dgw.L1.s')
  expect(session!.expiresAtMs).toBeGreaterThan(Date.now())

  await backend.signOut(client())
  expect(backend.session()).toBeNull()
})
