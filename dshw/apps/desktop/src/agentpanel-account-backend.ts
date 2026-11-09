/**
 * agentpanel 网关账号后端（替换 DeepSeek 账号登录）
 *
 * 设计要点：
 * - agentpanel 网关【数据面】只接受「租约虚拟 key」（`dgw.<lease_id>.<secret>`），不接受 JWT/登录态；
 * - 租约由【控制面】`POST /gateway/leases` 签发，身份认证用 Harness 客户端凭据
 *   （`Authorization: Bearer <client_id>.<secret>` 或 X-Harness-Client-Id/Secret）；
 * - 因此桌面端「登录」= 用客户端凭据向 agentpanel 申请一张可续期的租约虚拟 key，
 *   并以该 key 作为后续网关调用的会话凭证（即用户口中的「续约key」）；
 * - 后台按 TTL 比例自动续期（renew），过期/续期失败则通知会话失效。
 *
 * 配置（环境变量，由桌面启动进程注入）：
 * - AGENTPANEL_GATEWAY_URL        网关基址，默认 http://127.0.0.1:9999
 * - AGENTPANEL_HARNESS_TOKEN     完整 Bearer 凭证 `<client_id>.<secret>`
 * - AGENTPANEL_HARNESS_CLIENT_ID / AGENTPANEL_HARNESS_CLIENT_SECRET  二选一拆分形式
 * - AGENTPANEL_ACCOUNT_STORE_DIR  租约持久化目录（默认 %APPDATA%/dsh-agentpanel 或 ~/.config/dsh-agentpanel）
 * - AGENTPANEL_USAGE_URL / AGENTPANEL_TOPUP_URL  账号中心/充值页（仅展示）
 * - AGENTPANEL_RENEW_RATIO        剩余 TTL 低于该比例时续期，默认 0.8
 * - AGENTPANEL_RENEW_CHECK_MS     续期轮询间隔 ms，默认 30000
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync, rmSync } from 'node:fs'
import { homedir } from 'node:os'
import path from 'node:path'

/** Account view consumed by the desktop welcome/onboarding UI. */
export interface AccountView {
  readonly status: 'signed-out' | 'credential-stored'
  readonly links: { usageUrl: string; topUpUrl: string }
  readonly attempt: SignInAttempt | null
}

export interface SignInAttempt {
  readonly id: string
  readonly phase: string
  readonly authorizeUrl?: string
  readonly expiresAt?: number
  readonly errorCode?: string
}

/** Opaque client identity passed by the UI; not used by agentpanel login. */
export type AccountClientMetadata = Record<string, unknown>

export type SignInAttemptId = string

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
  gatewayUrl: string
  clientToken?: string
  clientId?: string
  clientSecret?: string
  storageDir?: string
  usageUrl?: string
  topUpUrl?: string
  renewRatio?: number
  renewCheckMs?: number
}

interface StoredLease {
  leaseId: string
  virtualKey: string
  expiresAt: string
  ttlSeconds: number
}

const LEASES = '/gateway/leases'

function base(gatewayUrl: string): string {
  return gatewayUrl.replace(/\/+$/, '')
}

function authHeader(config: AgentpanelAccountConfig): Record<string, string> {
  const token =
    config.clientToken ??
    (config.clientId && config.clientSecret ? `${config.clientId}.${config.clientSecret}` : '')
  if (!token) {
    throw new Error('agentpanel account: 缺少 Harness 客户端凭据（AGENTPANEL_HARNESS_TOKEN 或 CLIENT_ID+SECRET）')
  }
  return { Authorization: `Bearer ${token}` }
}

function linksOf(config: AgentpanelAccountConfig): { usageUrl: string; topUpUrl: string } {
  const b = base(config.gatewayUrl)
  return {
    usageUrl: config.usageUrl ?? `${b}/account/usage`,
    topUpUrl: config.topUpUrl ?? `${b}/account/top-up`,
  }
}

function signedOut(config: AgentpanelAccountConfig): AccountView {
  return { status: 'signed-out', links: linksOf(config), attempt: null }
}

function credentialStored(config: AgentpanelAccountConfig, _lease: StoredLease): AccountView {
  return { status: 'credential-stored', links: linksOf(config), attempt: null }
}

function resolveStorageFile(config: AgentpanelAccountConfig): string {
  const dir =
    config.storageDir ??
    (process.env.APPDATA
      ? path.join(process.env.APPDATA, 'dsh-agentpanel')
      : path.join(homedir(), '.config', 'dsh-agentpanel'))
  return path.join(dir, 'account.json')
}

/** Pull the lease payload out of agentpanel's `success_response` envelope (or a bare object). */
function extractLease(body: unknown): {
  lease_id: string
  virtual_key: string
  expires_at: string
  ttl_seconds?: number
} | null {
  if (body && typeof body === 'object') {
    const candidate = (body as Record<string, unknown>).data ?? body
    if (candidate && typeof candidate === 'object') {
      const d = candidate as Record<string, unknown>
      if (typeof d.lease_id === 'string' && typeof d.virtual_key === 'string') {
        return {
          lease_id: d.lease_id,
          virtual_key: d.virtual_key,
          expires_at: String(d.expires_at ?? ''),
          ttl_seconds: typeof d.ttl_seconds === 'number' ? d.ttl_seconds : undefined,
        }
      }
    }
  }
  return null
}

/**
 * Connect native account operations to the agentpanel gateway.
 * @param config - gateway base URL + Harness client credential.
 * @returns account operations with automatic lease renewal.
 */
export function agentpanelAccountBackend(config: AgentpanelAccountConfig): DesktopAccountBackend {
  const storageFile = resolveStorageFile(config)
  const renewRatio = config.renewRatio ?? 0.8
  const renewCheckMs = config.renewCheckMs ?? 30_000
  let renewTimer: ReturnType<typeof setInterval> | undefined
  let current: StoredLease | null = readStored()

  function readStored(): StoredLease | null {
    try {
      if (!existsSync(storageFile)) return null
      const parsed = JSON.parse(readFileSync(storageFile, 'utf8')) as StoredLease
      if (!parsed.leaseId || !parsed.virtualKey) return null
      if (parsed.expiresAt && new Date(parsed.expiresAt).getTime() <= Date.now()) return null
      return parsed
    } catch {
      return null
    }
  }

  function persist(lease: StoredLease | null): void {
    current = lease
    try {
      const dir = path.dirname(storageFile)
      if (!existsSync(dir)) mkdirSync(dir, { recursive: true })
      if (lease) writeFileSync(storageFile, JSON.stringify(lease), { mode: 0o600 })
      else if (existsSync(storageFile)) rmSync(storageFile)
    } catch {
      // 持久化失败不阻断登录态；下次启动会重新签发。
    }
  }

  async function issue(): Promise<StoredLease> {
    const res = await fetch(`${base(config.gatewayUrl)}${LEASES}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', ...authHeader(config) },
      body: JSON.stringify({}),
    })
    if (!res.ok) throw new Error(`agentpanel 租约签发失败: ${res.status}`)
    const lease = extractLease(await res.json())
    if (!lease || !lease.expires_at) throw new Error('agentpanel 租约响应缺少字段')
    return {
      leaseId: lease.lease_id,
      virtualKey: lease.virtual_key,
      expiresAt: lease.expires_at,
      ttlSeconds: lease.ttl_seconds ?? 900,
    }
  }

  async function renew(lease: StoredLease): Promise<StoredLease> {
    const res = await fetch(`${base(config.gatewayUrl)}${LEASES}/${encodeURIComponent(lease.leaseId)}/renew`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', ...authHeader(config) },
      body: JSON.stringify({}),
    })
    if (!res.ok) throw new Error(`agentpanel 租约续期失败: ${res.status}`)
    const data = (await res.json()) as Record<string, unknown>
    const expiresAt = (data.data as Record<string, unknown> | undefined)?.expires_at ?? (data.expires_at as string | undefined)
    if (!expiresAt) throw new Error('agentpanel 续期响应缺少 expires_at')
    const ttl = (data.data as Record<string, unknown> | undefined)?.ttl_seconds ?? (data.ttl_seconds as number | undefined)
    return { ...lease, expiresAt: String(expiresAt), ttlSeconds: typeof ttl === 'number' ? ttl : lease.ttlSeconds }
  }

  async function revoke(lease: StoredLease): Promise<void> {
    await fetch(`${base(config.gatewayUrl)}${LEASES}/${encodeURIComponent(lease.leaseId)}`, {
      method: 'DELETE',
      headers: authHeader(config),
    }).catch(() => {})
  }

  function stopRenew(): void {
    if (renewTimer) {
      clearInterval(renewTimer)
      renewTimer = undefined
    }
  }

  function ensureRenewLoop(onExpired: () => void): void {
    if (renewTimer) return
    renewTimer = setInterval(async () => {
      const lease = current
      if (!lease) return
      const expiresMs = new Date(lease.expiresAt).getTime()
      const ttlMs = (lease.ttlSeconds || 900) * 1000
      const remaining = expiresMs - Date.now()
      if (remaining > ttlMs * renewRatio) return
      try {
        persist(await renew(lease))
      } catch {
        if (new Date(lease.expiresAt).getTime() <= Date.now()) {
          persist(null)
          onExpired()
        }
      }
    }, renewCheckMs)
    if (typeof renewTimer.unref === 'function') renewTimer.unref()
  }

  return {
    async state() {
      current = readStored()
      return current ? credentialStored(config, current) : signedOut(config)
    },
    async start(_client) {
      stopRenew()
      const lease = await issue()
      persist(lease)
      ensureRenewLoop(() => {})
      return credentialStored(config, lease)
    },
    async cancel(_id) {
      current = readStored()
      return current ? credentialStored(config, current) : signedOut(config)
    },
    async signOut(_client) {
      const lease = readStored()
      if (lease) await revoke(lease)
      persist(null)
      stopRenew()
      return signedOut(config)
    },
    watch(listener, _failed, expired, onAnalyticsEnabledChanged) {
      // agentpanel 无产品分析策略流；本端直接发布 false。
      onAnalyticsEnabledChanged?.(false)
      listener(current ? credentialStored(config, current) : signedOut(config))
      const timer = setInterval(() => {
        const before = current?.leaseId ?? null
        current = readStored()
        const after = current?.leaseId ?? null
        if (before !== after) {
          listener(current ? credentialStored(config, current) : signedOut(config))
          return
        }
        if (after && new Date(current!.expiresAt).getTime() <= Date.now()) {
          persist(null)
          listener(signedOut(config))
          expired()
        }
      }, renewCheckMs)
      if (typeof timer.unref === 'function') timer.unref()
      return () => clearInterval(timer)
    },
  }
}
