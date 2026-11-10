/** Desktop welcome presentation; account and credential operations stay in the preload. */
import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Toast } from '@deepseek-ai/dsh-client-ui-primitives/src/Toast.tsx'
import { StateDot } from '@deepseek-ai/dsh-client-ui-primitives/src/StateDot.tsx'
import type { AccountView } from '@deepseek-ai/dsh-deepseek-account/types'
import type { WelcomeApi } from '../welcome-api.ts'

type Page = 'entry' | 'key' | 'account' | 'login' | 'register'
type LoginMode = 'password' | 'code'

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/**
 * Render the standalone welcome flow using shell-owned operations and localized copy.
 * Clearing the account attempt returns the sign-in status page to the initial choices.
 * @param props.api - isolated preload API; no account credentials reach the renderer.
 * @returns welcome pages with fixed bottom actions.
 */
export function Welcome({ api }: { api: WelcomeApi }) {
  const { messages: m } = api
  const [expiryNotice, setExpiryNotice] = useState(false)
  const [page, setPage] = useState<Page>('entry')
  const pageRef = useRef<Page>('entry')
  const visiblePage = useRef<Page>('entry')
  const [attempt, setAttempt] = useState<AccountView['attempt']>(null)
  const attemptRef = useRef<AccountView['attempt']>(null)
  const [starting, setStarting] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [copyFeedback, setCopyFeedback] = useState<{ status: 'idle' | 'busy' | 'copied' | 'failed' }>({ status: 'idle' })
  const copyState = copyFeedback.status
  const [draft, setDraft] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const busyRef = useRef(false)
  const mounted = useRef(true)
  const revision = useRef(0)
  const input = useRef<HTMLInputElement>(null)
  const keyButton = useRef<HTMLButtonElement>(null)
  const focusEntry = useRef(false)

  // Customer account form state. Credentials stay in the renderer only until the IPC call.
  const [loginMode, setLoginMode] = useState<LoginMode>('password')
  const [loginEmail, setLoginEmail] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [loginCode, setLoginCode] = useState('')
  const [registerEmail, setRegisterEmail] = useState('')
  const [registerCode, setRegisterCode] = useState('')
  const [registerPassword, setRegisterPassword] = useState('')
  const [codeSent, setCodeSent] = useState(false)
  const [accountError, setAccountError] = useState('')
  const [accountBusy, setAccountBusy] = useState(false)
  const loginEmailInput = useRef<HTMLInputElement>(null)
  const registerEmailInput = useRef<HTMLInputElement>(null)

  function navigate(next: Page) {
    pageRef.current = next
    setPage(next)
  }
  function showAccount(state: AccountView) {
    if (pageRef.current === 'key' || pageRef.current === 'login' || pageRef.current === 'register'
      || (state.attempt === null && pageRef.current === 'entry')) return
    attemptRef.current = state.attempt
    setAttempt(state.attempt)
    setStarting(false)
    setCopyFeedback({ status: 'idle' })
    navigate(state.attempt === null || state.attempt.phase === 'cancelled' ? 'entry' : 'account')
  }

  useEffect(() => {
    mounted.current = true
    document.documentElement.lang = api.id
    document.title = m.welcomeTitle
    const takeNotice = (): void => {
      void api.takeNotice().then((notice) => {
        if (mounted.current && notice === 'session-expired') setExpiryNotice(true)
      }).catch((_closedChannel: unknown) => {
        // A closed Welcome IPC channel must not interrupt the sign-in page.
      })
    }
    takeNotice()
    const stop = api.onAccountState((state) => {
      revision.current++
      takeNotice()
      showAccount(state)
    })
    return () => { mounted.current = false; stop() }
  }, [api, m.welcomeTitle])

  useEffect(() => {
    if (page === 'entry' && visiblePage.current !== 'entry') void api.analytics?.('auth_page_view', {})
    visiblePage.current = page
    if (page === 'key') input.current?.focus()
    else if (page === 'login') loginEmailInput.current?.focus()
    else if (page === 'register') registerEmailInput.current?.focus()
    else if (page === 'entry' && focusEntry.current) {
      focusEntry.current = false
      keyButton.current?.focus()
    }
  }, [page, api])

  useEffect(() => {
    if (copyState !== 'copied' && copyState !== 'failed') return
    const timer = setTimeout(() => { setCopyFeedback({ status: 'idle' }) }, 2000)
    return () => { clearTimeout(timer) }
  }, [copyFeedback])

  async function saveKey(event: FormEvent) {
    event.preventDefault()
    if (busyRef.current) return
    void api.analytics?.('api_key_save_click', {})
    const value = draft.trim()
    if (!/^[\x21-\x7e]+$/.test(value) || /^[A-Z][A-Z0-9_]*=[^=]/.test(value)
      || ((value.startsWith('"') || value.startsWith("'") || value.charCodeAt(0) === 96) && value.at(-1) === value[0])) {
      setError(value === '' ? m.welcomeKeyBlank : m.welcomeKeyInvalid)
      input.current?.focus()
      return
    }
    busyRef.current = true
    setBusy(true)
    setError('')
    try {
      const result = await api.saveApiKey(value)
      if (!mounted.current) return
      if (result.ok) setDraft('')
      else setError(m.welcomeKeyFailed)
    } catch {
      if (mounted.current) setError(m.welcomeKeyFailed)
    } finally {
      busyRef.current = false
      if (mounted.current) setBusy(false)
    }
  }
  async function skip() {
    if (busyRef.current) return
    busyRef.current = true
    setBusy(true)
    try {
      await api.skip()
      if (mounted.current) setDraft('')
    } catch {
      if (mounted.current) setError(m.welcomeContinueFailed)
    } finally {
      busyRef.current = false
      if (mounted.current) setBusy(false)
    }
  }
  async function start() {
    navigate('account')
    setStarting(true)
    setAttempt(null)
    attemptRef.current = null
    const current = ++revision.current
    try {
      const state = await api.startSignIn()
      if (mounted.current && revision.current === current) showAccount(state)
    } catch {
      if (mounted.current && revision.current === current) setStarting(false)
    }
  }
  async function cancel() {
    if (cancelling || attemptRef.current === null) return
    setCancelling(true)
    const current = ++revision.current
    try {
      const state = await api.cancelSignIn(attemptRef.current.id)
      if (mounted.current && revision.current === current) showAccount(state)
    } catch {
      // The current attempt remains visible so cancellation can be retried.
    } finally {
      if (mounted.current) setCancelling(false)
    }
  }
  async function copyLink() {
    const current = attemptRef.current
    if (current?.phase !== 'waiting-browser' || (copyState === 'busy' || copyState === 'copied')) return
    setCopyFeedback({ status: 'busy' })
    try {
      await api.copySignInLink(current.id)
      if (mounted.current && attemptRef.current === current) setCopyFeedback({ status: 'copied' })
    } catch {
      if (mounted.current && attemptRef.current === current) setCopyFeedback({ status: 'failed' })
    }
  }

  /** A successful customer authentication returns a `succeeded` snapshot; main opens the workspace. */
  function acceptAccount(state: AccountView): void {
    attemptRef.current = state.attempt
    setAttempt(state.attempt)
    setStarting(false)
    setAccountError('')
    navigate('account')
  }

  async function submitLogin(event: FormEvent) {
    event.preventDefault()
    if (accountBusy) return
    const email = loginEmail.trim()
    if (!EMAIL_PATTERN.test(email) || email.length > 254) { setAccountError(m.welcomeAccountEmailInvalid); return }
    if (loginMode === 'password' && loginPassword === '') { setAccountError(m.welcomeAccountPasswordBlank); return }
    if (loginMode === 'code' && !/^\d{6}$/.test(loginCode.trim())) { setAccountError(m.welcomeAccountCodeInvalid); return }
    setAccountError('')
    setAccountBusy(true)
    try {
      const result = loginMode === 'password'
        ? await api.login(email, loginPassword)
        : await api.loginCode(email, loginCode.trim())
      if (!mounted.current) return
      if (result.ok) acceptAccount(result.state)
      else setAccountError(result.message)
    } catch {
      if (mounted.current) setAccountError(m.welcomeAccountFailed)
    } finally {
      if (mounted.current) setAccountBusy(false)
    }
  }

  async function requestCode(purpose: 'register' | 'login') {
    if (accountBusy) return
    const email = (purpose === 'register' ? registerEmail : loginEmail).trim()
    if (!EMAIL_PATTERN.test(email) || email.length > 254) { setAccountError(m.welcomeAccountEmailInvalid); return }
    setAccountError('')
    setAccountBusy(true)
    try {
      const result = await api.sendCode(email, purpose)
      if (!mounted.current) return
      if (result.ok) { setCodeSent(true); setAccountError(m.welcomeRegisterCodeSent) }
      else setAccountError(result.message)
    } catch {
      if (mounted.current) setAccountError(m.welcomeAccountFailed)
    } finally {
      if (mounted.current) setAccountBusy(false)
    }
  }

  async function submitRegister(event: FormEvent) {
    event.preventDefault()
    if (accountBusy) return
    const email = registerEmail.trim()
    if (!EMAIL_PATTERN.test(email) || email.length > 254) { setAccountError(m.welcomeAccountEmailInvalid); return }
    if (!/^\d{6}$/.test(registerCode.trim())) { setAccountError(m.welcomeAccountCodeInvalid); return }
    if (registerPassword.length < 6) { setAccountError(m.welcomeAccountPasswordInvalid); return }
    setAccountError('')
    setAccountBusy(true)
    try {
      const result = await api.register(email, registerCode.trim(), registerPassword)
      if (!mounted.current) return
      if (result.ok) acceptAccount(result.state)
      else setAccountError(result.message)
    } catch {
      if (mounted.current) setAccountError(m.welcomeAccountFailed)
    } finally {
      if (mounted.current) setAccountBusy(false)
    }
  }

  function goRegister() {
    setAccountError('')
    setCodeSent(false)
    navigate('register')
  }
  function goLogin() {
    setAccountError('')
    navigate('login')
  }

  const phase = starting ? 'initializing' : attempt?.phase ?? 'failed'
  const waiting = phase === 'waiting-browser'
  const failed = phase === 'expired' || phase === 'failed'
  const title = phase === 'initializing' ? m.welcomeAuthStarting
    : waiting ? m.welcomeAuthWaiting : phase === 'expired' ? m.welcomeAuthExpired
      : phase === 'failed' ? m.welcomeAuthFailed : m.welcomeAuthExchanging
  const heading = page === 'entry' ? 'welcome-heading' : page === 'key' ? 'key-title'
    : page === 'login' ? 'login-title' : page === 'register' ? 'register-title' : 'auth-status'

  return <>
    {expiryNotice && <Toast text={m.welcomeSessionExpired} onDone={() => { setExpiryNotice(false) }} />}
    <div className="titlebar" aria-hidden="true" />
    <main className="welcome" aria-labelledby={heading}>
      <img className="brand" src="assets/welcome-brand.svg" alt={m.welcomeBrand} width="472" height="40" />
      <div id="tagline" className="tagline" hidden={page !== 'entry'}>
        <h1 id="welcome-heading"><span>{m.welcomeTaglineBefore}</span><em>{m.welcomeTaglineBrand}</em><span>{m.welcomeTaglineAfter}</span></h1>
        <p id="welcome-description">{m.welcomeDescription}</p>
      </div>
      <form id="key-form" className="key-form" hidden={page !== 'key'} noValidate onSubmit={(event) => { void saveKey(event) }} aria-busy={busy}>
        <header className="key-heading"><h1 id="key-title">{m.welcomeKeyTitle}</h1><p id="key-description">{m.welcomeKeyDescription}</p></header>
        <div className="key-field">
          <label className="visually-hidden" htmlFor="key-input">{m.welcomeKeyPlaceholder}</label>
          <input ref={input} id="key-input" type="password" autoComplete="new-password" autoCapitalize="off" spellCheck={false} required
            aria-describedby="key-description key-error" aria-invalid={error !== ''} placeholder={m.welcomeKeyPlaceholder}
            value={draft} disabled={busy} onChange={(event) => { setDraft(event.target.value); setError('') }} />
          <p id="key-error" className="key-error" role="alert" hidden={error === ''}>{error}</p>
        </div>
      </form>
      <form id="login-form" className="key-form account-form" hidden={page !== 'login'} noValidate
        aria-busy={accountBusy} onSubmit={(event) => { void submitLogin(event) }}>
        <header className="key-heading">
          <h1 id="login-title">{m.welcomeSignIn}</h1>
        </header>
        <div className="account-fields">
          <div className="key-field">
            <label className="visually-hidden" htmlFor="login-email">{m.welcomeLoginEmail}</label>
            <input ref={loginEmailInput} id="login-email" type="email" autoComplete="username" autoCapitalize="off" spellCheck={false}
              placeholder={m.welcomeLoginEmail} value={loginEmail} disabled={accountBusy}
              onChange={(event) => { setLoginEmail(event.target.value); setAccountError('') }} />
          </div>
          {loginMode === 'password' ? <div className="key-field">
            <label className="visually-hidden" htmlFor="login-password">{m.welcomeLoginPassword}</label>
            <input id="login-password" type="password" autoComplete="current-password"
              placeholder={m.welcomeLoginPassword} value={loginPassword} disabled={accountBusy}
              onChange={(event) => { setLoginPassword(event.target.value); setAccountError('') }} />
          </div> : <div className="account-code-row">
            <div className="key-field">
              <label className="visually-hidden" htmlFor="login-code">{m.welcomeRegisterCode}</label>
              <input id="login-code" type="text" inputMode="numeric" autoComplete="one-time-code" maxLength={6}
                placeholder={m.welcomeRegisterCode} value={loginCode} disabled={accountBusy}
                onChange={(event) => { setLoginCode(event.target.value); setAccountError('') }} />
            </div>
            <button id="login-send-code" type="button" disabled={accountBusy}
              onClick={() => { void requestCode('login') }}>{codeSent ? m.welcomeRegisterResend : m.welcomeRegisterSendCode}</button>
          </div>}
          <p id="login-error" className="account-error" role="alert" hidden={accountError === ''}>{accountError}</p>
          <button id="login-register" className="account-inline-link" type="button" disabled={accountBusy} onClick={goRegister}>{m.welcomeConnectAccount}</button>
        </div>
      </form>
      <form id="register-form" className="key-form account-form" hidden={page !== 'register'} noValidate
        aria-busy={accountBusy} onSubmit={(event) => { void submitRegister(event) }}>
        <header className="key-heading">
          <h1 id="register-title">{m.welcomeRegisterTitle}</h1>
          <p id="register-description">{m.welcomeRegisterDescription}</p>
        </header>
        <div className="account-fields">
          <div className="key-field">
            <label className="visually-hidden" htmlFor="register-email">{m.welcomeLoginEmail}</label>
            <input ref={registerEmailInput} id="register-email" type="email" autoComplete="username" autoCapitalize="off" spellCheck={false}
              placeholder={m.welcomeLoginEmail} value={registerEmail} disabled={accountBusy}
              onChange={(event) => { setRegisterEmail(event.target.value); setCodeSent(false); setAccountError('') }} />
          </div>
          <div className="account-code-row">
            <div className="key-field">
              <label className="visually-hidden" htmlFor="register-code">{m.welcomeRegisterCode}</label>
              <input id="register-code" type="text" inputMode="numeric" autoComplete="one-time-code" maxLength={6}
                placeholder={m.welcomeRegisterCode} value={registerCode} disabled={accountBusy}
                onChange={(event) => { setRegisterCode(event.target.value); setAccountError('') }} />
            </div>
            <button id="send-code" type="button" disabled={accountBusy}
              onClick={() => { void requestCode('register') }}>{codeSent ? m.welcomeRegisterResend : m.welcomeRegisterSendCode}</button>
          </div>
          <div className="key-field">
            <label className="visually-hidden" htmlFor="register-password">{m.welcomeRegisterPassword}</label>
            <input id="register-password" type="password" autoComplete="new-password" minLength={6}
              placeholder={m.welcomeRegisterPassword} value={registerPassword} disabled={accountBusy}
              onChange={(event) => { setRegisterPassword(event.target.value); setAccountError('') }} />
          </div>
          <p id="register-error" className="account-error" role="alert" hidden={accountError === ''}>{accountError}</p>
        </div>
      </form>
      <section id="auth-page" className={`key-heading ${waiting ? 'auth-waiting' : phase === 'expired' ? 'auth-expired' : ''}`}
        hidden={page !== 'account'} aria-live="polite">
        <h1 id="auth-status">{title}</h1>
        <p id="auth-description" hidden={!waiting && phase !== 'expired'}>{waiting ? m.welcomeAuthWaitingDescription : m.welcomeAuthExpiredDescription}</p>
        <button id="auth-copy" className="copy-link" type="button" hidden={!waiting} disabled={!waiting || (copyState === 'busy' || copyState === 'copied')} onClick={() => { void copyLink() }}>
          {copyState === 'copied' ? m.welcomeAuthCopied : copyState === 'failed' ? m.welcomeAuthCopyFailed : m.welcomeAuthCopyLink}
        </button>
      </section>
      <div id="auth-actions" className="actions" hidden={page !== 'account'}>
        <button id="auth-loading" className="primary" type="button" hidden={failed} disabled aria-label={m.welcomeAuthExchanging}>
          <StateDot state="ongoing" size={16} className="welcome-loading" />
        </button>
        <button id="auth-retry" className="primary" type="button" hidden={!failed} onClick={() => { void api.analytics?.('auth_page_click', { button_name: 'sign_in' }); void start() }}>{m.welcomeAuthRetry}</button>
        <button id="auth-api-key" className="secondary" type="button" hidden onClick={() => { void api.analytics?.('auth_page_click', { button_name: 'api-key' }); navigate('key') }}>{m.welcomeApiKey}</button>
        <button id="auth-cancel" className="secondary" type="button" hidden={failed}
          disabled={cancelling || phase === 'committing' || phase === 'succeeded' || (phase === 'initializing' && !attempt?.id)}
          onClick={() => { void cancel() }}>{m.welcomeAuthCancel}</button>
      </div>
      <div id="entry-actions" className="actions" hidden={page !== 'entry'}>
        <button id="sign-in" className="primary" type="button" onClick={() => { void api.analytics?.('auth_page_click', { button_name: 'sign_in' }); goLogin() }}>{m.welcomeSignIn}</button>
        <p id="entry-hint" className="entry-hint">{m.welcomeNoAccount}</p>
        <button id="goto-register" className="secondary" type="button" onClick={goRegister}>{m.welcomeConnectAccount}</button>
        <button ref={keyButton} id="api-key" className="secondary" type="button" hidden onClick={() => { void api.analytics?.('auth_page_click', { button_name: 'api-key' }); navigate('key') }}>{m.welcomeApiKey}</button>
      </div>
      <div id="login-actions" className="actions" hidden={page !== 'login'}>
        <button id="login-submit" className="primary" type="submit" form="login-form" disabled={accountBusy}>{m.welcomeLoginSubmit}</button>
        <button id="login-switch" className="secondary" type="button" disabled={accountBusy} onClick={() => {
          setLoginMode(loginMode === 'password' ? 'code' : 'password'); setCodeSent(false); setAccountError('')
        }}>{loginMode === 'password' ? m.welcomeAccountCodeLogin : m.welcomeAccountPasswordLogin}</button>
        <button id="login-back" className="back" type="button" disabled={accountBusy} onClick={() => { setAccountError(''); navigate('entry') }}>{m.welcomeLoginBack}</button>
      </div>
      <div id="register-actions" className="actions" hidden={page !== 'register'}>
        <button id="register-submit" className="primary" type="submit" form="register-form" disabled={accountBusy}>{m.welcomeRegisterSubmit}</button>
        <button id="register-login" className="secondary" type="button" disabled={accountBusy} onClick={goLogin}>{m.welcomeRegisterBack}</button>
        <button id="register-back" className="back" type="button" disabled={accountBusy} onClick={() => { setAccountError(''); navigate('entry') }}>{m.welcomeLoginBack}</button>
      </div>
      <div id="key-actions" className="actions" hidden={page !== 'key'}>
        <button id="save-key" className="primary" type="submit" form="key-form" disabled={busy || draft.trim() === ''}>{m.welcomeKeySave}</button>
        <button id="skip-key" className="secondary" type="button" disabled={busy} onClick={() => { void skip() }}>{m.welcomeKeyLater}</button>
        <button id="back-to-login" className="back" type="button" disabled={busy} onClick={() => {
          if (busyRef.current) return
          setDraft(''); setError(''); focusEntry.current = true; navigate('entry')
        }}>{m.welcomeKeyBack}</button>
      </div>
    </main>
  </>
}
