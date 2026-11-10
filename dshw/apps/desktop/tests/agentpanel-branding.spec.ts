/** The branding resolver reads the backend project name (config.conf [app] name) without ever blocking startup. */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { resolveAgentPanelProjectName } from '../src/agentpanel-branding.ts'

const okBody = (data: unknown) => ({
  ok: true,
  json: async () => ({ success: true, data }),
}) as Response

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
})

describe('resolveAgentPanelProjectName', () => {
  it('prefers an explicit DSH_AGENTPANEL_PROJECT_NAME over the control plane', async () => {
    vi.stubEnv('DSH_AGENTPANEL_PROJECT_NAME', '  Custom Panel  ')
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    expect(await resolveAgentPanelProjectName()).toBe('Custom Panel')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('reads app_name from the control-plane system-config', async () => {
    vi.stubEnv('AGENTPANEL_CUSTOMER_URL', 'http://127.0.0.1:9998/v1/customer')
    const fetch = vi.fn(async (input: unknown) => {
      expect(String(input)).toBe('http://127.0.0.1:9998/v1/common/system-config')
      return okBody({ app_name: 'AgentPanel' })
    })
    vi.stubGlobal('fetch', fetch)
    expect(await resolveAgentPanelProjectName()).toBe('AgentPanel')
  })

  it('falls back to the default customer URL origin', async () => {
    const fetch = vi.fn(async (input: unknown) => {
      expect(String(input)).toBe('http://127.0.0.1:9998/v1/common/system-config')
      return okBody({ app_name: 'AgentPanel' })
    })
    vi.stubGlobal('fetch', fetch)
    expect(await resolveAgentPanelProjectName()).toBe('AgentPanel')
  })

  it.each([
    ['an HTTP error', async () => ({ ok: false } as Response)],
    ['a success=false envelope', async () => ({ ok: true, json: async () => ({ success: false }) } as Response)],
    ['a missing app_name', async () => okBody({ app_version: 'v0.1.0' })],
    ['an empty app_name', async () => okBody({ app_name: '   ' })],
    ['an oversized app_name', async () => okBody({ app_name: 'x'.repeat(65) })],
    ['a rejected request', async () => { throw new Error('backend offline') }],
  ] satisfies [string, () => Promise<Response>][])('returns undefined on %s', async (_label, reply) => {
    vi.stubGlobal('fetch', vi.fn(reply))
    await expect(resolveAgentPanelProjectName()).resolves.toBeUndefined()
  })

  it('returns undefined when the customer URL cannot be parsed', async () => {
    vi.stubEnv('AGENTPANEL_CUSTOMER_URL', 'not a url')
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    expect(await resolveAgentPanelProjectName()).toBeUndefined()
    expect(fetch).not.toHaveBeenCalled()
  })
})
