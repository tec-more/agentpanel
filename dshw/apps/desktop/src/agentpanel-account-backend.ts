/**
 * agentpanel 客户账号后端（customer 主体 + 邮箱验证码注册）
 *
 * 认证链路：
 * - 注册：POST /v1/customer/auth/send-code(type=register) → POST /v1/customer/auth/register(email, code, password)
 * - 登录：POST /v1/customer/auth/login(email, password)（另提供 login-code 邮箱验证码登录）
 * - 以上端点返回 `typ=cus` 的 JWT；控制面另提供 POST /v1/customer/leases，
 *   用该 JWT 换一张绑定 owner_type=cus / owner_id=customer.id 的租约虚拟 key。
 *
 * 为什么需要换租约：agentpanel 网关【数据面】只接受 `dgw.<lease_id>.<secret>`，
 * 明确拒绝 JWT；业务接口又拒绝 `dgw.*`（双向隔离）。因此桌面端持有 JWT 作为登录态，
 * 同时持有租约作为网关调用凭证，两者都写入 account.json（0o600）。
 *
 * 配置（由桌面启动进程通过环境变量注入）：
 * - AGENTPANEL_CUSTOMER_URL   控制面客户体系基址，默认 http://127.0.0.1:9998/v1/customer
 * - AGENTPANEL_GATEWAY_URL    网关数据面基址，默认 http://127.0.0.1:9999
 * - AGENTPANEL_ACCOUNT_STORE_DIR  账号持久化目录
 * - AGENTPANEL_USAGE_URL / AGENTPANEL_TOPUP_URL  账号中心/充值页（仅展示）
 * - AGENTPANEL_RENEW_RATIO / AGENTPANEL_RENEW_CHECK_MS  租约自动续期参数
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync, rmSync } from 'node:fs'
import { homedir } from 'node:os'
import path from 'node:path'
import type { AccountClientMetadata, AccountView, SignInAttemptId } from '@deepseek-ai/dsh-deepseek-account/types'
import type { CustomerAuthOutcome, CustomerCodeOutcome } from './welcome-api.ts'

/** Native account operations; mirrors the contract the desktop UI expects. */
export interface DesktopAccountBackend {
  state(): Promise<AccountView>
  start(client: AccountClientMetadata): Promise<AccountView>
  cancel(id: SignInAttemptId): Promise<AccountView>
  signOut(client: AccountClientMetadata): Promise<AccountView>
  watch(
    listener: (state: AccountView) => void,
    failed: () => void,
    expired: () => void,
    onAnalyticsEnabledChanged?: (enabled: boolean) => void,
  ): () => void
}

export interface AgentpanelAccountConfig {
  /** 网关【数据面】基址（仅该 origin 会被注入租约 key）。默认 http://127.0.0.1:9999 */
  gatewayUrl: string
  /** 控制面客户体系基址（认证 + 账号租约）。默认 http://127.0.0.1:9998/v1/customer */
  customerUrl?: string | undefined
  storageDir?: string | undefined
  usageUrl?: string | undefined
  topUpUrl?: string | undefined
  renewRatio?: number | undefined
  renewCheckMs?: number | undefined
}

/** 租约快照，供导入工作区 Host 的账号服务（desktop 负责续期与吊销）。 */
export interface ImportedSession {
  leaseId: string
  virtualKey: string
  /** 租约过期时间（epoch 毫秒）。 */
  expiresAtMs: number
}

/** 欢迎页可调用的客户账号操作，超出 DesktopAccountBackend 的部分。 */
export interface CustomerAccountOperations {
  /** @param email - 待验证邮箱。 @param purpose - 验证码用途。 */
  sendCode(email: string, purpose: 'register' | 'login' | 'reset_password'): Promise<CustomerCodeOutcome>
  /** @returns 注册成功后的账号状态。 */
  register(email: string, code: string, password: string): Promise<CustomerAuthOutcome>
  /** @returns 密码登录成功后的账号状态。 */
  login(email: string, password: string): Promise<CustomerAuthOutcome>
  /** @returns 邮箱验证码登录成功后的账号状态。 */
  loginCode(email: string, code: string): Promise<CustomerAuthOutcome>
  /** @returns 当前有效租约快照；未登录或已过期时为 null。 */
  session(): ImportedSession | null
}

export type CustomerAccountBackend = DesktopAccountBackend & CustomerAccountOperations

interface StoredLease {
  leaseId: string
  virtualKey: string
  expiresAt: string
  ttlSeconds: number
}

interface StoredAccount {
  accessToken: string
  tokenExpiresAt: string
  customerId: string
  customerEmail: string
  lease: StoredLease | null
}

const AUTH = '/auth'
const LEASES = '/leases'
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function base(url: string): string {
  return url.replace(/\/+$/, '')
}

function customerBase(config: AgentpanelAccountConfig): string {
  return base(config.customerUrl ?? 'http://127.0.0.1:9998/v1/customer')
}

function linksOf(config: AgentpanelAccountConfig): { usageUrl: string; topUpUrl: string } {
  const b = customerBase(config)
  return {
    usageUrl: config.usageUrl ?? `${b}/account/usage`,
    topUpUrl: config.topUpUrl ?? `${b}/account/top-up`,
  }
}

function signedOut(config: AgentpanelAccountConfig): AccountView {
  return { status: 'signed-out', links: linksOf(config), attempt: null }
}

/**
 * 登录完成态：main.ts 依赖 `attempt.phase === 'succeeded'` 才会打开工作区，
 * 因此必须返回真实的 succeeded 快照，而不是 null。
 */
function credentialStored(config: AgentpanelAccountConfig): AccountView {
  return {
    status: 'credential-stored',
    links: linksOf(config),
    attempt: { id: 'agentpanel-customer' as SignInAttemptId, phase: 'succeeded' },
  }
}

function resolveStorageFile(config: AgentpanelAccountConfig): string {
  const dir =
    config.storageDir ??
    (process.env.APPDATA
      ? path.join(process.env.APPDATA, 'dsh-agentpanel')
      : path.join(homedir(), '.config', 'dsh-agentpanel'))
  return path.join(dir, 'account.json')
}

function expired(value: string | undefined): boolean {
  if (!value) return true
  const time = new Date(value).getTime()
  return !Number.isFinite(time) || time <= Date.now()
}

/** Pull the payload out of agentpanel's `success_response` envelope (or a bare object). */
function envelopeData(body: unknown): Record<string, unknown> {
  const source = body && typeof body === 'object' && 'data' in body
    ? (body as Record<string, unknown>).data
    : body
  if (!source || typeof source !== 'object' || Array.isArray(source)) {
    throw new Error('agentpanel account: 响应格式无效')
  }
  return source as Record<string, unknown>
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message.slice(0, 200) : '操作失败，请重试'
}

/**
 * Connect native account operations to the agentpanel customer control plane.
 * @param config - customer control-plane base URL and storage/renewal options.
 * @returns account operations with email-code registration and automatic lease renewal.
 */
export function agentpanelAccountBackend(config: AgentpanelAccountConfig): CustomerAccountBackend {
  const storageFile = resolveStorageFile(config)
  const renewRatio = config.renewRatio ?? 0.8
  const renewCheckMs = config.renewCheckMs ?? 30_000
  const listeners = new Set<(state: AccountView) => void>()
  let renewTimer: ReturnType<typeof setInterval> | undefined
  let current: StoredAccount | null = readStored()

  function readStored(): StoredAccount | null {
    try {
      if (!existsSync(storageFile)) return null
      const parsed = JSON.parse(readFileSync(storageFile, 'utf8')) as StoredAccount
      if (typeof parsed.accessToken !== 'string' || parsed.accessToken === '') return null
      if (expired(parsed.tokenExpiresAt)) return null
      return parsed
    } catch {
      return null
    }
  }

  function persist(account: StoredAccount | null): void {
    current = account
    try {
      const dir = path.dirname(storageFile)
      if (!existsSync(dir)) mkdirSync(dir, { recursive: true })
      if (account) writeFileSync(storageFile, JSON.stringify(account), { mode: 0o600 })
      else if (existsSync(storageFile)) rmSync(storageFile)
    } catch {
      // 持久化失败不阻断本次登录态；下次启动会要求重新登录。
    }
  }

  function view(): AccountView {
    const account = current
    if (!account || expired(account.tokenExpiresAt) || !account.lease || expired(account.lease.expiresAt)) {
      return signedOut(config)
    }
    return credentialStored(config)
  }

  function emit(state: AccountView): void {
    for (const listener of listeners) listener(state)
  }

  async function request(endpoint: string, body: Record<string, unknown>, token?: string): Promise<Record<string, unknown>> {
    const headers: Record<string, string> = { 'content-type': 'application/json' }
    if (token !== undefined) headers.Authorization = `Bearer ${token}`
    const res = await fetch(`${customerBase(config)}${endpoint}`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    })
    let payload: unknown
    try { payload = await res.json() } catch { throw new Error(`agentpanel account: 服务响应无效 (${res.status})`) }
    const envelope = payload && typeof payload === 'object' ? payload as Record<string, unknown> : {}
    if (!res.ok || envelope.success === false) {
      const detail = typeof envelope.msg === 'string' && envelope.msg !== '' ? envelope.msg : `请求失败 (${res.status})`
      throw new Error(detail)
    }
    return envelopeData(payload)
  }

  async function issueLease(account: StoredAccount): Promise<StoredLease> {
    const data = await request(LEASES, {}, account.accessToken)
    if (typeof data.lease_id !== 'string' || typeof data.virtual_key !== 'string') {
      throw new Error('agentpanel account: 租约响应缺少字段')
    }
    const expiresAt = typeof data.expires_at === 'string' ? data.expires_at : ''
    if (expired(expiresAt)) throw new Error('agentpanel account: 租约已过期')
    return {
      leaseId: data.lease_id,
      virtualKey: data.virtual_key,
      expiresAt,
      ttlSeconds: typeof data.ttl_seconds === 'number' ? data.ttl_seconds : 900,
    }
  }

  async function renewLease(account: StoredAccount, lease: StoredLease): Promise<StoredLease> {
    const data = await request(`${LEASES}/${encodeURIComponent(lease.leaseId)}/renew`, {}, account.accessToken)
    const expiresAt = typeof data.expires_at === 'string' ? data.expires_at : ''
    if (expired(expiresAt)) throw new Error('agentpanel account: 续期响应缺少有效过期时间')
    return { ...lease, expiresAt, ttlSeconds: typeof data.ttl_seconds === 'number' ? data.ttl_seconds : lease.ttlSeconds }
  }

  async function revokeLease(account: StoredAccount, lease: StoredLease): Promise<void> {
    const res = await fetch(`${customerBase(config)}${LEASES}/${encodeURIComponent(lease.leaseId)}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${account.accessToken}` },
    })
    if (!res.ok) throw new Error('agentpanel account: 租约吊销失败')
  }

  function validateEmail(email: string): string | null {
    return EMAIL_PATTERN.test(email.trim()) && email.length <= 254 ? email.trim() : null
  }

  async function authenticate(
    endpoint: string,
    body: Record<string, unknown>,
    email: string,
  ): Promise<CustomerAuthOutcome> {
    try {
      const data = await request(`${AUTH}${endpoint}`, body)
      const accessToken = data.access_token
      if (typeof accessToken !== 'string' || accessToken === '') throw new Error('登录态无效，请重试')
      const expiresIn = typeof data.expires_in === 'number' && data.expires_in > 0 ? data.expires_in : 86_400
      const customer = data.customer && typeof data.customer === 'object'
        ? data.customer as Record<string, unknown> : {}
      const account: StoredAccount = {
        accessToken,
        tokenExpiresAt: new Date(Date.now() + expiresIn * 1000).toISOString(),
        customerId: String(customer.id ?? ''),
        customerEmail: typeof customer.email === 'string' ? customer.email : email,
        lease: null,
      }
      persist(account)
      account.lease = await issueLease(account)
      persist(account)
      ensureRenewLoop(() => {})
      const state = credentialStored(config)
      emit(state)
      return { ok: true, state }
    } catch (error) {
      // 认证成功但换租约失败：保留 JWT 供重试，避免用户重新走一遍邮箱验证。
      return { ok: false, message: messageOf(error) }
    }
  }

  function stopRenew(): void {
    if (renewTimer) {
      clearInterval(renewTimer)
      renewTimer = undefined
    }
  }

  function ensureRenewLoop(onExpired: () => void): void {
    if (renewTimer) return
    renewTimer = setInterval(() => {
      const account = current
      if (!account?.lease) return
      const ttlMs = (account.lease.ttlSeconds || 900) * 1000
      if (new Date(account.lease.expiresAt).getTime() - Date.now() > ttlMs * renewRatio) return
      void renewLease(account, account.lease).then((lease) => {
        account.lease = lease
        persist(account)
      }).catch(() => {
        if (expired(account.lease?.expiresAt)) {
          persist(null)
          emit(signedOut(config))
          onExpired()
        }
      })
    }, renewCheckMs)
    if (typeof renewTimer.unref === 'function') renewTimer.unref()
  }

  return {
    async state() {
      current = readStored()
      return view()
    },
    session() {
      const lease = current?.lease
      if (!lease || expired(lease.expiresAt)) return null
      const expiresAtMs = new Date(lease.expiresAt).getTime()
      if (!Number.isFinite(expiresAtMs)) return null
      return { leaseId: lease.leaseId, virtualKey: lease.virtualKey, expiresAtMs }
    },
    async start(_client) {
      const account = readStored()
      if (!account) { persist(null); return signedOut(config) }
      try {
        account.lease = await issueLease(account)
        persist(account)
        ensureRenewLoop(() => {})
        const state = credentialStored(config)
        emit(state)
        return state
      } catch {
        return signedOut(config)
      }
    },
    async cancel(_id) {
      current = readStored()
      return view()
    },
    async signOut(_client) {
      const account = readStored()
      if (account?.lease) await revokeLease(account, account.lease).catch(() => undefined)
      persist(null)
      stopRenew()
      const state = signedOut(config)
      emit(state)
      return state
    },
    async sendCode(emailInput, purpose) {
      const email = validateEmail(emailInput)
      if (!email) return { ok: false, message: '请输入有效的邮箱地址' }
      try {
        await request(`${AUTH}/send-code`, { email, type: purpose })
        return { ok: true }
      } catch (error) {
        return { ok: false, message: messageOf(error) }
      }
    },
    register(emailInput, code, password) {
      const email = validateEmail(emailInput)
      if (!email) return Promise.resolve({ ok: false, message: '请输入有效的邮箱地址' })
      if (!/^\d{6}$/.test(code.trim())) return Promise.resolve({ ok: false, message: '请输入 6 位邮箱验证码' })
      if (password.length < 6) return Promise.resolve({ ok: false, message: '密码至少需要 6 位' })
      return authenticate('/register', { email, code: code.trim(), password }, email)
    },
    login(emailInput, password) {
      const email = validateEmail(emailInput)
      if (!email) return Promise.resolve({ ok: false, message: '请输入有效的邮箱地址' })
      if (password === '') return Promise.resolve({ ok: false, message: '请输入密码' })
      return authenticate('/login', { email, password }, email)
    },
    loginCode(emailInput, code) {
      const email = validateEmail(emailInput)
      if (!email) return Promise.resolve({ ok: false, message: '请输入有效的邮箱地址' })
      if (!/^\d{6}$/.test(code.trim())) return Promise.resolve({ ok: false, message: '请输入 6 位邮箱验证码' })
      return authenticate('/login-code', { email, code: code.trim() }, email)
    },
    watch(listener, _failed, expiredCallback, onAnalyticsEnabledChanged) {
      listeners.add(listener)
      onAnalyticsEnabledChanged?.(false)
      listener(view())
      const timer = setInterval(() => {
        const before = view().status
        current = readStored()
        // A sign-in written by another surface (for example the workspace web UI
        // through the shared store) adopts renewal here, so the lease survives
        // even though this process never ran its own sign-in flow.
        if (current?.lease && !renewTimer) ensureRenewLoop(expiredCallback)
        const after = view()
        if (after.status !== before) emit(after)
        if (after.status === 'signed-out' && before === 'credential-stored') expiredCallback()
      }, renewCheckMs)
      if (typeof timer.unref === 'function') timer.unref()
      return () => { listeners.delete(listener); clearInterval(timer) }
    },
  }
}
