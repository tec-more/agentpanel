/** Registers the AgentPanel discovery entry in the session header. */
import type { Context } from '@deepseek-ai/cordis'
import type {} from '@deepseek-ai/dsh-api-remotes/client'
import type { HostObservable } from '@deepseek-ai/dsh-client-ui-slots'
import type {} from '@deepseek-ai/dsh-client-locale/client'
import type {} from '@deepseek-ai/dsh-client-ui-conversation/client'
import type {} from '@deepseek-ai/dsh-client-ui-renderer/client'
import { createInjected, DiscoverEntry, portalUrl } from './DiscoverEntry.tsx'
import { BrandMark, BrandName } from './Brand.tsx'
import { HeroHeadline, HeroMark, HeroPreview } from './Hero.tsx'
import { createBrandStore } from './brand.ts'
import { de, en, es, fr, ja, NS, pt, ru, zh } from './locales.ts'

declare module '@deepseek-ai/dsh-client-ui-slots' {
  interface LocaleNamespaceMap {
    agentpanelEntry: keyof typeof en
  }
}

/** Remote services used by the entry. */
export const inject = ['slots', 'locale', 'remote', 'remote.account']

/** @param ctx - client context with slot, locale, and account Remote services. */
export function apply(ctx: Context): void {
  ctx.effect(() => ctx.locale.register(NS, { zh, en, ja, es, fr, de, ru, pt }), 'agentpanel-entry: dictionaries')

  // Operator-configurable sidebar identity. The store is shared by both brand
  // slots so one public-settings read updates the mark and the name together.
  const brand = createBrandStore(ctx)
  ctx.effect(() => () => { brand.dispose() }, 'agentpanel-entry: brand store')

  // Browser chrome is outside every React slot. The title flows through the
  // layout's root hook so session titles still append to the operator brand;
  // the two theme icons are patched in place and restored when settings clear.
  const productTitle: HostObservable<string | undefined> = {
    getSnapshot: () => brand.getSnapshot().productTitle,
    subscribe: listener => brand.subscribe(listener),
  }
  ctx.effect(() => ctx.slots.provideRoot({ hooks: { productTitle } }), 'agentpanel-entry: product title')
  const iconLinks = typeof document === 'undefined' ? []
    : [...document.querySelectorAll<HTMLLinkElement>('link[rel="icon"][type="image/svg+xml"]')]
  const originalIcons = new Map(iconLinks.map(link => [link, {
    href: link.getAttribute('href'),
    type: link.getAttribute('type'),
  }]))
  const applyFavicons = (): void => {
    const view = brand.getSnapshot()
    for (const link of iconLinks) {
      const dark = (link.getAttribute('media') ?? '').includes('dark')
      const href = dark ? view.faviconDark : view.faviconLight
      const original = originalIcons.get(link)
      if (href !== undefined) {
        link.setAttribute('href', href)
        link.removeAttribute('type')
      } else if (original !== undefined) {
        if (original.href === null) link.removeAttribute('href')
        else link.setAttribute('href', original.href)
        if (original.type === null) link.removeAttribute('type')
        else link.setAttribute('type', original.type)
      }
    }
  }
  applyFavicons()
  const disposeFavicons = brand.subscribe(applyFavicons)
  ctx.effect(() => () => { disposeFavicons() }, 'agentpanel-entry: favicon links')

  ctx.slots.inject('sidebar.brand.mark', () => ctx.slots.register({
    name: 'sidebar.brand.mark',
    id: 'agentpanel-brand-mark',
    order: 20,
    inject: () => ({ brand }),
  }, BrandMark))
  ctx.slots.inject('sidebar.brand.name', () => ctx.slots.register({
    name: 'sidebar.brand.name',
    id: 'agentpanel-brand-name',
    order: 20,
    inject: () => ({ brand }),
  }, BrandName))

  // Operator-configurable home Hero. The conversation namespace supplies the
  // localized fallback copy; a cleared setting hides the badge entirely.
  const conversationT = ctx.locale.bind('conversation')
  ctx.slots.inject('conversation.hero.brand.mark', () => ctx.slots.register({
    name: 'conversation.hero.brand.mark',
    id: 'agentpanel-hero-mark',
    order: 20,
    inject: () => ({ brand, t: conversationT }),
  }, HeroMark))
  ctx.slots.inject('conversation.hero.headline', () => ctx.slots.register({
    name: 'conversation.hero.headline',
    id: 'agentpanel-hero-headline',
    order: 20,
    inject: () => ({ brand, t: conversationT }),
  }, HeroHeadline))
  ctx.slots.inject('conversation.hero.preview', () => ctx.slots.register({
    name: 'conversation.hero.preview',
    id: 'agentpanel-hero-preview',
    order: 20,
    inject: () => ({ brand, t: conversationT }),
  }, HeroPreview))

  ctx.slots.inject(
    'conversation.session.header.actions',
    () => ctx.slots.register({
      name: 'conversation.session.header.actions',
      id: 'agentpanel-discover',
      order: 12,
      locale: NS,
      inject: () => createInjected(ctx),
    }, DiscoverEntry),
  )
  // Sidebar header's trailing row (beside the expand/collapse toggle) keeps
  // the entry reachable in the empty/new-session state, where the session
  // header is not rendered at all.
  ctx.slots.inject(
    'sidebar.header.action',
    () => ctx.slots.register({
      name: 'sidebar.header.action',
      id: 'agentpanel-discover-header',
      order: 20,
      locale: NS,
      inject: () => createInjected(ctx),
    }, DiscoverEntry),
  )
}

export { portalUrl }
