/** Account Remote boundary values shared by the Host account controller. */
import type { AccountView } from '@deepseek-ai/dsh-deepseek-account/types'

/**
 * Lease snapshot adopted from the desktop customer sign-in flow.
 *
 * The desktop main process authenticates the customer (email/password or email
 * code), exchanges the customer JWT for a `cus`-bound gateway lease, and keeps
 * renewing it. The Host process only needs the key so `resolveToken` can inject
 * it into gateway requests; renewal and revocation stay with the desktop.
 */
export interface ImportedLeaseSession {
  /** Control-plane lease id. */
  readonly leaseId: string
  /** Gateway virtual key (`dgw.<lease_id>.<secret>`). */
  readonly virtualKey: string
  /** Lease expiry in epoch milliseconds. */
  readonly expiresAtMs: number
  /** Seconds before expiry the desktop renews (informational). */
  readonly renewAfterSeconds?: number
}

/** Purpose of a customer email verification code, mirrored by the control plane's `type` field. */
export type CustomerCodePurpose = 'register' | 'login' | 'reset_password'

/** Outcome of a customer verification-code request; `message` is empty when the mail was accepted. */
export interface CustomerCodeOutcome {
  readonly ok: boolean
  readonly message: string
}

/** Outcome of a customer sign-in attempt; `state` carries the account view on success and is null on failure. */
export interface CustomerAuthOutcome {
  readonly ok: boolean
  readonly message: string
  readonly state: AccountView | null
}

/** Display-safe projection of one operator-configured discover-app row. */
export interface DiscoverAppView {
  readonly id: number
  readonly name: string
  readonly description: string
  readonly iconText: string
  readonly iconColor: string | null
  /** `portal` opens the customer portal route; `link` opens an external https/loopback URL. */
  readonly openMode: 'portal' | 'link'
  /** In-site path for `portal`, full URL for `link`. Never a credential. */
  readonly target: string
  readonly sort: number
  readonly isActive: boolean
}

/** Outcome of reading the discover-app catalog; `message` is a user-facing failure reason. */
export interface DiscoverAppsOutcome {
  readonly ok: boolean
  readonly apps: readonly DiscoverAppView[]
  readonly message?: string
}

/** Outcome of a portal web-ticket request; `ticket` is present only while `ok` is true. */
export interface WebTicketOutcome {
  readonly ok: boolean
  readonly ticket?: string
  readonly expiresIn?: number
  readonly message?: string
}
