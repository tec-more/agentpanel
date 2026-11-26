/** Discover-app style header action backed by the operator-configured catalog. */
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { Context } from '@deepseek-ai/cordis'
import type {} from '@deepseek-ai/dsh-api-remotes/client'
import {
  Button,
  IconChevronDownOutlineRegular,
  Modal,
  useDismissOnOutsidePointer,
} from '@deepseek-ai/dsh-client-ui-primitives'
import type { InjectFace, PropsLocale, PropsRuntime } from '@deepseek-ai/dsh-client-ui-slots'
import type {} from '@deepseek-ai/dsh-client-ui-conversation/client'
import type {} from '@deepseek-ai/dsh-client-ui-sidebar/client'
import { NS } from './locales.ts'
import css from './DiscoverEntry.module.css'

/** Display-only projection of one backend catalog row. */
export interface DiscoverAppView {
  readonly id: number
  readonly name: string
  readonly description: string
  readonly iconText: string
  readonly iconColor: string | null
  readonly openMode: 'portal' | 'link'
  readonly target: string
}

/** Operations supplied by the client plugin: Host Remote calls and safe navigation. */
export interface DiscoverEntryInjected {
  /** Portal base URL from the account links (safe to expose without a credential). */
  getPortalUrl: () => Promise<string | undefined>
  /** Whether a customer credential is stored, enabling one-time portal tickets. */
  isSignedIn: () => Promise<boolean>
  /** Load the enabled catalog rows from AgentPanel; rejects with a user-facing message. */
  getApps: () => Promise<DiscoverAppView[]>
  /** Resolve an app to a URL safe to hand to the system browser, or undefined. */
  openApp: (app: DiscoverAppView) => Promise<string | undefined>
  /** Open Harness's own sign-in dialog (settings-account surface). */
  openHarnessSignIn: () => Promise<void>
}

export type DiscoverEntryProps =
  (PropsRuntime<'conversation.session.header.actions'> | PropsRuntime<'sidebar.header.action'>)
  & PropsLocale<typeof NS>
  & InjectFace<DiscoverEntryInjected>

interface PanelPosition {
  top: number
  left: number
}

/** @param props - slot runtime, localized copy, and injected catalog operations. @returns the header action. */
export function DiscoverEntry({ t, getPortalUrl, isSignedIn, getApps, openApp, openHarnessSignIn }: DiscoverEntryProps) {
  const [open, setOpen] = useState(false)
  const [portalUrl, setPortalUrl] = useState<string | undefined>(undefined)
  const [signedIn, setSignedIn] = useState(false)
  const [apps, setApps] = useState<readonly DiscoverAppView[]>([])
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const [loginPromptOpen, setLoginPromptOpen] = useState(false)
  const [position, setPosition] = useState<PanelPosition>({ top: 0, left: 0 })
  const wrapRef = useRef<HTMLSpanElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const [query, setQuery] = useState('')

  useEffect(() => {
    let live = true
    void Promise.all([getPortalUrl(), isSignedIn()]).then(([url, signed]) => {
      if (live) { setPortalUrl(url); setSignedIn(signed) }
    }).catch(() => undefined)
    return () => { live = false }
  }, [getPortalUrl, isSignedIn])

  useDismissOnOutsidePointer(wrapRef, open, setOpen, panelRef)

  const loadApps = (): void => {
    setLoading(true)
    setStatus('')
    // The catalog itself is read with a customer JWT. When signed out (or the
    // read fails) we still show the operator-branded card, with no error text:
    // the account service only gates the portal ticket, not the app description.
    const fallback: DiscoverAppView[] = [{
      id: 0,
      name: t('app.agentpanel'),
      description: t('app.agentpanel.desc'),
      iconText: 'AP',
      iconColor: '#4f46e5',
      openMode: 'portal',
      target: '/dashboard',
    }]
    if (!signedIn) {
      setApps(fallback)
      setLoading(false)
      return
    }
    void getApps()
      .then((rows) => setApps(rows.length > 0 ? rows : fallback))
      .catch(() => setApps(fallback))
      .finally(() => setLoading(false))
  }

  const toggle = (): void => {
    if (open) { setOpen(false); return }
    const rect = wrapRef.current?.getBoundingClientRect()
    const width = 292
    const left = rect === undefined ? 0 : Math.min(rect.left, Math.max(8, window.innerWidth - width - 8))
    setPosition({ top: rect === undefined ? 0 : rect.bottom + 6, left })
    setStatus('')
    setOpen(true)
    loadApps()
  }

  const openAppDirect = async (app: DiscoverAppView): Promise<void> => {
    setBusy(true)
    setStatus(t('state.opening'))
    // A missing portal URL means no usable customer credential (stale in-memory
    // lease, signed-out, or ticket service failure). Always fall back to the
    // sign-in hint instead of a dead red error — the user's next step is login.
    const needSignIn = (): void => {
      setStatus('')
      setOpen(false)
      if (app.openMode === 'portal') setLoginPromptOpen(true)
      else setStatus(t('state.failed'))
    }
    try {
      const url = await openApp(app)
      if (url === undefined) { needSignIn(); return }
      window.open(url, '_blank', 'noopener,noreferrer')
      setOpen(false)
      setStatus('')
    } catch {
      needSignIn()
    } finally {
      setBusy(false)
    }
  }

  const activate = async (app: DiscoverAppView): Promise<void> => {
    // Re-check the live account state at click time. The mount-time `signedIn`
    // snapshot goes stale after the user signs in through Harness's dialog in
    // this same page session, which would otherwise keep prompting to sign in.
    let liveSignedIn = signedIn
    try { liveSignedIn = await isSignedIn() } catch { /* fall back to snapshot */ }
    setSignedIn(liveSignedIn)
    // A portal entry needs a single-use ticket minted from the Harness customer
    // credential. Signed out: first show a plain sign-in hint; its button opens
    // Harness's own sign-in dialog, where the user logs in or registers.
    if (!liveSignedIn && app.openMode === 'portal') {
      setStatus('')
      setOpen(false)
      setLoginPromptOpen(true)
      return
    }
    await openAppDirect(app)
  }

  const goToHarnessSignIn = async (): Promise<void> => {
    setLoginPromptOpen(false)
    try { await openHarnessSignIn() } catch { /* the account surface reports its own errors */ }
  }

  const needle = query.trim().toLowerCase()
  const visible = apps.filter((app) => needle === ''
    || app.name.toLowerCase().includes(needle)
    || app.description.toLowerCase().includes(needle))

  return <>
    <span className={css.wrap} ref={wrapRef}>
      <button type="button" className={css.trigger} aria-label={t('button.aria')} aria-expanded={open}
        onClick={toggle}>
        {t('button.label')}
        <IconChevronDownOutlineRegular size={12} />
      </button>
    </span>
    {open && createPortal(
      <div className={css.panel} ref={panelRef} style={{ top: position.top, left: position.left }}>
        <input className={css.search} value={query} onChange={(event) => setQuery(event.target.value)}
          placeholder={t('panel.search')} aria-label={t('panel.search')} />
        <div className={css.sectionTitle}>{t('panel.frequent')}</div>
        {loading && <div className={css.status}>{t('state.loading')}</div>}
        {!loading && visible.length === 0 && status === '' && <div className={css.status}>{t('state.empty')}</div>}
        <div className={css.cards}>
          {visible.map((app) => <button type="button" className={css.card} key={app.id}
            disabled={busy} onClick={() => { void activate(app) }}>
            <span className={css.icon} aria-hidden="true"
              style={app.iconColor === null ? undefined : { background: app.iconColor }}>
              {app.iconText === '' ? 'AP' : app.iconText}
            </span>
            <span className={css.cardName}>{app.name}</span>
            <span className={css.cardDesc}>{app.description}</span>
          </button>)}
        </div>
        <div className={`${css.status} ${status === '' ? '' : css.statusError}`} role="status">{status}</div>
      </div>,
      document.body,
    )}
    <Modal
      open={loginPromptOpen}
      title={t('login.title')}
      closeLabel={t('login.close')}
      description={t('login.desc')}
      onClose={() => setLoginPromptOpen(false)}
      footer={<>
        <Button onClick={() => setLoginPromptOpen(false)}>{t('login.cancel')}</Button>
        <Button variant="primary" data-modal-autofocus onClick={() => { void goToHarnessSignIn() }}>
          {t('login.action')}
        </Button>
      </>}
    />
  </>
}

/** Build a portal URL carrying only a single-use ticket, never a JWT or gateway key. */
export function portalUrl(base: string, ticket: string, redirectTo: string): string {
  const origin = base.replace(/\/+$/, '')
  return `${origin}/portal/login?ticket=${encodeURIComponent(ticket)}&redirect=${encodeURIComponent(redirectTo)}`
}

/** Re-check the backend-provided external URL before handing it to the browser. */
export function safeExternalUrl(target: string): string | undefined {
  try {
    const url = new URL(target)
    const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
    if (url.username || url.password || !(url.protocol === 'https:' || (loopback && url.protocol === 'http:'))) return undefined
    return target
  } catch {
    return undefined
  }
}

/** Helper kept separate so unit tests can exercise the injected callbacks without React. */
export function createInjected(ctx: Context): DiscoverEntryInjected {
  return {
    getPortalUrl: async () => {
      const state = await ctx.remote.account.getState()
      if (!state.ok) return undefined
      return state.value.links.panelUrl || undefined
    },
    isSignedIn: async () => {
      const state = await ctx.remote.account.getState()
      return state.ok && state.value.status === 'credential-stored'
    },
    getApps: async () => {
      const result = await ctx.remote.account.discoverApps()
      if (!result.ok) throw new Error(result.error.message)
      const outcome = result.value
      if (!outcome.ok) throw new Error(outcome.message === '' ? undefined : outcome.message)
      return outcome.apps.map((app) => ({
        id: app.id,
        name: app.name,
        description: app.description,
        iconText: app.iconText,
        iconColor: app.iconColor,
        openMode: app.openMode,
        target: app.target,
      }))
    },
    openApp: async (app) => {
      if (app.openMode === 'link') return safeExternalUrl(app.target)
      const state = await ctx.remote.account.getState()
      if (!state.ok || state.value.status !== 'credential-stored') return undefined
      const base = state.value.links.panelUrl
      if (base === undefined || base === '') return undefined
      const result = await ctx.remote.account.webTicket(app.target)
      if (!result.ok || result.value.ok !== true || result.value.ticket === undefined) return undefined
      return portalUrl(base, result.value.ticket, app.target)
    },
    openHarnessSignIn: async () => {
      // The settings-account plugin registers its operations on this slot. Its
      // start() flips loginVisible, which mounts Harness's own sign-in/register
      // dialog exactly as the account menu does.
      const entries = ctx.slots.entries('settings.models.sign-in')
      for (const entry of entries) {
        const operations = entry.inject?.() as { start?: () => Promise<void> } | undefined
        if (operations?.start !== undefined) { await operations.start(); return }
      }
    },
  }
}
