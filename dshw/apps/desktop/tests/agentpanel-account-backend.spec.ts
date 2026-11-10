/**
 * Desktop agentpanel account backend: lease issuance / persistence / revocation
 * against the gateway contract. `fetch` is mocked; the lease file is written to a
 * temp dir so no live gateway or Electron runtime is required.
 */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { agentpanelAccountBackend } from '../src/agentpanel-account-backend.ts'

function leaseResponse(): Record<string, unknown> {
  return {
    code: 0,
    msg: 'ok',
    data: {
      lease_id: 'L1',
      virtual_key: 'dgw.L1.s',
      expires_at: new Date(Date.now() + 900_000).toISOString(),
      ttl_seconds: 900,
      renew_after_seconds: 720,
    },
    status_code: 200,
    success: true,
  }
}

let dir: string
beforeEach(() => {
  dir = mkdtempSync(path.join(tmpdir(), 'dsh-ap-'))
  vi.stubGlobal('fetch', vi.fn())
})
afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  rmSync(dir, { recursive: true, force: true })
})

const config = (): Record<string, unknown> => ({
  gatewayUrl: 'http://gw.test',
  controlPlaneUrl: 'http://cp.test/v1/harness',
  clientToken: 'cid.csec',
  storageDir: dir,
  renewCheckMs: 10,
})

it('start issues a lease on the control plane, reports credential-stored, and persists it', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => leaseResponse() } as Response)
  vi.stubGlobal('fetch', fetchMock)
  const backend = agentpanelAccountBackend(config())

  expect((await backend.state()).status).toBe('signed-out')
  const view = await backend.start({})
  expect(view.status).toBe('credential-stored')

  expect(fetchMock).toHaveBeenCalledTimes(1)
  const [url, opts] = fetchMock.mock.calls[0] as [string, RequestInit]
  expect(String(url)).toBe('http://cp.test/v1/harness/gateway/leases')
  expect((opts.headers as Record<string, string>).Authorization).toBe('Bearer cid.csec')

  const file = path.join(dir, 'account.json')
  expect(existsSync(file)).toBe(true)
  const stored = JSON.parse(readFileSync(file, 'utf8')) as { virtualKey: string }
  expect(stored.virtualKey).toBe('dgw.L1.s')
})

it('signOut revokes the lease and clears the persisted credential', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => leaseResponse() } as Response)
  vi.stubGlobal('fetch', fetchMock)
  const backend = agentpanelAccountBackend(config())

  await backend.start({})
  const view = await backend.signOut({})
  expect(view.status).toBe('signed-out')

  expect(existsSync(path.join(dir, 'account.json'))).toBe(false)
  const revoke = fetchMock.mock.calls
    .find((call) => String(call[0]).includes('/gateway/leases/') && (call[1] as RequestInit).method === 'DELETE')
  expect(revoke).toBeTruthy()
  expect(String(revoke![0])).toBe('http://cp.test/v1/harness/gateway/leases/L1')
})
