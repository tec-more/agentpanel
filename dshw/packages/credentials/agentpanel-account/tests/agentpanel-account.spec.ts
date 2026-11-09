/**
 * AgentPanelAccount end-to-end behavior against the agentpanel gateway lease
 * contract. `fetch` is mocked so no live gateway is required; this validates the
 * real service logic (issue / parse / resolveToken / renew scheduling / revoke),
 * not just the controller delegation.
 */
import { Context } from '@deepseek-ai/cordis'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { AgentPanelAccount } from '../src/index.ts'

interface LeaseArgs {
  leaseId?: string
  virtualKey?: string
  expiresAt?: string
  ttl?: number
  renewAfter?: number
}

function leaseResponse(args: LeaseArgs = {}): Record<string, unknown> {
  const leaseId = args.leaseId ?? 'lease-1'
  const virtualKey = args.virtualKey ?? 'dgw.lease-1.secret'
  const expiresAt = args.expiresAt ?? new Date(Date.now() + 900_000).toISOString()
  const ttl = args.ttl ?? 900
  const renewAfter = args.renewAfter ?? 720
  return {
    code: 0,
    msg: 'ok',
    data: { lease_id: leaseId, virtual_key: virtualKey, expires_at: expiresAt, ttl_seconds: ttl, renew_after_seconds: renewAfter },
    status_code: 200,
    success: true,
  }
}

const client = { version: '0.0.0-test', locale: 'en-US', timezoneOffsetSeconds: 0 }
const roots: Context[] = []

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn())
})
afterEach(async () => {
  await Promise.all(roots.splice(0).map((ctx) => ctx.fiber.dispose()))
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function started(url: string, opts: RequestInit): [string, RequestInit] {
  return [url, opts]
}

it('issues a renewable lease and reports credential-stored state', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => leaseResponse() } as Response)
  vi.stubGlobal('fetch', fetchMock)
  const ctx = new Context()
  roots.push(ctx)
  const svc = new AgentPanelAccount(ctx, { gatewayUrl: 'http://gw.test', clientId: 'cid', clientSecret: 'csec' })

  expect((await svc.getState()).status).toBe('signed-out')
  await svc.startSignIn(client, 'http://127.0.0.1:8080', 'web')
  await new Promise((resolve) => setTimeout(resolve, 60))

  expect((await svc.getState()).status).toBe('credential-stored')

  expect(fetchMock).toHaveBeenCalledTimes(1)
  const [url, opts] = started(...(fetchMock.mock.calls[0] as [string, RequestInit]))
  expect(String(url)).toContain('/gateway/leases')
  expect((opts.headers as Record<string, string>).authorization).toBe('Bearer cid.csec')
  expect(opts.method).toBe('POST')

  expect(await svc.resolveToken('http://gw.test/x')).toBe('dgw.lease-1.secret')
  expect(await svc.resolveToken('http://other.test/x')).toBeUndefined()
})

it('stays signed-out when the gateway rejects the lease', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({}) } as Response)
  vi.stubGlobal('fetch', fetchMock)
  const ctx = new Context()
  roots.push(ctx)
  const svc = new AgentPanelAccount(ctx, { gatewayUrl: 'http://gw.test', clientId: 'cid', clientSecret: 'csec' })

  await svc.startSignIn(client, 'http://127.0.0.1:8080', 'web')
  await new Promise((resolve) => setTimeout(resolve, 60))
  expect((await svc.getState()).status).toBe('signed-out')
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

it('revokes the lease on signOut', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => leaseResponse() } as Response)
  vi.stubGlobal('fetch', fetchMock)
  const ctx = new Context()
  roots.push(ctx)
  const svc = new AgentPanelAccount(ctx, { gatewayUrl: 'http://gw.test', clientId: 'cid', clientSecret: 'csec' })

  await svc.startSignIn(client, 'http://127.0.0.1:8080', 'web')
  await new Promise((resolve) => setTimeout(resolve, 60))
  expect((await svc.getState()).status).toBe('credential-stored')

  const state = await svc.signOut(client)
  expect(state.status).toBe('signed-out')

  const deleteCall = fetchMock.mock.calls
    .map((c) => started(...(c as [string, RequestInit])))
    .find(([u, o]) => String(u).includes('/gateway/leases/') && o.method === 'DELETE')
  expect(deleteCall).toBeTruthy()
  expect(String(deleteCall![0])).toContain('/gateway/leases/lease-1')
})
