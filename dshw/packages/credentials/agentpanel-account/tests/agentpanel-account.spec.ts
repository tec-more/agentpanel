/**
 * AgentPanelAccount end-to-end behavior against the agentpanel gateway lease
 * contract. `fetch` is mocked so no live gateway is required; this validates the
 * real service logic (issue / parse / resolveToken / renew scheduling / revoke),
 * not just the controller delegation.
 *
 * Topology: lease issue/renew/revoke go to the 【control-plane】 (`controlPlaneUrl`,
 * e.g. http://127.0.0.1:9998/v1/harness); `resolveToken` only returns the lease
 * key for the 【data-plane】 gateway origin (`gatewayUrl`, e.g. http://127.0.0.1:9999).
 */
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { Context } from '@deepseek-ai/cordis'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
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

const CONFIG = {
  gatewayUrl: 'http://gw.test',
  controlPlaneUrl: 'http://cp.test/v1/harness',
  clientId: 'cid',
  clientSecret: 'csec',
}

it('issues a renewable lease on the control plane and resolves the key for the data plane', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => leaseResponse() } as Response)
  vi.stubGlobal('fetch', fetchMock)
  const ctx = new Context()
  roots.push(ctx)
  const svc = new AgentPanelAccount(ctx, CONFIG)

  expect((await svc.getState()).status).toBe('signed-out')
  await svc.startSignIn(client, 'http://127.0.0.1:8080', 'web')
  await new Promise((resolve) => setTimeout(resolve, 60))

  expect((await svc.getState()).status).toBe('credential-stored')

  expect(fetchMock).toHaveBeenCalledTimes(1)
  const [url, opts] = started(...(fetchMock.mock.calls[0] as [string, RequestInit]))
  expect(String(url)).toBe('http://cp.test/v1/harness/gateway/leases')
  expect((opts.headers as Record<string, string>).authorization).toBe('Bearer cid.csec')
  expect(opts.method).toBe('POST')

  // 续约 key 仅对数据面网关（gatewayUrl）生效，不对控制面（controlPlaneUrl）。
  expect(await svc.resolveToken('http://gw.test/x')).toBe('dgw.lease-1.secret')
  expect(await svc.resolveToken('http://cp.test/x')).toBeUndefined()
  expect(await svc.resolveToken('http://other.test/x')).toBeUndefined()
})

it('stays signed-out when the gateway rejects the lease', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({}) } as Response)
  vi.stubGlobal('fetch', fetchMock)
  const ctx = new Context()
  roots.push(ctx)
  const svc = new AgentPanelAccount(ctx, CONFIG)

  await svc.startSignIn(client, 'http://127.0.0.1:8080', 'web')
  await new Promise((resolve) => setTimeout(resolve, 60))
  expect((await svc.getState()).status).toBe('signed-out')
  expect(fetchMock).toHaveBeenCalledTimes(1)
  expect(String(fetchMock.mock.calls[0]![0])).toBe('http://cp.test/v1/harness/gateway/leases')
})

it('revokes the lease on signOut via the control plane', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => leaseResponse() } as Response)
  vi.stubGlobal('fetch', fetchMock)
  const ctx = new Context()
  roots.push(ctx)
  const svc = new AgentPanelAccount(ctx, CONFIG)

  await svc.startSignIn(client, 'http://127.0.0.1:8080', 'web')
  await new Promise((resolve) => setTimeout(resolve, 60))
  expect((await svc.getState()).status).toBe('credential-stored')

  const state = await svc.signOut(client)
  expect(state.status).toBe('signed-out')

  const deleteCall = fetchMock.mock.calls
    .map((c) => started(...(c as [string, RequestInit])))
    .find(([u, o]) => String(u).includes('/gateway/leases/') && o.method === 'DELETE')
  expect(deleteCall).toBeTruthy()
  expect(String(deleteCall![0])).toBe('http://cp.test/v1/harness/gateway/leases/lease-1')
})

it('adopted desktop sessions report signed-in without contacting the control plane', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  const ctx = new Context()
  roots.push(ctx)
  const svc = new AgentPanelAccount(ctx, CONFIG)

  const state = await svc.importSession({
    leaseId: 'lease-cus',
    virtualKey: 'dgw.lease-cus.secret',
    expiresAtMs: Date.now() + 900_000,
    renewAfterSeconds: 720,
  })
  expect(state.status).toBe('credential-stored')
  expect(fetchMock).not.toHaveBeenCalled()

  // 续约 key 仅对数据面网关生效，与自签租约一致。
  expect(await svc.resolveToken('http://gw.test/x')).toBe('dgw.lease-cus.secret')
  expect(await svc.resolveToken('http://cp.test/x')).toBeUndefined()
})

it('imported leases are never self-renewed and sign-out clears them without a revoke call', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  const ctx = new Context()
  roots.push(ctx)
  const svc = new AgentPanelAccount(ctx, CONFIG)

  await svc.importSession({ leaseId: 'lease-cus', virtualKey: 'dgw.lease-cus.secret', expiresAtMs: Date.now() + 900_000 })
  // 桌面负责续期：本服务没有续期凭据，不应发出任何续期请求。
  await new Promise((resolve) => setTimeout(resolve, 60))
  expect(fetchMock).not.toHaveBeenCalled()

  const state = await svc.signOut(client)
  expect(state.status).toBe('signed-out')
  expect(fetchMock).not.toHaveBeenCalled()
})

it('clearSession drops the imported desktop session', async () => {
  const ctx = new Context()
  roots.push(ctx)
  const svc = new AgentPanelAccount(ctx, CONFIG)
  await svc.importSession({ leaseId: 'lease-cus', virtualKey: 'dgw.lease-cus.secret', expiresAtMs: Date.now() + 900_000 })
  expect((await svc.getState()).status).toBe('credential-stored')

  const state = await svc.clearSession()
  expect(state.status).toBe('signed-out')
  expect(await svc.resolveToken('http://gw.test/x')).toBeUndefined()
})

it('a gateway rejection expires the imported session', async () => {
  const ctx = new Context()
  roots.push(ctx)
  const svc = new AgentPanelAccount(ctx, CONFIG)
  await svc.importSession({ leaseId: 'lease-cus', virtualKey: 'dgw.lease-cus.secret', expiresAtMs: Date.now() + 900_000 })

  await svc.rejectToken('dgw.lease-cus.secret')
  expect((await svc.getState()).status).toBe('signed-out')
})

/** Customer email-code flow against the customer control plane. */
describe('customer sign-in', () => {
  const CUSTOMER = {
    gatewayUrl: 'http://gw.test',
    controlPlaneUrl: 'http://cp.test/v1/harness',
    customerUrl: 'http://cp.test/v1/customer',
    storageDir: undefined as string | undefined,
  }

  function authResponse(): Record<string, unknown> {
    return { success: true, data: {
      access_token: 'jwt.cus',
      expires_in: 86_400,
      customer: { id: 'cus-1', email: 'user@example.com' },
    } }
  }

  function customerLeaseResponse(): Record<string, unknown> {
    return { success: true, data: {
      lease_id: 'lease-cus',
      virtual_key: 'dgw.lease-cus.secret',
      expires_at: new Date(Date.now() + 900_000).toISOString(),
      ttl_seconds: 900,
    } }
  }

  function route(handlers: Record<string, () => Record<string, unknown> | { status: number }>): ReturnType<typeof vi.fn> {
    return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = init?.method ?? 'GET'
      const handler = handlers[`${method} ${url}`]
      if (handler === undefined) return { ok: false, status: 404, json: async () => ({}) } as Response
      const payload = handler()
      if ('status' in payload) return { ok: false, status: payload.status, json: async () => payload } as Response
      return { ok: true, json: async () => payload } as Response
    })
  }

  it('reports browser mode without customerUrl and customer mode with it', async () => {
    const browserCtx = new Context()
    roots.push(browserCtx)
    expect(await new AgentPanelAccount(browserCtx, CONFIG).getAuthMode()).toBe('browser')

    const customerCtx = new Context()
    roots.push(customerCtx)
    expect(await new AgentPanelAccount(customerCtx, { ...CONFIG, customerUrl: 'http://cp.test/v1/customer' }).getAuthMode()).toBe('customer')
  })

  it('password login exchanges the JWT for a lease and persists the shared session', async () => {
    CUSTOMER.storageDir = mkdtempSync(join(tmpdir(), 'agentpanel-account-'))
    const fetchMock = route({
      'POST http://cp.test/v1/customer/auth/login': authResponse,
      'POST http://cp.test/v1/customer/leases': customerLeaseResponse,
    })
    vi.stubGlobal('fetch', fetchMock)
    const ctx = new Context()
    roots.push(ctx)
    const svc = new AgentPanelAccount(ctx, { ...CUSTOMER })

    expect((await svc.getAuthMode())).toBe('customer')
    const outcome = await svc.login('user@example.com', 'secret123')
    expect(outcome.ok).toBe(true)
    expect(outcome.state?.status).toBe('credential-stored')
    expect((await svc.getState()).status).toBe('credential-stored')
    // 客户租约同样只对数据面网关注入。
    expect(await svc.resolveToken('http://gw.test/x')).toBe('dgw.lease-cus.secret')
    expect(await svc.resolveToken('http://cp.test/x')).toBeUndefined()

    const [loginUrl, loginInit] = started(...(fetchMock.mock.calls[0]! as [string, RequestInit]))
    expect(loginUrl).toBe('http://cp.test/v1/customer/auth/login')
    expect(JSON.parse(String(loginInit.body))).toEqual({ email: 'user@example.com', password: 'secret123' })
    const [leaseUrl, leaseInit] = started(...(fetchMock.mock.calls[1]! as [string, RequestInit]))
    expect(leaseUrl).toBe('http://cp.test/v1/customer/leases')
    expect((leaseInit.headers as Record<string, string>).authorization).toBe('Bearer jwt.cus')

    // 持久化与桌面 account.json 同构，双端共享一个会话。
    const stored = JSON.parse(readFileSync(join(CUSTOMER.storageDir, 'account.json'), 'utf8')) as Record<string, unknown>
    expect(stored.accessToken).toBe('jwt.cus')
    expect(stored.customerEmail).toBe('user@example.com')
    expect((stored.lease as Record<string, unknown>).virtualKey).toBe('dgw.lease-cus.secret')

    const state = await svc.signOut(client)
    expect(state.status).toBe('signed-out')
    const revoke = fetchMock.mock.calls
      .map((c) => started(...(c as [string, RequestInit])))
      .find(([u, o]) => String(u) === 'http://cp.test/v1/customer/leases/lease-cus' && o.method === 'DELETE')
    expect(revoke).toBeTruthy()
    expect(existsSync(join(CUSTOMER.storageDir, 'account.json'))).toBe(false)
  })

  it('surface control-plane messages as user-facing login failures', async () => {
    CUSTOMER.storageDir = mkdtempSync(join(tmpdir(), 'agentpanel-account-'))
    const fetchMock = route({
      'POST http://cp.test/v1/customer/auth/login': () => ({ success: false, msg: '密码错误' }),
    })
    vi.stubGlobal('fetch', fetchMock)
    const ctx = new Context()
    roots.push(ctx)
    const svc = new AgentPanelAccount(ctx, { ...CUSTOMER })

    const outcome = await svc.login('user@example.com', 'wrong')
    expect(outcome.ok).toBe(false)
    expect(outcome.message).toBe('密码错误')
    expect((await svc.getState()).status).toBe('signed-out')
  })

  it('validates inputs locally before calling the control plane', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const ctx = new Context()
    roots.push(ctx)
    const svc = new AgentPanelAccount(ctx, { ...CUSTOMER, storageDir: mkdtempSync(join(tmpdir(), 'agentpanel-account-')) })

    expect((await svc.sendCode('not-an-email', 'login')).message).toContain('邮箱')
    expect((await svc.loginCode('user@example.com', '12ab')).message).toContain('6 位')
    expect((await svc.register('user@example.com', '123456', '123')).message).toContain('6 位')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('adopted shared-store sessions sign in without any control-plane call', async () => {
    CUSTOMER.storageDir = mkdtempSync(join(tmpdir(), 'agentpanel-account-'))
    const file = join(CUSTOMER.storageDir, 'account.json')
    mkdirSync(CUSTOMER.storageDir, { recursive: true })
    writeFileSync(file, JSON.stringify({
      accessToken: 'jwt.cus',
      tokenExpiresAt: new Date(Date.now() + 3_600_000).toISOString(),
      customerId: 'cus-1',
      customerEmail: 'user@example.com',
      lease: { leaseId: 'lease-cus', virtualKey: 'dgw.lease-cus.secret', expiresAt: new Date(Date.now() + 900_000).toISOString(), ttlSeconds: 900 },
    }))
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const ctx = new Context()
    roots.push(ctx)
    const svc = new AgentPanelAccount(ctx, { ...CUSTOMER })

    expect((await svc.getState()).status).toBe('credential-stored')
    expect(await svc.resolveToken('http://gw.test/x')).toBe('dgw.lease-cus.secret')
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
