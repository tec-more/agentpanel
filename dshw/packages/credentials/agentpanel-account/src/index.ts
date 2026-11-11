/**
 * agentpanel account backend for dshw.
 *
 * Replaces the DeepSeek Platform account with agentpanel's gateway lease. Sign-in
 * issues a renewable virtual key (`dgw.<lease_id>.<secret>`, the "续约key") through
 * Harness client credentials, and the controller uses that key as the session
 * credential. The lease auto-renews before expiry; the gateway origin resolves the
 * key through `resolveToken`. Platform-only features (profile, balance, bonuses)
 * have no agentpanel equivalent and return null.
 */
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { homedir } from 'node:os'
import path from 'node:path'
import { randomUUID } from 'node:crypto'
import { platform, release } from 'node:os'
import { Context, Service } from '@deepseek-ai/cordis'
import type { CustomerAuthOutcome, CustomerCodeOutcome, CustomerCodePurpose, ImportedLeaseSession } from './types.ts'
import type {
  AccountBonusBatch,
  AccountBonusOrderId,
  AccountClientMetadata,
  AccountDetails,
  AccountUserId,
  AccountView,
  SignInAttemptId,
  SignInAttemptView,
} from '@deepseek-ai/dsh-deepseek-account/types'

export type { CustomerAuthOutcome, CustomerCodeOutcome, CustomerCodePurpose, ImportedLeaseSession } from './types.ts'

/** Deployment options for the agentpanel account backend. */
export interface Config {
  /** agentpanel gateway 【data-plane】 base URL (default http://127.0.0.1:9999). Used by `resolveToken` so the lease key is only sent to the gateway origin. */
  gatewayUrl?: string | undefined
  /** agentpanel gateway 【control-plane】 base URL for lease issue/renew/revoke (default http://127.0.0.1:9998/v1/harness). */
  controlPlaneUrl?: string | undefined
  /** Harness client id used as `Bearer <clientId>.<clientSecret>`. */
  clientId?: string | undefined
  /** Harness client secret. */
  clientSecret?: string | undefined
  /** Lease TTL in seconds (30-3600); defaults to 900. */
  leaseTtlSeconds?: number | undefined
  /** Lease requests-per-minute limit; defaults to 60. */
  leaseRpmLimit?: number | undefined
  /** Renew the lease after this fraction of its TTL elapses; defaults to 0.8. */
  renewalRatio?: number | undefined
  /** Usage page URL shown in the account UI (agentpanel has none by default). */
  usageUrl?: string | undefined
  /** Top-up page URL shown in the account UI. */
  topUpUrl?: string | undefined
  /**
   * Deployment display brand for account copy (for example the agentpanel
   * project name). Empty keeps the built-in DeepSeek product name.
   */
  brandName?: string | undefined
  /** Optional gateway API key header (x-api-key) when the gateway requires one. */
  gatewayApiKey?: string | undefined
  /**
   * agentpanel customer control-plane base URL for email-code sign-in and
   * customer leases (for example http://127.0.0.1:9998/v1/customer). Empty
   * (the default) keeps only the harness-lease flow and the browser dialog.
   */
  customerUrl?: string | undefined
  /**
   * Directory of the persisted customer session file. Defaults to the desktop
   * account store (`%APPDATA%/dsh-agentpanel` / `~/.config/dsh-agentpanel`) so
   * a web sign-in and the desktop share one session.
   */
  storageDir?: string | undefined
  /** Customer lease renewal check interval in milliseconds; defaults to 30000. */
  renewCheckMs?: number | undefined
}

/** Resolved configuration with defaults applied. */
interface ResolvedConfig {
  gatewayUrl: string
  controlPlaneUrl: string
  clientId: string
  clientSecret: string
  leaseTtlSeconds: number
  leaseRpmLimit: number
  renewalRatio: number
  usageUrl: string
  topUpUrl: string
  brandName: string
  gatewayApiKey: string
  customerUrl: string
  storageFile: string
  renewCheckMs: number
}

interface Lease {
  leaseId: string
  virtualKey: string
  expiresAtMs: number
  renewAfterSeconds: number
}

interface Attempt {
  locale: string
  origin: string
  loginSource: 'web' | 'desktop'
  view: SignInAttemptView
  controller: AbortController
  done: Promise<void>
}

/** Persisted customer lease; the schema is shared with the desktop account store. */
interface StoredLease {
  leaseId: string
  virtualKey: string
  expiresAt: string
  ttlSeconds: number
}

/** Persisted customer session; the schema is shared with the desktop account store. */
interface StoredAccount {
  accessToken: string
  tokenExpiresAt: string
  customerId: string
  customerEmail: string
  /** Account display name from the customer profile (nickname, then username). */
  customerName?: string
  /** Remaining purchased hours last reported by the agentpanel customer service. */
  remainingHours?: string
  lease: StoredLease | null
}

/** Customer identity and allowance read from `/auth/me`; absent fields keep the persisted values. */
interface CustomerSummary {
  name?: string
  email?: string
  remainingHours?: string
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/** @returns true when an ISO timestamp is missing or in the past. */
function expiredIso(value: string | undefined): boolean {
  if (!value) return true
  const time = new Date(value).getTime()
  return !Number.isFinite(time) || time <= Date.now()
}

/** @returns the trimmed email when well-formed, null otherwise. */
function validEmail(email: string): string | null {
  const address = email.trim()
  return EMAIL_PATTERN.test(address) && address.length <= 254 ? address : null
}

/** @returns a short user-facing message for an arbitrary failure. */
function messageOf(error: unknown): string {
  return error instanceof Error && error.message !== '' ? error.message.slice(0, 200) : '操作失败，请重试'
}

/**
 * Unwrap agentpanel's `success_response` envelope.
 * @returns the payload object; an empty object for a success response that carries
 * `data: null` (for example send-code, which reports only `msg`).
 */
function envelopeData(body: unknown): Record<string, unknown> {
  const envelope = body && typeof body === 'object' && !Array.isArray(body)
    ? body as Record<string, unknown>
    : undefined
  if (envelope === undefined) throw new Error('agentpanel account: 响应格式无效')
  const source = 'data' in envelope ? envelope.data : envelope
  if (source === null) return {}
  if (!source || typeof source !== 'object' || Array.isArray(source)) {
    throw new Error('agentpanel account: 响应格式无效')
  }
  return source as Record<string, unknown>
}

/** @returns the non-empty string at `key`, undefined for any other value. */
function textField(data: Record<string, unknown>, key: string): string | undefined {
  const value = data[key]
  return typeof value === 'string' && value !== '' ? value : undefined
}

/** @returns the customer display name: nickname, then username. */
function displayNameOf(data: Record<string, unknown>): string | undefined {
  return textField(data, 'nickname') ?? textField(data, 'username')
}

/** @returns `remaining_hours` as a decimal string, undefined when the field is absent. */
function remainingHoursOf(data: Record<string, unknown>): string | undefined {
  const value = data.remaining_hours
  return typeof value === 'number' || typeof value === 'string' ? String(value) : undefined
}

/** Resolve the customer session file; the default matches the desktop account store. */
function resolveStorageFile(storageDir?: string): string {
  const dir = storageDir || (process.env.APPDATA
    ? path.join(process.env.APPDATA, 'dsh-agentpanel')
    : path.join(homedir(), '.config', 'dsh-agentpanel'))
  return path.join(dir, 'account.json')
}

/** Thrown for unrecoverable agentpanel account configuration or protocol errors. */
export class AgentPanelAuthError extends Error {
  /** Stable error code rendered through the caller's locale dictionary. */
  readonly code: 'no-response' | 'network' | 'protocol' | 'expired' | 'storage'

  constructor(code: AgentPanelAuthError['code'], message?: string) {
    super(message ?? `agentpanel-account: ${code}`)
    this.name = 'AgentPanelAuthError'
    this.code = code
  }
}

/** Account backend that authenticates dshw against the agentpanel gateway lease. */
export class AgentPanelAccount extends Service {
  static inject: string[] = []
  private readonly config: ResolvedConfig
  private lease: Lease | undefined
  /** True when the lease was imported from the desktop customer session (no self-renewal/revocation). */
  private externalLease = false
  /** True when the active lease was issued through the customer control plane (renewed and revoked there). */
  private customerLease = false
  /** Persisted customer session backing a customer lease. */
  private customer: StoredAccount | undefined
  /** In-flight customer identity read shared by concurrent profile refreshes. */
  private summaryRead: Promise<CustomerSummary | undefined> | undefined
  private attempt: Attempt | undefined
  private readonly listeners = new Set<(identityOnly: boolean) => void>()
  private renewTimer: ReturnType<typeof setTimeout> | undefined
  private closed = false

  /** @param ctx - Host context. @param config - deployment options. */
  constructor(ctx: Context, config: Config = {}) {
    super(ctx, 'agentpanelAccount')
    this.config = {
      gatewayUrl: config.gatewayUrl || 'http://127.0.0.1:9999',
      controlPlaneUrl: config.controlPlaneUrl || 'http://127.0.0.1:9998/v1/harness',
      clientId: config.clientId || '',
      clientSecret: config.clientSecret || '',
      leaseTtlSeconds: config.leaseTtlSeconds ?? 900,
      leaseRpmLimit: config.leaseRpmLimit ?? 60,
      renewalRatio: config.renewalRatio ?? 0.8,
      usageUrl: config.usageUrl ?? '',
      topUpUrl: config.topUpUrl ?? '',
      brandName: (config.brandName ?? '').trim(),
      gatewayApiKey: config.gatewayApiKey ?? '',
      customerUrl: config.customerUrl || '',
      storageFile: resolveStorageFile(config.storageDir),
      renewCheckMs: config.renewCheckMs ?? 30_000,
    }
    // Adopt a persisted customer session (shared with the desktop account
    // store) so a restart — of this Host or of `dsh web` — keeps the sign-in.
    if (this.config.customerUrl !== '') this.adoptStoredCustomer()
    ctx.effect(() => async () => {
      this.closed = true
      if (this.renewTimer !== undefined) clearTimeout(this.renewTimer)
      this.renewTimer = undefined
    }, 'agentpanel-account: lifetime')
  }

  getState(): Promise<AccountView> {
    const brandName = this.config.brandName
    return Promise.resolve({
      status: this.lease === undefined ? 'signed-out' : 'credential-stored',
      links: { usageUrl: this.config.usageUrl, topUpUrl: this.config.topUpUrl },
      attempt: this.attempt?.view ?? null,
      ...(brandName === '' ? {} : { brandName }),
    })
  }

  async getProfile(_client: AccountClientMetadata): Promise<AccountDetails['profile'] | null> {
    // agentpanel has no Platform profile: the customer session carries the
    // account name and the remaining purchased hours. Re-read them from the
    // business service on every account refresh so the page follows usage.
    const account = this.customer
    if (account === undefined) return null
    const summary = await this.readCustomerSummary(account)
    const name = summary?.name ?? account.customerName ?? account.customerEmail
    const contact = summary?.email ?? account.customerEmail
    const remainingHours = summary?.remainingHours ?? account.remainingHours
    return {
      status: 'ready',
      value: {
        id: null, name, contact,
        ...(remainingHours === undefined ? {} : { remainingHours }),
      },
    }
  }

  getBalance(_client: AccountClientMetadata): Promise<AccountDetails['balance'] | null> {
    return Promise.resolve(null)
  }

  getUnnotifiedBonuses(_client: AccountClientMetadata): Promise<AccountBonusBatch | null> {
    return Promise.resolve(null)
  }

  ackBonusNotified(_accountId: AccountUserId, _orderId: AccountBonusOrderId, _client: AccountClientMetadata): Promise<boolean> {
    return Promise.resolve(false)
  }

  async startSignIn(client: AccountClientMetadata, callbackOrigin: string, loginSource: 'web' | 'desktop'): Promise<AccountView> {
    if (this.closed) throw new AgentPanelAuthError('protocol')
    const phase = this.attempt?.view.phase
    if (phase !== undefined && ['initializing', 'waiting-browser', 'exchanging', 'committing'].includes(phase)) {
      return this.getState()
    }
    const previous = this.attempt
    if (previous !== undefined) await previous.done
    const attempt: Attempt = {
      locale: client.locale.toLowerCase().startsWith('zh') ? 'zh_CN' : 'en_US',
      origin: callbackOrigin,
      loginSource,
      view: { id: randomUUID() as SignInAttemptId, phase: 'initializing' },
      controller: new AbortController(),
      done: Promise.resolve(),
    }
    this.attempt = attempt
    this.changed()
    attempt.done = this.issueLease(attempt).catch((error: unknown) => {
      console.error('[agentpanel-account] sign-in failed', error instanceof Error ? error.message : error)
      this.update(attempt, { phase: 'failed', errorCode: 'network' })
    })
    return this.getState()
  }

  async cancelSignIn(id: SignInAttemptId): Promise<AccountView> {
    const attempt = this.attempt
    if (attempt?.view.id === id) {
      if (attempt.view.phase !== 'committing') attempt.controller.abort()
      await attempt.done
    }
    return this.getState()
  }

  async signOut(_client: AccountClientMetadata): Promise<AccountView> {
    if (this.customerLease && this.customer !== undefined) {
      // Customer session: revoke the lease through the customer control plane
      // and drop the shared store so every surface (web Host, desktop main)
      // observes the signed-out state.
      const account = this.customer
      if (account.lease !== null) {
        try {
          const res = await fetch(`${this.config.customerUrl}/leases/${encodeURIComponent(account.lease.leaseId)}`, {
            method: 'DELETE',
            headers: { authorization: `Bearer ${account.accessToken}` },
          })
          if (!res.ok) throw new Error(`revoke http ${res.status}`)
        } catch (error) {
          console.error('[agentpanel-account] customer lease revoke failed', error instanceof Error ? error.message : error)
        }
      }
      this.dropCustomer()
      this.attempt = undefined
      this.ctx.emit('agentpanel-account/signed-out')
      this.changed()
      return this.getState()
    }
    if (this.lease !== undefined && !this.externalLease) {
      const { clientId, clientSecret, controlPlaneUrl, gatewayApiKey } = this.config
      const headers: Record<string, string> = { authorization: `Bearer ${clientId}.${clientSecret}` }
      if (gatewayApiKey) headers['x-api-key'] = gatewayApiKey
      try {
        await fetch(`${controlPlaneUrl}/gateway/leases/${encodeURIComponent(this.lease.leaseId)}`, { method: 'DELETE', headers })
      } catch (error) {
        console.error('[agentpanel-account] revoke failed', error instanceof Error ? error.message : error)
      }
    }
    if (this.renewTimer !== undefined) clearTimeout(this.renewTimer)
    this.renewTimer = undefined
    this.lease = undefined
    this.externalLease = false
    // The desktop-owned shared session stays on disk; this Host only stops
    // reading it until the next import.
    this.customer = undefined
    this.customerLease = false
    this.attempt = undefined
    this.ctx.emit('agentpanel-account/signed-out')
    this.changed()
    return this.getState()
  }

  /**
   * Adopt a lease issued through the desktop customer sign-in flow.
   *
   * The desktop keeps renewing the lease and re-imports after each renewal, so
   * this service must not schedule its own renewal (it has no renewal
   * credentials). Sign-out through this service clears the imported lease
   * locally without revoking it; the desktop session stays authoritative.
   *
   * @param session - lease snapshot from the desktop account store.
   * @returns the account state after adopting the session.
   */
  async importSession(session: ImportedLeaseSession): Promise<AccountView> {
    if (this.closed) throw new AgentPanelAuthError('protocol')
    if (this.renewTimer !== undefined) { clearTimeout(this.renewTimer); this.renewTimer = undefined }
    // The desktop owns lease renewal and revocation. Its shared customer
    // session still names the account and carries the business allowance, so
    // keep it for read-only profile reads; no renewal or revocation runs
    // through it (externalLease short-circuits both). Without a customer
    // control plane there is no profile to read.
    this.customer = this.config.customerUrl === '' ? undefined : this.readStoredCustomer()
    this.customerLease = false
    this.lease = {
      leaseId: session.leaseId,
      virtualKey: session.virtualKey,
      expiresAtMs: session.expiresAtMs,
      renewAfterSeconds: session.renewAfterSeconds ?? 0,
    }
    this.externalLease = true
    this.attempt = undefined
    this.changed()
    return this.getState()
  }

  /**
   * Drop the local session mirror: an imported desktop lease, or a self-owned
   * customer session that an authoritative surface (for example desktop main)
   * reports as signed out. Owned customer sessions are cleared without
   * revocation — the caller that observed the signed-out state owns revocation.
   * @returns the account state after clearing.
   */
  async clearSession(): Promise<AccountView> {
    if (this.closed) throw new AgentPanelAuthError('protocol')
    if (this.lease === undefined) return this.getState()
    if (this.renewTimer !== undefined) { clearTimeout(this.renewTimer); this.renewTimer = undefined }
    const ownedCustomer = this.customerLease
    this.lease = undefined
    this.externalLease = false
    this.customer = undefined
    this.customerLease = false
    if (ownedCustomer) this.dropCustomerStore()
    this.attempt = undefined
    this.ctx.emit('agentpanel-account/signed-out')
    this.changed()
    return this.getState()
  }

  async *watch(signal: AbortSignal, includeIdentityChanges: boolean = false): AsyncIterable<AccountView> {
    let dirty = true
    let wake: (() => void) | undefined
    const wakeUp = (): void => { dirty = true; wake?.() }
    const changed = (identityOnly: boolean): void => { if (!identityOnly || includeIdentityChanges) wakeUp() }
    this.listeners.add(changed)
    signal.addEventListener('abort', wakeUp, { once: true })
    try {
      while (!this.closed && !signal.aborted) {
        if (dirty) { dirty = false; yield await this.getState(); continue }
        await new Promise<void>((resolve) => { wake = resolve })
      }
    } finally {
      this.listeners.delete(changed)
      signal.removeEventListener('abort', wakeUp)
    }
  }

  async resolveToken(url: string): Promise<string | undefined> {
    if (this.closed || this.lease === undefined) return undefined
    let destination: URL
    let gateway: URL
    try { destination = new URL(url) } catch { return undefined }
    try { gateway = new URL(this.config.gatewayUrl) } catch { return undefined }
    if (destination.origin !== gateway.origin) return undefined
    return this.lease.virtualKey
  }

  async rejectToken(token: string): Promise<void> {
    if (this.lease?.virtualKey === token) this.expireLease()
  }

  getDeviceIdentity(): Promise<{ deviceId?: string; userId?: AccountUserId; osVersion: string }> {
    return Promise.resolve({ osVersion: `${platform()} ${release()}` })
  }

  /** @returns which sign-in surface the client should offer: the agentpanel customer form or the browser flow. */
  getAuthMode(): Promise<'customer' | 'browser'> {
    return Promise.resolve(this.config.customerUrl === '' ? 'browser' : 'customer')
  }

  /**
   * Request a verification mail for the customer sign-in form.
   * @param email - customer mailbox.
   * @param purpose - code purpose mirrored by the control plane's `type` field.
   * @returns whether the control plane accepted the request, with a user-facing message on failure.
   */
  async sendCode(email: string, purpose: CustomerCodePurpose): Promise<CustomerCodeOutcome> {
    if (this.config.customerUrl === '') return { ok: false, message: 'customer sign-in is not configured' }
    const address = validEmail(email)
    if (address === null) return { ok: false, message: '请输入有效的邮箱地址' }
    try {
      await this.customerRequest('/auth/send-code', { email: address, type: purpose })
      return { ok: true, message: '' }
    } catch (error) {
      return { ok: false, message: messageOf(error) }
    }
  }

  /**
   * Register a customer account with an email verification code and a password.
   * @returns the signed-in account state, or a user-facing failure message.
   */
  async register(email: string, code: string, password: string): Promise<CustomerAuthOutcome> {
    const address = validEmail(email)
    if (address === null) return { ok: false, message: '请输入有效的邮箱地址', state: null }
    if (!/^\d{6}$/.test(code.trim())) return { ok: false, message: '请输入 6 位邮箱验证码', state: null }
    if (password.length < 6) return { ok: false, message: '密码至少需要 6 位', state: null }
    const resumed = await this.resumeCustomer()
    if (resumed !== null) return resumed
    return this.customerAuthenticate('/register', { email: address, code: code.trim(), password }, address)
  }

  /**
   * Sign in with the customer email and password.
   * @returns the signed-in account state, or a user-facing failure message.
   */
  async login(email: string, password: string): Promise<CustomerAuthOutcome> {
    const address = validEmail(email)
    if (address === null) return { ok: false, message: '请输入有效的邮箱地址', state: null }
    if (password === '') return { ok: false, message: '请输入密码', state: null }
    const resumed = await this.resumeCustomer()
    if (resumed !== null) return resumed
    return this.customerAuthenticate('/login', { email: address, password }, address)
  }

  /**
   * Sign in with the customer email and a verification code.
   * @returns the signed-in account state, or a user-facing failure message.
   */
  async loginCode(email: string, code: string): Promise<CustomerAuthOutcome> {
    const address = validEmail(email)
    if (address === null) return { ok: false, message: '请输入有效的邮箱地址', state: null }
    if (!/^\d{6}$/.test(code.trim())) return { ok: false, message: '请输入 6 位邮箱验证码', state: null }
    const resumed = await this.resumeCustomer()
    if (resumed !== null) return resumed
    return this.customerAuthenticate('/login-code', { email: address, code: code.trim() }, address)
  }

  /**
   * Reset a customer password with an email verification code.
   * @param email - customer mailbox.
   * @param code - 6-digit mail code sent with the `reset_password` purpose.
   * @param password - new account password.
   * @returns whether the control plane accepted the reset, with a user-facing message on failure.
   */
  async resetPassword(email: string, code: string, password: string): Promise<CustomerCodeOutcome> {
    if (this.config.customerUrl === '') return { ok: false, message: 'customer sign-in is not configured' }
    const address = validEmail(email)
    if (address === null) return { ok: false, message: '请输入有效的邮箱地址' }
    if (!/^\d{6}$/.test(code.trim())) return { ok: false, message: '请输入 6 位邮箱验证码' }
    if (password.length < 6) return { ok: false, message: '密码至少需要 6 位' }
    try {
      await this.customerRequest('/auth/reset-password', {
        email: address, code: code.trim(), new_password: password,
      })
      return { ok: true, message: '' }
    } catch (error) {
      return { ok: false, message: messageOf(error) }
    }
  }

  private async issueLease(attempt: Attempt): Promise<void> {
    const { clientId, clientSecret, controlPlaneUrl, leaseTtlSeconds, leaseRpmLimit, gatewayApiKey } = this.config
    if (!clientId || !clientSecret) {
      this.update(attempt, { phase: 'failed', errorCode: 'protocol' })
      return
    }
    const headers: Record<string, string> = {
      'content-type': 'application/json',
      authorization: `Bearer ${clientId}.${clientSecret}`,
    }
    if (gatewayApiKey) headers['x-api-key'] = gatewayApiKey
    let res: Response
    try {
      res = await fetch(`${controlPlaneUrl}/gateway/leases`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ ttl_seconds: leaseTtlSeconds, rpm_limit: leaseRpmLimit }),
      })
    } catch (error) {
      console.error('[agentpanel-account] lease request failed', error instanceof Error ? error.message : error)
      this.update(attempt, { phase: 'failed', errorCode: 'no-response' })
      return
    }
    if (!res.ok) {
      this.update(attempt, { phase: 'failed', errorCode: 'network' })
      return
    }
    const json = await res.json().catch(() => null) as { data?: Record<string, unknown> } | null
    const data = (json?.data ?? json) as Record<string, unknown> | null
    const virtualKey = typeof data?.virtual_key === 'string' ? data.virtual_key : undefined
    const leaseId = typeof data?.lease_id === 'string' ? data.lease_id : undefined
    if (!virtualKey || !leaseId) {
      this.update(attempt, { phase: 'failed', errorCode: 'protocol' })
      return
    }
    const ttl = typeof data?.ttl_seconds === 'number' ? data.ttl_seconds : leaseTtlSeconds
    this.lease = {
      leaseId,
      virtualKey,
      expiresAtMs: typeof data?.expires_at === 'string' ? Date.parse(data.expires_at) : Date.now() + ttl * 1000,
      renewAfterSeconds: typeof data?.renew_after_seconds === 'number'
        ? data.renew_after_seconds
        : Math.floor(ttl * this.config.renewalRatio),
    }
    this.update(attempt, { phase: 'succeeded' })
    this.scheduleRenewal()
    this.changed()
  }

  private scheduleRenewal(): void {
    if (this.lease === undefined) return
    if (this.renewTimer !== undefined) clearTimeout(this.renewTimer)
    const delay = Math.max(1000, this.lease.renewAfterSeconds * 1000)
    this.renewTimer = setTimeout(() => { void this.renewLease() }, delay)
  }

  private async renewLease(): Promise<void> {
    // Imported (desktop-owned) leases renew on the desktop, which re-imports
    // after each renewal; this service has no renewal credentials for them.
    if (this.lease === undefined || this.externalLease || this.closed) return
    if (this.customerLease) {
      await this.renewCustomerLease()
      return
    }
    const { clientId, clientSecret, controlPlaneUrl, leaseTtlSeconds, gatewayApiKey } = this.config
    const headers: Record<string, string> = {
      'content-type': 'application/json',
      authorization: `Bearer ${clientId}.${clientSecret}`,
    }
    if (gatewayApiKey) headers['x-api-key'] = gatewayApiKey
    try {
      const res = await fetch(`${controlPlaneUrl}/gateway/leases/${encodeURIComponent(this.lease.leaseId)}/renew`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ ttl_seconds: leaseTtlSeconds }),
      })
      if (!res.ok) throw new Error(`renew http ${res.status}`)
      const json = await res.json().catch(() => null) as { data?: Record<string, string | number> } | null
      const data = (json?.data ?? json) as Record<string, string | number> | null
      if (typeof data?.expires_at === 'string') this.lease.expiresAtMs = Date.parse(data.expires_at)
      if (typeof data?.renew_after_seconds === 'number') this.lease.renewAfterSeconds = data.renew_after_seconds
      else if (typeof data?.ttl_seconds === 'number') this.lease.renewAfterSeconds = Math.floor(data.ttl_seconds * this.config.renewalRatio)
      this.scheduleRenewal()
    } catch (error) {
      console.error('[agentpanel-account] lease renewal failed', error instanceof Error ? error.message : error)
      this.expireLease()
    }
  }

  private expireLease(): void {
    if (this.renewTimer !== undefined) clearTimeout(this.renewTimer)
    this.renewTimer = undefined
    const hadLease = this.lease !== undefined
    const ownedCustomer = this.customerLease
    this.lease = undefined
    this.externalLease = false
    this.customerLease = false
    // A rejected or unrenewable customer lease is dead server-side; drop the
    // shared store so the desktop account surfaces sign out as well.
    if (ownedCustomer) {
      this.customer = undefined
      this.dropCustomerStore()
    }
    if (hadLease) {
      this.ctx.emit('agentpanel-account/session-expired')
      this.changed()
    }
  }

  /** Clear the customer session in memory and its persisted store. */
  private dropCustomer(): void {
    if (this.renewTimer !== undefined) clearTimeout(this.renewTimer)
    this.renewTimer = undefined
    this.lease = undefined
    this.externalLease = false
    this.customerLease = false
    this.customer = undefined
    this.dropCustomerStore()
  }

  /** Read the persisted customer session; undefined when absent or its token expired. */
  private readStoredCustomer(): StoredAccount | undefined {
    try {
      if (!existsSync(this.config.storageFile)) return undefined
      const parsed = JSON.parse(readFileSync(this.config.storageFile, 'utf8')) as StoredAccount
      if (typeof parsed.accessToken !== 'string' || parsed.accessToken === '') return undefined
      if (expiredIso(parsed.tokenExpiresAt)) return undefined
      return parsed
    } catch {
      return undefined
    }
  }

  /** Persist the current customer session (0o600); persistence failures do not block the sign-in. */
  private persistCustomer(): void {
    if (this.customer === undefined) return
    try {
      const dir = path.dirname(this.config.storageFile)
      if (!existsSync(dir)) mkdirSync(dir, { recursive: true })
      writeFileSync(this.config.storageFile, JSON.stringify(this.customer), { mode: 0o600 })
    } catch {
      // 持久化失败不阻断本次登录态；下次启动会要求重新登录。
    }
  }

  /** Remove the persisted customer session file. */
  private dropCustomerStore(): void {
    try {
      if (existsSync(this.config.storageFile)) rmSync(this.config.storageFile)
    } catch {
      // Store removal is best-effort; the in-memory session is already gone.
    }
  }

  /** Adopt the persisted customer session when its token and lease are still valid. */
  private adoptStoredCustomer(): void {
    const stored = this.readStoredCustomer()
    if (stored === undefined) return
    this.customer = stored
    if (stored.lease !== null && !expiredIso(stored.lease.expiresAt)) {
      this.applyCustomerLease(stored.lease)
      this.scheduleRenewal()
      this.changed()
      return
    }
    // Token valid but no live lease (for example a crash between sign-in and
    // lease exchange): resume in the background without blocking boot.
    void this.resumeCustomer().then((outcome) => {
      if (outcome?.ok === true) this.changed()
    }).catch(() => undefined)
  }

  /** Point the active lease at a customer-issued lease snapshot. */
  private applyCustomerLease(lease: StoredLease): void {
    const expiresAtMs = Date.parse(lease.expiresAt)
    this.lease = {
      leaseId: lease.leaseId,
      virtualKey: lease.virtualKey,
      expiresAtMs: Number.isFinite(expiresAtMs) ? expiresAtMs : Date.now() + lease.ttlSeconds * 1000,
      renewAfterSeconds: Math.max(1, Math.floor(lease.ttlSeconds * this.config.renewalRatio)),
    }
    this.externalLease = false
    this.customerLease = true
  }

  /**
   * Read the customer identity and remaining allowance once for concurrent
   * account refreshes; finished reads are not cached so the page follows usage.
   * @param account - customer session the read belongs to.
   * @returns the business-service summary, or undefined when the read failed.
   */
  private readCustomerSummary(account: StoredAccount): Promise<CustomerSummary | undefined> {
    this.summaryRead ??= this.fetchCustomerSummary(account)
      .finally(() => { this.summaryRead = undefined })
    return this.summaryRead
  }

  /**
   * GET the customer's current profile and fold its identity fields into the
   * persisted session. A failure keeps the previously stored values.
   * @param account - customer session the read belongs to.
   * @returns the fields the business service reported.
   */
  private async fetchCustomerSummary(account: StoredAccount): Promise<CustomerSummary | undefined> {
    try {
      const data = await this.customerRequest('/auth/me', undefined, account.accessToken)
      const name = displayNameOf(data)
      const email = textField(data, 'email')
      const remainingHours = remainingHoursOf(data)
      let changed = false
      if (name !== undefined && name !== account.customerName) { account.customerName = name; changed = true }
      if (email !== undefined && email !== account.customerEmail) { account.customerEmail = email; changed = true }
      if (remainingHours !== undefined && remainingHours !== account.remainingHours) {
        account.remainingHours = remainingHours
        changed = true
      }
      if (changed) this.persistCustomer()
      return {
        ...(name === undefined ? {} : { name }),
        ...(email === undefined ? {} : { email }),
        ...(remainingHours === undefined ? {} : { remainingHours }),
      }
    } catch (error) {
      console.error('[agentpanel-account] customer profile read failed', error instanceof Error ? error.message : error)
      return undefined
    }
  }

  /**
   * Resume a persisted customer session: return the signed-in state when a live
   * lease exists, re-issue the lease when only the token remains valid, and
   * null when the caller must authenticate from scratch.
   */
  private async resumeCustomer(): Promise<CustomerAuthOutcome | null> {
    // An imported desktop lease owns renewal; never issue or resume a second
    // customer lease from this Host while it is in force.
    if (this.externalLease) return null
    const account = this.customer
    if (account === undefined || expiredIso(account.tokenExpiresAt)) return null
    if (account.lease !== null && !expiredIso(account.lease.expiresAt) && this.lease !== undefined) {
      return { ok: true, message: '', state: await this.getState() }
    }
    try {
      const lease = await this.issueCustomerLease(account)
      account.lease = lease
      this.applyCustomerLease(lease)
      this.persistCustomer()
      this.markCustomerSucceeded()
      this.scheduleRenewal()
      this.changed()
      return { ok: true, message: '', state: await this.getState() }
    } catch {
      return null
    }
  }

  /**
   * Authenticate a customer against the control plane, exchange the JWT for a
   * gateway lease, persist the session, and publish the signed-in state.
   */
  private async customerAuthenticate(endpoint: string, body: Record<string, unknown>, email: string): Promise<CustomerAuthOutcome> {
    if (this.config.customerUrl === '') return { ok: false, message: 'customer sign-in is not configured', state: null }
    try {
      const data = await this.customerRequest(`/auth${endpoint}`, body)
      const accessToken = data.access_token
      if (typeof accessToken !== 'string' || accessToken === '') throw new Error('登录态无效，请重试')
      const expiresIn = typeof data.expires_in === 'number' && data.expires_in > 0 ? data.expires_in : 86_400
      const customer = data.customer && typeof data.customer === 'object' ? data.customer as Record<string, unknown> : {}
      const name = displayNameOf(customer)
      const remainingHours = remainingHoursOf(customer)
      const account: StoredAccount = {
        accessToken,
        tokenExpiresAt: new Date(Date.now() + expiresIn * 1000).toISOString(),
        customerId: String(customer.id ?? ''),
        customerEmail: typeof customer.email === 'string' ? customer.email : email,
        ...(name === undefined ? {} : { customerName: name }),
        ...(remainingHours === undefined ? {} : { remainingHours }),
        lease: null,
      }
      // 认证成功但换租约失败：保留 JWT 供重试，避免用户重新走一遍邮箱验证。
      try {
        account.lease = await this.issueCustomerLease(account)
      } catch (error) {
        this.customer = account
        this.persistCustomer()
        throw error
      }
      this.customer = account
      this.applyCustomerLease(account.lease)
      this.persistCustomer()
      this.markCustomerSucceeded()
      this.scheduleRenewal()
      this.changed()
      return { ok: true, message: '', state: await this.getState() }
    } catch (error) {
      return { ok: false, message: messageOf(error), state: null }
    }
  }

  /** Publish a succeeded attempt so clients treat the transition as a completed sign-in. */
  private markCustomerSucceeded(): void {
    this.attempt = {
      locale: 'zh_CN',
      origin: '',
      loginSource: 'web',
      view: { id: randomUUID() as SignInAttemptId, phase: 'succeeded' },
      controller: new AbortController(),
      done: Promise.resolve(),
    }
  }

  /** Exchange the customer JWT for a fresh gateway lease bound to the customer. */
  private async issueCustomerLease(account: StoredAccount): Promise<StoredLease> {
    const data = await this.customerRequest('/leases', {}, account.accessToken)
    if (typeof data.lease_id !== 'string' || typeof data.virtual_key !== 'string') {
      throw new Error('agentpanel account: 租约响应缺少字段')
    }
    const expiresAt = typeof data.expires_at === 'string' ? data.expires_at : ''
    if (expiredIso(expiresAt)) throw new Error('agentpanel account: 租约已过期')
    return {
      leaseId: data.lease_id,
      virtualKey: data.virtual_key,
      expiresAt,
      ttlSeconds: typeof data.ttl_seconds === 'number' ? data.ttl_seconds : 900,
    }
  }

  /** Renew the customer lease through the control plane; expiry drops the shared session. */
  private async renewCustomerLease(): Promise<void> {
    const account = this.customer
    const lease = account?.lease
    if (account === undefined || lease === null || lease === undefined) return
    try {
      const data = await this.customerRequest(`/leases/${encodeURIComponent(lease.leaseId)}/renew`, {}, account.accessToken)
      const expiresAt = typeof data.expires_at === 'string' ? data.expires_at : ''
      if (expiredIso(expiresAt)) throw new Error('agentpanel account: 续期响应缺少有效过期时间')
      account.lease = {
        ...lease,
        expiresAt,
        ttlSeconds: typeof data.ttl_seconds === 'number' ? data.ttl_seconds : lease.ttlSeconds,
      }
      this.applyCustomerLease(account.lease)
      this.persistCustomer()
      this.scheduleRenewal()
    } catch (error) {
      console.error('[agentpanel-account] customer lease renewal failed', error instanceof Error ? error.message : error)
      if (expiredIso(account.lease?.expiresAt)) this.dropCustomer()
    }
  }

  /**
   * Call the customer control plane and unwrap the `success_response` envelope.
   * @param endpoint - path below `customerUrl`.
   * @param body - JSON body for a POST; absent issues a GET.
   * @param token - customer JWT for authenticated reads.
   * @returns the response payload.
   */
  private async customerRequest(endpoint: string, body: Record<string, unknown> | undefined, token?: string): Promise<Record<string, unknown>> {
    const headers: Record<string, string> = { 'content-type': 'application/json' }
    if (token !== undefined) headers.authorization = `Bearer ${token}`
    const res = await fetch(`${this.config.customerUrl}${endpoint}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers,
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
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

  private update(attempt: Attempt, value: Partial<SignInAttemptView>): void {
    attempt.view = { ...attempt.view, ...value }
    this.changed()
  }

  private changed(identityOnly = false): void { for (const listener of this.listeners) listener(identityOnly) }
}

export default AgentPanelAccount

declare module '@deepseek-ai/cordis' {
  interface Context {
    agentpanelAccount: AgentPanelAccount
  }
  interface Events {
    /** Server rejection or renewal failure removed the current lease credential. */
    'agentpanel-account/session-expired'(): void
    /** Local grant removal has completed. */
    'agentpanel-account/signed-out'(): void
  }
}
