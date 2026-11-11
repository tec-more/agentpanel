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
