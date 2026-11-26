/** Portal URLs carry only a single-use ticket, never a JWT or gateway key. */
import type { Context } from '@deepseek-ai/cordis'
import { expect, it } from 'vitest'
import { createInjected, portalUrl, safeExternalUrl } from '../src/client/DiscoverEntry.tsx'

it('builds a portal login URL with encoded ticket and redirect', () => {
  expect(portalUrl('http://127.0.0.1:9080/', 'abc+/=', '/dashboard?tab=1'))
    .toBe('http://127.0.0.1:9080/portal/login?ticket=abc%2B%2F%3D&redirect=%2Fdashboard%3Ftab%3D1')
})

it('never embeds gateway keys or JWTs', () => {
  const url = portalUrl('https://panel.example.com', 'dgw.1.secret', '/dashboard')
  expect(url).not.toContain('access_token')
  expect(url).toContain('ticket=dgw.1.secret')
})

it('only opens https or loopback http external links', () => {
  expect(safeExternalUrl('https://docs.example.com/a')).toBe('https://docs.example.com/a')
  expect(safeExternalUrl('http://127.0.0.1:9080/x')).toBe('http://127.0.0.1:9080/x')
  expect(safeExternalUrl('http://example.com')).toBeUndefined()
  expect(safeExternalUrl('javascript:alert(1)')).toBeUndefined()
  expect(safeExternalUrl('https://user:pass@example.com')).toBeUndefined()
})

it('renders the backend catalog and opens portal entries through a ticket', async () => {
  const calls: string[] = []
  const account = {
    getState: async () => ({ ok: true, value: { status: 'credential-stored', links: { panelUrl: 'http://127.0.0.1:9080' } } }),
    discoverApps: async () => ({
      ok: true,
      value: { ok: true, apps: [
        { id: 1, name: 'AgentPanel', description: 'console', iconText: 'AP', iconColor: null, openMode: 'portal', target: '/dashboard', sort: 1, isActive: true },
        { id: 2, name: 'Docs', description: 'help', iconText: 'DC', iconColor: null, openMode: 'link', target: 'https://docs.example.com/', sort: 2, isActive: true },
      ] },
    }),
    webTicket: async (target: string) => { calls.push(target); return { ok: true, value: { ok: true, ticket: 't'.repeat(43) } } },
  }
  const injected = createInjected({ remote: { account } } as unknown as Context)
  const apps = await injected.getApps()
  expect(apps.map((app) => app.name)).toEqual(['AgentPanel', 'Docs'])

  const ticketUrl = await injected.openApp(apps[0]!)
  expect(ticketUrl).toBe(portalUrl('http://127.0.0.1:9080', 't'.repeat(43), '/dashboard'))
  expect(calls).toEqual(['/dashboard'])
  expect(await injected.openApp(apps[1]!)).toBe('https://docs.example.com/')
})
