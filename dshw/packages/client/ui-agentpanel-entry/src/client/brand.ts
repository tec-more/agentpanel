/** Operator-branded sidebar identity backed by AgentPanel public system settings. */
import type { Context } from '@deepseek-ai/cordis'
import type {} from '@deepseek-ai/dsh-api-remotes/client'

/** Display-safe brand projection consumed by the sidebar and home-hero slots. */
export interface BrandView {
  readonly name: string
  readonly logo: string | undefined
  readonly heroHeadline: string | undefined
  readonly heroBeta: string | undefined
  readonly heroLogo: string | undefined
  /** Browser-tab product title; falls back to the sidebar brand name. */
  readonly productTitle: string | undefined
  /** Light/dark favicon URLs; fall back to the brand logo. */
  readonly faviconLight: string | undefined
  readonly faviconDark: string | undefined
}

/** Shared store plus lifecycle used by both brand slot occupants. */
export interface BrandStore {
  getSnapshot(): BrandView
  subscribe(listener: () => void): () => void
  refresh(force?: boolean): Promise<void>
  dispose(): void
}

/** Resolve an operator-supplied logo URL without accepting credentials or script URLs. */
export function resolveLogo(raw: unknown, base: string): string | undefined {
  if (typeof raw !== 'string' || raw.trim() === '') return undefined
  try {
    const origin = new URL(base).origin
    const url = new URL(raw.trim(), origin)
    if (url.username !== '' || url.password !== '') return undefined
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return undefined
    return url.href
  } catch {
    return undefined
  }
}

/** @param ctx - client context exposing the account Remote. @returns a subscribable brand store. */
export function createBrandStore(ctx: Context): BrandStore {
  let snapshot: BrandView = {
    name: 'AgentPanel', logo: undefined, heroHeadline: undefined, heroBeta: undefined, heroLogo: undefined,
    productTitle: undefined, faviconLight: undefined, faviconDark: undefined,
  }
  let lastFetch = 0
  let inFlight: Promise<void> | undefined
  const listeners = new Set<() => void>()

  const publish = (next: BrandView): void => {
    if (next.name === snapshot.name && next.logo === snapshot.logo
      && next.heroHeadline === snapshot.heroHeadline && next.heroBeta === snapshot.heroBeta
      && next.heroLogo === snapshot.heroLogo && next.productTitle === snapshot.productTitle
      && next.faviconLight === snapshot.faviconLight && next.faviconDark === snapshot.faviconDark) return
    snapshot = next
    for (const listener of listeners) listener()
  }

  const load = async (): Promise<void> => {
    const state = await ctx.remote.account.getState()
    const base = state.ok ? state.value.links.panelUrl : undefined
    const fallbackName = state.ok && typeof state.value.brandName === 'string' && state.value.brandName !== ''
      ? state.value.brandName
      : 'AgentPanel'
    if (base === undefined || base === '') {
      publish({
        name: fallbackName, logo: undefined, heroHeadline: undefined, heroBeta: undefined, heroLogo: undefined,
        productTitle: fallbackName, faviconLight: undefined, faviconDark: undefined,
      })
      return
    }
    const response = await fetch(`${base.replace(/\/+$/, '')}/v1/system-settings/public`, {
      cache: 'no-store',
    })
    if (!response.ok) throw new Error(String(response.status))
    const payload = await response.json() as { data?: Record<string, unknown> }
    const data = payload?.data ?? {}
    const configuredName = data['system_name']
    const name = typeof configuredName === 'string' && configuredName.trim() !== ''
      ? configuredName.trim()
      : fallbackName
    const text = (key: string): string | undefined => {
      const raw = data[key]
      return typeof raw === 'string' && raw.trim() !== '' ? raw.trim() : undefined
    }
    // `hero_beta` has a different empty-value contract from other text settings:
    // clearing it in the admin panel means "hide the badge", not "use the default".
    const rawBeta = data['hero_beta']
    const heroBeta = typeof rawBeta === 'string' ? rawBeta.trim() : undefined
    const logo = resolveLogo(data['system_logo'], base)
    const faviconLight = resolveLogo(data['favicon_light'], base) ?? logo
    const faviconDark = resolveLogo(data['favicon_dark'], base) ?? faviconLight
    publish({
      name,
      logo,
      heroHeadline: text('hero_headline'),
      heroBeta,
      heroLogo: resolveLogo(data['hero_logo'], base),
      productTitle: text('browser_title') ?? name,
      faviconLight,
      faviconDark,
    })
  }

  const refresh = async (force = false): Promise<void> => {
    if (!force && Date.now() - lastFetch < 30_000) return
    if (inFlight !== undefined) return inFlight
    lastFetch = Date.now()
    inFlight = load()
      .catch(() => undefined)
      .finally(() => { inFlight = undefined })
    return inFlight
  }

  const onVisible = (): void => {
    if (typeof document !== 'undefined' && document.visibilityState === 'visible') void refresh(true)
  }
  if (typeof window !== 'undefined') {
    document.addEventListener('visibilitychange', onVisible)
  }

  return {
    getSnapshot: () => snapshot,
    subscribe(listener) {
      listeners.add(listener)
      return () => { listeners.delete(listener) }
    },
    refresh,
    dispose() {
      if (typeof window !== 'undefined') document.removeEventListener('visibilitychange', onVisible)
      listeners.clear()
    },
  }
}
