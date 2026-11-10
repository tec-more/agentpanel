/**
 * REAL end-to-end integration test for the agentpanel account backend.
 *
 * Hits the live agentpanel gateway (control plane on the harness app + data-plane
 * gateway) to verify the full lease lifecycle: issue → resolve → revoke. It is
 * env-gated and skipped unless AGENTPANEL_E2E_CLIENT_ID / AGENTPANEL_E2E_CLIENT_SECRET
 * are provided, so it never runs (or leaks secrets) in CI.
 *
 * Run locally with:
 *   AGENTPANEL_E2E_CLIENT_ID=hcli_xxx AGENTPANEL_E2E_CLIENT_SECRET=hsc_xxx \
 *   pnpm exec vitest run packages/credentials/agentpanel-account/tests/agentpanel-account.integration.spec.ts
 */
import { Context } from '@deepseek-ai/cordis'
import { afterEach, expect, it } from 'vitest'
import { AgentPanelAccount } from '../src/index.ts'

const clientId = process.env.AGENTPANEL_E2E_CLIENT_ID
const clientSecret = process.env.AGENTPANEL_E2E_CLIENT_SECRET
const controlPlaneUrl = process.env.AGENTPANEL_E2E_CONTROL_PLANE_URL || 'http://127.0.0.1:9998/v1/harness'
const gatewayUrl = process.env.AGENTPANEL_E2E_GATEWAY_URL || 'http://127.0.0.1:9999'

const roots: Context[] = []
afterEach(async () => {
  await Promise.all(roots.splice(0).map((ctx) => ctx.fiber.dispose()))
})

const client = { version: '0.0.0-test', locale: 'en-US', timezoneOffsetSeconds: 0 }

async function activeLeases(): Promise<Array<Record<string, unknown>>> {
  const res = await fetch(`${controlPlaneUrl}/gateway/leases`, {
    headers: { authorization: `Bearer ${clientId}.${clientSecret}` },
  })
  const body = (await res.json()) as { data?: { items?: Array<Record<string, unknown>> } }
  return body.data?.items ?? []
}

it.skipIf(!clientId || !clientSecret)('issues, resolves, and revokes a real gateway lease', async () => {
  const ctx = new Context()
  roots.push(ctx)
  const svc = new AgentPanelAccount(ctx, {
    controlPlaneUrl,
    gatewayUrl,
    clientId,
    clientSecret,
    leaseTtlSeconds: 900,
  })

  expect((await svc.getState()).status).toBe('signed-out')

  // 签发前不应有激活租约
  expect(await activeLeases()).toHaveLength(0)

  await svc.startSignIn(client, 'http://127.0.0.1:8080', 'desktop')
  await new Promise((resolve) => setTimeout(resolve, 1500))

  expect((await svc.getState()).status).toBe('credential-stored')

  // resolveToken 仅对数据面网关 origin 返回续约key
  const key = await svc.resolveToken(`${gatewayUrl}/chat/completions`)
  expect(key).toMatch(/^dgw\./)

  // 网关侧确有激活租约
  const active = await activeLeases()
  expect(active.length).toBeGreaterThanOrEqual(1)
  expect(active.some((l) => l.status === 'active')).toBe(true)

  const after = await svc.signOut(client)
  expect(after.status).toBe('signed-out')

  // 吊销后控制面不再返回激活租约
  const afterRevoke = await activeLeases()
  expect(afterRevoke.some((l) => l.status === 'active')).toBe(false)
})
