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
import { randomUUID } from 'node:crypto'
import { platform, release } from 'node:os'
import { Context, Service } from '@deepseek-ai/cordis'
import type { ImportedLeaseSession } from './types.ts'
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

export type { ImportedLeaseSession } from './types.ts'

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
  /** Optional gateway API key header (x-api-key) when the gateway requires one. */
  gatewayApiKey?: string | undefined
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
  gatewayApiKey: string
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
      gatewayApiKey: config.gatewayApiKey ?? '',
    }
    ctx.effect(() => async () => {
      this.closed = true
      if (this.renewTimer !== undefined) clearTimeout(this.renewTimer)
      this.renewTimer = undefined
    }, 'agentpanel-account: lifetime')
  }

  getState(): Promise<AccountView> {
    return Promise.resolve({
      status: this.lease === undefined ? 'signed-out' : 'credential-stored',
      links: { usageUrl: this.config.usageUrl, topUpUrl: this.config.topUpUrl },
      attempt: this.attempt?.view ?? null,
    })
  }

  getProfile(_client: AccountClientMetadata): Promise<AccountDetails['profile'] | null> {
    return Promise.resolve(null)
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
   * Drop the imported desktop session locally (for example after the desktop
   * account store was signed out or expired).
   * @returns the account state after clearing.
   */
  async clearSession(): Promise<AccountView> {
    if (this.closed) throw new AgentPanelAuthError('protocol')
    if (!this.externalLease) return this.getState()
    if (this.renewTimer !== undefined) { clearTimeout(this.renewTimer); this.renewTimer = undefined }
    this.lease = undefined
    this.externalLease = false
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
    this.lease = undefined
    this.externalLease = false
    if (hadLease) {
      this.ctx.emit('agentpanel-account/session-expired')
      this.changed()
    }
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
