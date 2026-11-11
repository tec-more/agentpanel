/** Account settings registration and reconnecting Remote subscription. */
import type {} from '@deepseek-ai/dsh-client-product-analytics/client'
import type { TranscriptViewMode } from '@deepseek-ai/dsh-client-ui-chat/client'
import type { Context } from '@deepseek-ai/cordis'
import type {} from '@deepseek-ai/dsh-client-locale/client'
import type {} from '@deepseek-ai/dsh-client-ui-settings/client'
import type {} from '@deepseek-ai/dsh-client-ui-renderer/client'
import type {} from '@deepseek-ai/dsh-client-ui-theme/client'
import type {} from '@deepseek-ai/dsh-client-ui-chat/client'
import type {} from '@deepseek-ai/dsh-client-ui-layout/client'
import type {} from '@deepseek-ai/dsh-api-remote-access/client'
import type {} from '@deepseek-ai/dsh-api-remotes/client'
import type { AccountView, AccountDetails } from '@deepseek-ai/dsh-deepseek-account/types'
import type { OnboardingChange } from './onboarding-contract.ts'
import type { PlatformBridge } from './PlatformOverlay.tsx'
import { ContactConfig, CONTACT_CONFIG_GLOBAL } from '../contact-config.ts'
import { contactUrl } from './contact-url.ts'
import { authorizeUrlWithTheme } from './authorize-url.ts'
import { BrowserLogin } from './browser-login.ts'
import { AccountOnboarding } from './AccountOnboarding.tsx'
import { AccountPlatformHost, type AccountPlatformHostInjected } from './AccountPlatformHost.tsx'
import { AccountMenu } from './AccountMenu.tsx'
import { createPlatformPages, type PlatformPages } from './platform-pages.ts'
import { AccountSection, type AccountSnapshot, type AccountSectionInjected } from './AccountSection.tsx'
import { createBonusNoticeController } from './bonus-notices.ts'
import { accountClientMetadata } from './client-metadata.ts'
import { en, ja, es, fr, de, ru, pt, zh, type AccountKey } from './locales.ts'
import { AccountQuotaNotice, type AccountQuotaNoticeInjected } from './AccountQuotaNotice.tsx'
import { DESKTOP_ONBOARDING_NAMESPACE, type OnboardingSettings } from '../onboarding-settings.ts'
import { DesktopOnboardingController } from './onboarding-state.ts'
import { DesktopOnboardingEntry, type DesktopOnboardingInjected } from './DesktopOnboardingEntry.tsx'
import { readOnboardingApiKeyPresence } from './onboarding-credentials.ts'
import { refreshAfterReturn } from './account-refresh.ts'
import { AccountAvatarLoader } from './account-avatar.ts'
export type { AccountSectionInjected, AccountSectionProps } from './AccountSection.tsx'
export type { AccountMenuProps } from './AccountMenu.tsx'
export type { AccountSnapshot } from './AccountSection.tsx'
export type { AccountKey } from './locales.ts'

declare module '@deepseek-ai/dsh-client-ui-slots' {
  interface LocaleNamespaceMap { 'settings.account': AccountKey }
}

/** Services required by account settings. */
export const inject = ['slots', 'locale', 'remote', 'remote.account', 'remote.session', 'theme', 'configForms', 'remoteAccess']
/**
 * Replace the built-in product names in one locale dictionary with the deployment brand.
 * @param dictionary - complete locale dictionary for the account namespace.
 * @param brand - Host-provided display brand.
 * @returns a copy using the brand wherever the built-in DeepSeek names appear.
 */
function brandDictionary<T extends Record<string, string>>(dictionary: T, brand: string): T {
  return Object.fromEntries(Object.entries(dictionary).map(([key, value]) => [
    key, value.replaceAll('DeepSeek Harness', brand).replaceAll('DeepSeek', brand),
  ])) as T
}
/** Register account UI in Desktop and plain Web clients. @param ctx - client plugin context. */
export function apply(ctx: Context): void {
  const desktop = 'dshDesktop' in globalThis
  const t = ctx.locale.bind('settings.account')
  const page = globalThis as Partial<Record<typeof CONTACT_CONFIG_GLOBAL, unknown>>
  const config = ContactConfig(page[CONTACT_CONFIG_GLOBAL] ?? {})
  let snapshot: AccountSnapshot = {
    view: undefined, details: undefined, avatar: undefined, failed: false, loginVisible: false, desktopOnboardingVisible: desktop,
  }
  // Which sign-in surface this deployment offers: the agentpanel customer
  // email-code form or the upstream browser authorization flow. Resolved once
  // and cached; a failed probe keeps the browser dialog.
  let authModePromise: Promise<'customer' | 'browser'> | undefined
  const authMode = (): Promise<'customer' | 'browser'> => {
    authModePromise ??= ctx.remote.account.getAuthMode()
      .then(result => result.ok && result.value === 'customer' ? 'customer' : 'browser')
      .catch(() => 'browser')
    return authModePromise
  }
  void authMode().then((mode) => { publish({ ...snapshot, customerAuth: mode === 'customer' }) }).catch(() => undefined)
  // Desktop main opens the authorization page natively; a plain browser opens it in a tab it owns.
  const browser = new BrowserLogin(url => authorizeUrlWithTheme(url, ctx.theme.getTheme().active.colorScheme))
  ctx.effect(() => () => { browser.dispose() }, 'account: pending browser window')
  const listeners = new Set<() => void>()
  // Account copy follows the Host-provided deployment brand; dictionaries are
  // re-registered when the account view first carries (or drops) the brand.
  let registeredBrand: string | undefined
  let dictionariesRegistered = false
  let disposeDictionaries: (() => void) | undefined
  const registerDictionaries = (): void => {
    const brand = snapshot.view?.brandName?.trim()
    if (dictionariesRegistered && brand === registeredBrand) return
    dictionariesRegistered = true
    registeredBrand = brand
    disposeDictionaries?.()
    if (brand === undefined) {
      disposeDictionaries = ctx.locale.register('settings.account', { en, zh, ja, es, fr, de, ru, pt })
      return
    }
    disposeDictionaries = ctx.locale.register('settings.account', {
      en: brandDictionary(en, brand), zh: brandDictionary(zh, brand),
      ja: brandDictionary(ja, brand), es: brandDictionary(es, brand),
      fr: brandDictionary(fr, brand), de: brandDictionary(de, brand),
      ru: brandDictionary(ru, brand), pt: brandDictionary(pt, brand),
    })
  }
  const publish = (value: AccountSnapshot) => {
    snapshot = value
    registerDictionaries()
    for (const listener of listeners) listener()
  }
  registerDictionaries()
  ctx.effect(() => () => { disposeDictionaries?.(); disposeDictionaries = undefined }, 'account: dictionaries')
  const avatar = new AccountAvatarLoader((value) => { publish({ ...snapshot, avatar: value }) })
  ctx.effect(() => () => { avatar.dispose() }, 'account: profile picture lifetime')
  /** @returns the client identity for one account call, read at call time so it carries the language and zone in effect then. */
  const client = () => accountClientMetadata(ctx.locale.getSnapshot().active, process.env.DSH_CLIENT_VERSION)
  // The browser half of the notice lifecycle: reads when the account becomes
  // active and on an explicit refresh, and acknowledges an order only after its
  // card reports a presented frame. The Host owns which bonus is unnotified and
  // the server owns the copy.
  const notices = createBonusNoticeController({
    ackRetryDelayMs: config.bonusAckRetryDelayMs,
    ackRetryMaxDelayMs: config.bonusAckRetryMaxDelayMs,
    read: async () => {
      const result = await ctx.remote.account.getUnnotifiedBonuses(client())
      if (!result.ok) throw new Error('account bonus read failed')
      return result.value
    },
    acknowledge: async (accountId, orderId) => {
      const result = await ctx.remote.account.ackBonusNotified(accountId, orderId, client())
      if (!result.ok) throw new Error('account bonus acknowledgement failed')
      return result.value
    },
    publish: (notices) => {
      const { notices: _replaced, ...withoutNotices } = snapshot
      publish(notices.length === 0 ? withoutNotices : { ...withoutNotices, notices })
    },
  })
  ctx.effect(() => () => { notices.end() }, 'account: bonus notice lifetime')
  let revision = 0
  let refreshing: Promise<void> | undefined
  const refresh = (): Promise<void> => {
    if (snapshot.view?.status !== 'credential-stored') return Promise.resolve()
    if (refreshing !== undefined) return refreshing
    const generation = revision
    const read = async <K extends keyof AccountDetails>(field: K,
      query: () => Promise<AccountDetails[K] | null>) => {
      let value: AccountDetails[K] | null
      try { value = await query() }
      catch { value = { status: 'failed' } }
      // null means the provider has no such Platform concept (agentpanel); render
      // it as an unavailable field instead of leaving the card loading forever.
      // It is not a query failure, so it stays out of the error log.
      const resolved = value ?? ({ status: 'failed' } as AccountDetails[K])
      if (value !== null && resolved.status === 'failed') console.error('[deepseek-account] account read failed', { field })
      if (generation === revision) publish({ ...snapshot, details: { ...snapshot.details, [field]: resolved } })
    }
    const request = Promise.all([
      read('profile', async () => {
        const result = await ctx.remote.account.getProfile(client())
        if (!result.ok) throw new Error('account profile failed')
        if (generation === revision && result.value?.status === 'ready') avatar.setUrl(result.value.value.avatarUrl)
        return result.value
      }),
      read('balance', async () => {
        const result = await ctx.remote.account.getBalance(client())
        if (!result.ok) throw new Error('account balance failed')
        return result.value
      }),
    ]).then(() => undefined)
    refreshing = request
    void request.finally(() => { if (refreshing === request) refreshing = undefined })
    return request
  }
  ctx.effect(() => () => { revision++ }, 'account: details request lifetime')
  // The account stream, and the reads it starts, follow access to this host's account state.
  ctx.remoteAccess.whenAccess('account/watch', function* () {
    const stream = ctx.remote.$stream<AccountView>({
      name: 'account', open: signal => ctx.remote.account.watch(signal), ended: () => new Error('account stream ended'),
    })
    // Read across closures: the disposer ends this grant while the frame loop awaits.
    const grant = { ended: false }
    // Withdrawing access invalidates the reads this grant started, closes the
    // pending authorization tab, and clears the account view and the sign-in
    // dialog state, synchronously, so the next grant starts from no account
    // state. `notices.end()` disposes this generation's notice lifetime, which a
    // frame of this stream begins; the notice controller stays outside and
    // begins again under the next grant.
    yield () => {
      grant.ended = true
      revision++
      refreshing = undefined
      avatar.reset()
      browser.dispose()
      const { loginFailed: _loginFailed, ...current } = snapshot
      publish({ ...current, view: undefined, details: undefined, avatar: undefined, failed: false, loginVisible: false })
      notices.end()
      return stream.dispose()
    }
    void (async () => {
      for await (const frame of stream) {
        // A frame the stream delivered before the revocation is not this grant's to apply.
        if (grant.ended) return
        revision++
        refreshing = undefined
        avatar.reset()
        const initialize = frame.value.status === 'credential-stored' && frame.value.attempt?.phase === 'succeeded'
          && snapshot.view?.attempt?.phase !== 'succeeded'
        const { notices: previousNotices, ...previous } = snapshot
        publish({ ...previous, view: frame.value, details: undefined, avatar: undefined, failed: false,
          ...(frame.value.status === 'credential-stored' && previousNotices ? { notices: previousNotices } : {}) })
        browser.update(frame.value)
        frame.accept()
        if (frame.value.status === 'credential-stored') notices.begin()
        else notices.end()
        if (initialize) void (async () => {
          try {
            const initialized = await ctx.remote.session.initializeDefaultModel()
            if (!initialized.ok) console.error('[deepseek-account] default model initialization failed', { reason: 'refused' })
          } catch (_error) {
            console.error('[deepseek-account] default model initialization failed', { reason: 'disconnected' })
          }
        })()
        void refresh()
      }
    })().catch(() => { if (!grant.ended) publish({ ...snapshot, failed: true }) })
  })
  const nativePlatform = (globalThis as typeof globalThis & { dshPlatform?: PlatformBridge }).dshPlatform
  // One request channel for the single native Platform view. It always exists
  // so every entry can observe whether a page is showing; only a native bridge
  // lets an entry request one.
  const platformPages = createPlatformPages()
  ctx.effect(() => () => { platformPages.dispose() }, 'account: platform page request')
  // One account refresh: the recharge/bonus wallet and the unnotified-bonus read,
  // whichever surface asks — a Settings entry, or returning from top-up. Both
  // reads are independent, and a concurrent refresh shares the in-flight request.
  const refreshAccount = async (): Promise<void> => {
    avatar.retry()
    await Promise.all([refresh(), notices.refresh()])
  }
  /**
   * Narrow the shared channel to one surface's post-return read: only a viewer
   * returning from top-up re-reads, so a superseded page or a plugin teardown
   * never triggers account work.
   * @param reRead - that surface's read after a returned top-up page.
   * @returns the opener that surface injects.
   */
  const platformPageOpener = (reRead: () => Promise<void>): PlatformPages['open'] =>
    (page, onClose) => platformPages.open(page, (reason) => {
      onClose(reason)
      if (reason === 'returned' && page === 'top-up') void refreshAfterReturn(refreshing, reRead)
    })
  const operations: AccountSectionInjected = {
    avatarFailed: (value) => { avatar.failed(value) },
    subscribeSessionExpired: listener => ctx.remote.$on('deepseek-account/session-expired', listener),
    subscribeModelSignInRequired: listener => ctx.remote.$on('deepseek-account/model-sign-in-required', listener),
    ...nativePlatform === undefined ? {} : { openPlatformPage: platformPageOpener(refreshAccount) },
    refreshAccount,
    contactUs() {
      // Sample the account, build and environment before awaiting native information, so
      // a profile the read outlasts cannot replace the UID this click reported.
      const profile = snapshot.details?.profile
      const context = {
        uid: profile?.status === 'ready' ? profile.value.id : null,
        version: process.env.DSH_CLIENT_VERSION,
        width: window.screen.width, height: window.screen.height, pixelRatio: window.devicePixelRatio,
      }
      const openForm = (deviceInfo: string): void => {
        window.open(contactUrl(config, { ...context, deviceInfo }), '_blank', 'noopener,noreferrer')
      }
      const readDeviceInfo = (globalThis as typeof globalThis & {
        dshDesktop?: { deviceInfo?: () => Promise<string> }
      }).dshDesktop?.deviceInfo
      if (readDeviceInfo === undefined) {
        // A plain browser, or a Desktop bridge without the optional reader, reports the renderer user agent.
        openForm(navigator.userAgent)
        return
      }
      void (async () => {
        let deviceInfo = ''
        try { deviceInfo = await readDeviceInfo() }
        catch (_error) {
          // Native information is optional; the questionnaire opens without it.
        }
        openForm(deviceInfo)
      })()
    },
    showLogin(visible) { publish({ ...snapshot, loginVisible: visible }) },
    setOnboarding(active) { publish({ ...snapshot, onboarding: active }) },
    bonusNoticeShown(orderId) { notices.shown(orderId) },
    bonusNoticeDismissed(orderId) { notices.dismiss(orderId) },
    hooks: {
      account: {
        getSnapshot: () => snapshot,
        subscribe: (listener) => { listeners.add(listener); return () => { listeners.delete(listener) } },
      },
      theme: {
        getSnapshot: () => ctx.theme.getTheme(),
        subscribe: listener => ctx.on('theme/change', listener),
      },
    },
    async start() {
      publish({ ...snapshot, loginVisible: true, loginFailed: false })
      // Customer deployments open the email-code dialog; the browser flow only
      // starts an attempt when the browser dialog is actually in charge.
      if ((await authMode()) === 'customer') return
      const transport = (globalThis as typeof globalThis & {
        __DSH_TRANSPORT__?: { streamBaseUrl?: string }
      }).__DSH_TRANSPORT__
      const request = async () => {
        const result = await ctx.remote.account.startSignIn(client(),
          desktop && transport?.streamBaseUrl !== undefined ? new URL(transport.streamBaseUrl).origin : window.location.origin,
          desktop ? 'desktop' : 'web')
        if (!result.ok) throw new Error('account start failed')
        return result.value
      }
      try {
        if (desktop) await request()
        else await browser.start(request, () => snapshot.view)
      } catch (error) {
        publish({ ...snapshot, loginFailed: true })
        throw error
      }
    },
    async cancel(id) { const result = await ctx.remote.account.cancelSignIn(id); if (!result.ok) throw new Error('account cancel failed') },
    async sendCode(email, purpose) {
      const result = await ctx.remote.account.customerSendCode(email, purpose)
      if (!result.ok) throw new Error('account send-code failed')
      return result.value
    },
    async login(email, password) {
      const result = await ctx.remote.account.customerLogin(email, password)
      if (!result.ok) throw new Error('account login failed')
      return { ok: result.value.ok, message: result.value.message, signedIn: result.value.ok }
    },
    async register(email, code, password) {
      const result = await ctx.remote.account.customerRegister(email, code, password)
      if (!result.ok) throw new Error('account register failed')
      return { ok: result.value.ok, message: result.value.message, signedIn: result.value.ok }
    },
    async resetPassword(email, code, password) {
      const result = await ctx.remote.account.customerResetPassword(email, code, password)
      if (!result.ok) throw new Error('account password reset failed')
      return result.value
    },
    async hasRunningAccountTasks() {
      const result = await ctx.remote.account.hasRunningAccountTasks()
      if (!result.ok) throw new Error('account task query failed')
      return result.value
    },
    async signOut() {
      const result = await ctx.remote.account.signOut(client())
      if (result.ok) return
      throw result.error
    },
  }
  if (desktop) {
    const controller = new DesktopOnboardingController(
      ctx.configForms.get<OnboardingSettings>(DESKTOP_ONBOARDING_NAMESPACE),
      ctx.configForms.get<{ transcriptView?: TranscriptViewMode | null; performanceUsage: 'compact' | 'detailed' }>('ui-chat'),
      enabled => ctx.configForms.developerTools.setEnabled(enabled),
      operations.hooks.account,
      readOnboardingApiKeyPresence,
      ctx.configForms.describe(),
    )
    ctx.effect(() => () => { controller.dispose() }, 'account: desktop onboarding lifetime')
    ctx.effect(() => {
      const refreshCredentials = () => { controller.invalidateCredentials() }
      const disposers = [
        ctx.remote.$on('credentials/reference-updated', refreshCredentials),
        ctx.remote.$on('llm/adapters-updated', refreshCredentials),
        ctx.configForms.describe().subscribe(refreshCredentials),
      ]
      return () => { for (const dispose of disposers) dispose() }
    }, 'account: desktop credential readiness')
    ctx.slots.inject('shell.overlay', () => ctx.slots.register({
      name: 'shell.overlay', id: 'desktop-onboarding', locale: 'settings.account',
      inject: (): DesktopOnboardingInjected => ({
        hooks: { account: operations.hooks.account, onboarding: controller.state },
        setVisible: (visible: boolean) => {
          if (snapshot.desktopOnboardingVisible !== visible) publish({ ...snapshot, desktopOnboardingVisible: visible })
        },
        // Onboarding's recharge return re-reads profile and balance only.
        ...nativePlatform === undefined ? {} : { openPlatformPage: platformPageOpener(refresh) },
        update: (change: OnboardingChange) => controller.update(change),
        complete: (reason: 'completed' | 'skipped') => controller.complete(reason),
        retry: () => controller.retry(),
        track: (name, attributes) => ctx.get('productAnalytics')?.track(name, attributes),
      }),
    }, DesktopOnboardingEntry))
  }
  ctx.remoteAccess.whenAccess('account/watch', () => ctx.slots.inject('settings.models.sign-in', () => ctx.slots.register({
    name: 'settings.models.sign-in', locale: 'settings.account', inject: () => operations,
  }, AccountOnboarding)))
  ctx.remoteAccess.whenAccess('account/watch', () => ctx.slots.inject('shell.quota-notice', () => ctx.slots.register({
    name: 'shell.quota-notice', locale: 'settings.account',
    select: owner => owner.code === 'ACCOUNT_QUOTA' ? owner : null,
    inject: (): AccountQuotaNoticeInjected => ({
      hooks: { account: operations.hooks.account, platformPage: platformPages },
      ...nativePlatform === undefined ? {} : { openPlatformPage: platformPageOpener(refreshAccount) },
    }),
  }, AccountQuotaNotice)))
  if (nativePlatform !== undefined) {
    ctx.slots.inject('shell.overlay', () => ctx.slots.register({
      name: 'shell.overlay', id: 'account.platform-page', locale: 'settings.account',
      inject: (): AccountPlatformHostInjected => ({
        platform: nativePlatform, hooks: { page: platformPages },
        closePage: platformPages.close,
      }),
    }, AccountPlatformHost))
  }
  ctx.remoteAccess.whenAccess('account/watch', () => ctx.slots.inject('settings.launcher', () => ctx.slots.register({
    name: 'settings.launcher', locale: 'settings.account', inject: () => operations,
  }, AccountMenu)))
  ctx.remoteAccess.whenAccess('account/watch', () => ctx.slots.inject('settings.section', () => {
    let unregister: (() => void) | undefined
    const update = () => {
      if (snapshot.view?.status === 'credential-stored') {
        unregister ??= ctx.slots.register({
          name: 'settings.section', id: 'account', order: -10, label: () => t('nav'),
          locale: 'settings.account', inject: () => operations,
        }, AccountSection)
      } else {
        unregister?.()
        unregister = undefined
      }
    }
    listeners.add(update)
    update()
    return () => { listeners.delete(update); unregister?.() }
  }))
}
