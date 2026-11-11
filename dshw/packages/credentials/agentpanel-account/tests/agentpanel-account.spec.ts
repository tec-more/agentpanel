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
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { Context } from '@deepseek-ai/cordis'
import { afterEach, beforeEach, describe, expect, it, onTestFinished, vi } from 'vitest'
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

it('reports the deployment brand in account state', async () => {
  const ctx = new Context()
  roots.push(ctx)
  const svc = new AgentPanelAccount(ctx, { ...CONFIG, brandName: '  AgentPanel  ' })
  const state = await svc.getState()
  expect(state.status).toBe('signed-out')
  expect(state.brandName).toBe('AgentPanel')
})

it('reads the customer account name and remaining hours for the account card', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'ap-profile-'))
  onTestFinished(() => { rmSync(dir, { recursive: true, force: true }) })
  const expiresAt = new Date(Date.now() + 600_000).toISOString()
  writeFileSync(join(dir, 'account.json'), JSON.stringify({
    accessToken: 'jwt.customer.token', tokenExpiresAt: expiresAt, customerId: '42',
    customerEmail: 'user@example.com',
    lease: { leaseId: 'L1', virtualKey: 'dgw.L1.s', expiresAt, ttlSeconds: 900 },
  }))
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      success: true,
      data: { id: 42, email: 'user@example.com', nickname: 'Alice', username: 'alice', remaining_hours: 12.5 },
    }),
  } as Response)
  vi.stubGlobal('fetch', fetchMock)
  const ctx = new Context()
  roots.push(ctx)
  const svc = new AgentPanelAccount(ctx, {
    ...CONFIG, customerUrl: 'http://cp.test/v1/customer', storageDir: dir, brandName: 'AgentPanel',
  })
  expect((await svc.getState()).brandName).toBe('AgentPanel')
  expect(await svc.getProfile(client)).toEqual({
    status: 'ready',
    value: { id: null, name: 'Alice', contact: 'user@example.com', remainingHours: '12.5' },
  })
  const [url, init] = started(...(fetchMock.mock.calls[0] as [string, RequestInit]))
  expect(url).toBe('http://cp.test/v1/customer/auth/me')
  expect(init.method).toBe('GET')
  expect((init.headers as Record<string, string>).authorization).toBe('Bearer jwt.customer.token')
  // The refreshed identity is persisted for later launches.
  const stored = JSON.parse(readFileSync(join(dir, 'account.json'), 'utf8')) as Record<string, unknown>
  expect(stored.customerName).toBe('Alice')
  expect(stored.remainingHours).toBe('12.5')
  // A repeated read keeps the stored values and still reports them.
  expect(await svc.getProfile(client)).toEqual({
    status: 'ready',
    value: { id: null, name: 'Alice', contact: 'user@example.com', remainingHours: '12.5' },
  })
  expect(fetchMock).toHaveBeenCalledTimes(2)
})

it('keeps the persisted identity when the business profile read fails', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'ap-profile-'))
  onTestFinished(() => { rmSync(dir, { recursive: true, force: true }) })
  const expiresAt = new Date(Date.now() + 600_000).toISOString()
  writeFileSync(join(dir, 'account.json'), JSON.stringify({
    accessToken: 'jwt.customer.token', tokenExpiresAt: expiresAt, customerId: '42',
    customerEmail: 'user@example.com', customerName: 'Stored Name', remainingHours: '3.25',
    lease: { leaseId: 'L1', virtualKey: 'dgw.L1.s', expiresAt, ttlSeconds: 900 },
  }))
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
  const ctx = new Context()
  roots.push(ctx)
  const svc = new AgentPanelAccount(ctx, {
    ...CONFIG, customerUrl: 'http://cp.test/v1/customer', storageDir: dir,
  })
  expect(await svc.getProfile(client)).toEqual({
    status: 'ready',
    value: { id: null, name: 'Stored Name', contact: 'user@example.com', remainingHours: '3.25' },
  })
})

it('falls back to the username and omits fields the business service does not return', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'ap-profile-'))
  onTestFinished(() => { rmSync(dir, { recursive: true, force: true }) })
  const expiresAt = new Date(Date.now() + 600_000).toISOString()
  writeFileSync(join(dir, 'account.json'), JSON.stringify({
    accessToken: 'jwt.customer.token', tokenExpiresAt: expiresAt, customerId: '42',
    customerEmail: 'user@example.com',
    lease: { leaseId: 'L1', virtualKey: 'dgw.L1.s', expiresAt, ttlSeconds: 900 },
  }))
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ success: true, data: { username: 'alice' } }),
  } as Response)
  vi.stubGlobal('fetch', fetchMock)
  const ctx = new Context()
  roots.push(ctx)
  const svc = new AgentPanelAccount(ctx, {
    ...CONFIG, customerUrl: 'http://cp.test/v1/customer', storageDir: dir,
  })
  expect(await svc.getProfile(client)).toEqual({
    status: 'ready',
    value: { id: null, name: 'alice', contact: 'user@example.com' },
  })
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

it('an imported desktop lease reads the shared customer identity without owning renewal', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'ap-import-profile-'))
  onTestFinished(() => { rmSync(dir, { recursive: true, force: true }) })
  const leaseExpiresAt = new Date(Date.now() + 900_000).toISOString()
  writeFileSync(join(dir, 'account.json'), JSON.stringify({
    accessToken: 'jwt.customer.token',
    tokenExpiresAt: new Date(Date.now() + 3_600_000).toISOString(),
    customerId: '42', customerEmail: 'user@example.com', customerName: 'Alice', remainingHours: '3',
    lease: { leaseId: 'lease-cus', virtualKey: 'dgw.lease-cus.secret', expiresAt: leaseExpiresAt, ttlSeconds: 900 },
  }))
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      success: true,
      data: { nickname: 'Alice', email: 'user@example.com', remaining_hours: 2.5 },
    }),
  } as Response)
  vi.stubGlobal('fetch', fetchMock)
  const ctx = new Context()
  roots.push(ctx)
  const svc = new AgentPanelAccount(ctx, {
    ...CONFIG, customerUrl: 'http://cp.test/v1/customer', storageDir: dir,
  })

  // 桌面端把同一张租约镜像进来；本进程只读取业务端资料，不负责续期/吊销。
  await svc.importSession({ leaseId: 'lease-cus', virtualKey: 'dgw.lease-cus.secret', expiresAtMs: Date.now() + 900_000 })
  expect(await svc.getProfile(client)).toEqual({
    status: 'ready',
    value: { id: null, name: 'Alice', contact: 'user@example.com', remainingHours: '2.5' },
  })
  expect(fetchMock.mock.calls.map(call => String(call[0])))
    .toEqual(['http://cp.test/v1/customer/auth/me'])

  await svc.signOut(client)
  // 桌面拥有吊销；本进程退出登录不发出任何请求。
  expect(fetchMock).toHaveBeenCalledTimes(1)
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
      customer: { id: 'cus-1', email: 'user@example.com', nickname: 'Alice', username: 'alice', remaining_hours: 7.5 },
    } }
  }

  function customerProfileResponse(): Record<string, unknown> {
    return { success: true, data: {
      id: 'cus-1', email: 'user@example.com', nickname: 'Alice', username: 'alice', remaining_hours: 6.25,
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
      'GET http://cp.test/v1/customer/auth/me': customerProfileResponse,
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
    // 账号名与余量来自业务端；读取后余量随业务数据更新。
    expect(await svc.getProfile(client)).toEqual({
      status: 'ready',
      value: { id: null, name: 'Alice', contact: 'user@example.com', remainingHours: '6.25' },
    })

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
    expect(stored.customerName).toBe('Alice')
    expect(stored.remainingHours).toBe('6.25')
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

  it('accepts a control-plane success whose payload is null', async () => {
    CUSTOMER.storageDir = mkdtempSync(join(tmpdir(), 'agentpanel-account-'))
    const fetchMock = route({
      'POST http://cp.test/v1/customer/auth/send-code': () => ({ success: true, data: null, msg: '验证码已发送' }),
    })
    vi.stubGlobal('fetch', fetchMock)
    const ctx = new Context()
    roots.push(ctx)
    const svc = new AgentPanelAccount(ctx, { ...CUSTOMER })

    expect(await svc.sendCode('user@example.com', 'register')).toEqual({ ok: true, message: '' })
  })

  it('resets a password through the customer control plane', async () => {
    CUSTOMER.storageDir = mkdtempSync(join(tmpdir(), 'agentpanel-account-'))
    const fetchMock = route({
      'POST http://cp.test/v1/customer/auth/reset-password': () => ({ success: true, data: null, msg: '密码重置成功' }),
    })
    vi.stubGlobal('fetch', fetchMock)
    const ctx = new Context()
    roots.push(ctx)
    const svc = new AgentPanelAccount(ctx, { ...CUSTOMER })

    expect(await svc.resetPassword('user@example.com', '123456', 'secret123')).toEqual({ ok: true, message: '' })
    const [url, init] = started(...(fetchMock.mock.calls[0]! as [string, RequestInit]))
    expect(url).toBe('http://cp.test/v1/customer/auth/reset-password')
    expect(JSON.parse(String(init.body))).toEqual({
      email: 'user@example.com', code: '123456', new_password: 'secret123',
    })
  })

  it('validates reset inputs locally and surfaces control-plane failures', async () => {
    const fetchMock = route({
      'POST http://cp.test/v1/customer/auth/reset-password': () => ({ success: false, msg: '验证码错误或已过期' }),
    })
    vi.stubGlobal('fetch', fetchMock)
    const ctx = new Context()
    roots.push(ctx)
    const svc = new AgentPanelAccount(ctx, { ...CUSTOMER })

    expect((await svc.resetPassword('not-an-email', '123456', 'secret123')).message).toContain('邮箱')
    expect((await svc.resetPassword('user@example.com', '12ab', 'secret123')).message).toContain('6 位')
    expect((await svc.resetPassword('user@example.com', '123456', '123')).message).toContain('6 位')
    expect(fetchMock).not.toHaveBeenCalled()
    expect(await svc.resetPassword('user@example.com', '123456', 'secret123'))
      .toEqual({ ok: false, message: '验证码错误或已过期' })
    const browserCtx = new Context()
    roots.push(browserCtx)
    expect((await new AgentPanelAccount(browserCtx, CONFIG).resetPassword('user@example.com', '123456', 'secret123')).message)
      .toContain('not configured')
  })

  it('reports a withdrawn password reset as a user-facing failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    const ctx = new Context()
    roots.push(ctx)
    const svc = new AgentPanelAccount(ctx, {
      ...CUSTOMER, storageDir: mkdtempSync(join(tmpdir(), 'agentpanel-account-')),
    })
    expect(await svc.resetPassword('user@example.com', '123456', 'secret123'))
      .toEqual({ ok: false, message: 'offline' })
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
