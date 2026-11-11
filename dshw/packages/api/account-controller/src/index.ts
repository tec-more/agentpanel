/** Authenticated Remote operations for account UI consumers. */
import { Context } from '@deepseek-ai/cordis'
import { Remote, TypertRemoteService } from '@deepseek-ai/dsh-typert-protocol'
import { isRunningAccountTask } from '@deepseek-ai/dsh-deepseek-account'
import type {} from '@deepseek-ai/dsh-agent'
import type { AccountBonusBatch, AccountBonusOrderId, AccountClientMetadata, AccountDetails, AccountUserId } from '@deepseek-ai/dsh-deepseek-account/types'
import type { AgentPanelAccount } from '@deepseek-ai/dsh-agentpanel-account'
import type { CustomerAuthOutcome, CustomerCodeOutcome, CustomerCodePurpose } from '@deepseek-ai/dsh-agentpanel-account/types'
import type { AccountView, ImportedLeaseSession, SignInAttemptId } from './types.ts'

declare module '@deepseek-ai/cordis' {
  interface Context {
    /** agentpanel gateway-lease account backend. */
    agentpanelAccount: AgentPanelAccount
  }
  interface Events {
    /** Server rejection or renewal failure removed the current lease credential. */
    'agentpanel-account/session-expired'(): void
    /** Local grant removal has completed. */
    'agentpanel-account/signed-out'(): void
  }
}

/** Account commands and reconnect-safe state stream. */
export class AccountController extends TypertRemoteService {
  static inject = ['agentpanelAccount', 'agents']
  /** @param ctx - Host with the account provider mounted. */
  constructor(ctx: Context) { super(ctx, 'accountController', { namespace: 'account' }) }
  /**
   * Read the safe account projection.
   * @returns current account and attempt state.
   */
  @Remote
  getState(): Promise<AccountView> { return this.ctx.agentpanelAccount.getState() }
  /**
   * Query display-safe Platform profile data.
   * @param client - identity of the requesting UI; the Host derives Platform request headers from it.
   * @returns profile outcome, or null when the account grant is absent or changed.
   */
  @Remote
  getProfile(client: AccountClientMetadata): Promise<AccountDetails['profile'] | null> {
    return this.ctx.agentpanelAccount.getProfile(client)
  }
  /**
   * Query Platform recharge-wallet balances.
   * @param client - identity of the requesting UI; the Host derives Platform request headers from it.
   * @returns balance outcome, or null when the account grant is absent or changed.
   */
  @Remote
  getBalance(client: AccountClientMetadata): Promise<AccountDetails['balance'] | null> {
    return this.ctx.agentpanelAccount.getBalance(client)
  }
  /**
   * Query the granted bonuses Platform has not yet recorded as displayed.
   * @param client - identity of the requesting UI; its language selects the server-authored message.
   * @returns bonuses with their account, or null when the account grant is absent or changed.
   */
  @Remote
  getUnnotifiedBonuses(client: AccountClientMetadata): Promise<AccountBonusBatch | null> {
    return this.ctx.agentpanelAccount.getUnnotifiedBonuses(client)
  }
  /**
   * Record one displayed bonus as notified for the account it belongs to.
   * @param accountId - account the notification was read for.
   * @param orderId - granted bonus order the user saw.
   * @param client - identity of the requesting UI; the Host derives Platform request headers from it.
   * @returns true once Platform records the acknowledgement; false when the account is absent or changed.
   */
  @Remote
  ackBonusNotified(accountId: AccountUserId, orderId: AccountBonusOrderId, client: AccountClientMetadata): Promise<boolean> {
    return this.ctx.agentpanelAccount.ackBonusNotified(accountId, orderId, client)
  }
  /**
   * Begin browser sign-in.
   * @param client - identity of the requesting UI, captured by a new attempt.
   * @param callbackOrigin - browser-accessible loopback HTTP origin.
   * @param loginSource - initiating UI, used to return from a failed exchange.
   * @returns a new or already-active login attempt.
   */
  @Remote
  startSignIn(client: AccountClientMetadata, callbackOrigin: string, loginSource: 'web' | 'desktop'): Promise<AccountView> {
    return this.ctx.agentpanelAccount.startSignIn(client, callbackOrigin, loginSource)
  }
  /**
   * Cancel the named local attempt.
   * @param attemptId - attempt to cancel.
   * @returns settled cancellation or commit state.
   */
  @Remote
  cancelSignIn(attemptId: SignInAttemptId): Promise<AccountView> { return this.ctx.agentpanelAccount.cancelSignIn(attemptId) }
  /**
   * Inspect the latest logged request providers of running tasks, including tools and retries.
   * @returns whether running work has a latest request context on the account route.
   */
  @Remote
  hasRunningAccountTasks(): boolean {
    return this.ctx.agents.list().some(isRunningAccountTask)
  }
  /**
   * Remove the local account grant and revoke it through Platform in the background, without deleting API keys.
   * @param client - identity of the requesting UI, captured for the background revocation retries.
   * @returns state after removing the local account grant.
   */
  @Remote
  signOut(client: AccountClientMetadata): Promise<AccountView> { return this.ctx.agentpanelAccount.signOut(client) }
  /**
   * Adopt the lease issued by the desktop customer sign-in flow. The desktop
   * owns renewal and revocation; this only mirrors the session so workspace
   * surfaces report signed-in and gateway requests carry the key.
   * @param session - lease snapshot from the desktop account store.
   * @returns account state after adopting the session.
   */
  @Remote
  importSession(session: ImportedLeaseSession): Promise<AccountView> {
    return this.ctx.agentpanelAccount.importSession(session)
  }
  /**
   * Drop the previously imported desktop session locally, for example when the
   * desktop account store reports signed-out or an expired credential.
   * @returns account state after clearing the session.
   */
  @Remote
  clearSession(): Promise<AccountView> { return this.ctx.agentpanelAccount.clearSession() }
  /**
   * Report which sign-in surface the deployment offers: the agentpanel customer
   * email-code form or the upstream browser authorization flow.
   * @returns the active sign-in mode.
   */
  @Remote
  getAuthMode(): Promise<'customer' | 'browser'> { return this.ctx.agentpanelAccount.getAuthMode() }
  /**
   * Request a customer verification mail.
   * @param email - customer mailbox.
   * @param purpose - code purpose mirrored by the control plane's `type` field.
   * @returns whether the mail was accepted, with a user-facing message on failure.
   */
  @Remote
  customerSendCode(email: string, purpose: CustomerCodePurpose): Promise<CustomerCodeOutcome> {
    return this.ctx.agentpanelAccount.sendCode(email, purpose)
  }
  /**
   * Register a customer account with an email verification code and a password.
   * @param email - customer mailbox.
   * @param code - 6-digit verification code from the mail.
   * @param password - account password (at least 6 characters).
   * @returns the signed-in account state, or a user-facing failure message.
   */
  @Remote
  customerRegister(email: string, code: string, password: string): Promise<CustomerAuthOutcome> {
    return this.ctx.agentpanelAccount.register(email, code, password)
  }
  /**
   * Sign in with the customer email and password.
   * @param email - customer mailbox.
   * @param password - account password.
   * @returns the signed-in account state, or a user-facing failure message.
   */
  @Remote
  customerLogin(email: string, password: string): Promise<CustomerAuthOutcome> {
    return this.ctx.agentpanelAccount.login(email, password)
  }
  /**
   * Sign in with the customer email and a verification code.
   * @param email - customer mailbox.
   * @param code - 6-digit verification code from the mail.
   * @returns the signed-in account state, or a user-facing failure message.
   */
  @Remote
  customerLoginCode(email: string, code: string): Promise<CustomerAuthOutcome> {
    return this.ctx.agentpanelAccount.loginCode(email, code)
  }
  /**
   * Reset a customer password with an email verification code.
   * @param email - customer mailbox.
   * @param code - 6-digit verification code from the mail.
   * @param password - new account password (at least 6 characters).
   * @returns whether the reset was accepted, with a user-facing message on failure.
   */
  @Remote
  customerResetPassword(email: string, code: string, password: string): Promise<CustomerCodeOutcome> {
    return this.ctx.agentpanelAccount.resetPassword(email, code, password)
  }
  /**
   * Subscribe to credential expiry without replaying prior notifications.
   * @param signal - stream lifetime.
   * @returns notifications emitted while subscribed.
   */
  @Remote({ mode: 'stream' })
  async *watchExpiry(signal: AbortSignal): AsyncIterable<'session-expired'> {
    let pending = 0
    let wake: (() => void) | undefined
    const stop = this.ctx.on('agentpanel-account/session-expired', () => { pending++; wake?.() })
    const abort = (): void => { wake?.() }
    signal.addEventListener('abort', abort, { once: true })
    try {
      while (!signal.aborted) {
        if (pending > 0) { pending--; yield 'session-expired'; continue }
        await new Promise<void>((resolve) => { wake = resolve })
      }
    } finally {
      stop()
      signal.removeEventListener('abort', abort)
    }
  }
  /**
   * Stream the safe account projection.
   * @param signal - stream lifetime.
   * @returns initial snapshot and subsequent changes.
   */
  @Remote({ mode: 'stream' })
  watch(signal: AbortSignal): AsyncIterable<AccountView> { return this.ctx.agentpanelAccount.watch(signal) }
}
export default AccountController
