/** Customer email sign-in dialog: password login and registration. */
import { useEffect, useState } from 'react'
import { Button, IconCloseOutlineRegular, IconLoadingOutlineRegular, Input, Modal } from '@deepseek-ai/dsh-client-ui-primitives'
import type { AccountSnapshot } from './AccountSection.tsx'
import type { AccountKey } from './locales.ts'
import css from './EmailSignInDialog.module.css'

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const CODE_PATTERN = /^\d{6}$/
const RESEND_SECONDS = 60

/** Outcome shapes mirroring the Host's customer account operations; message is empty on success. */
export interface EmailCodeResult { ok: boolean; message: string }

/** @param props - safe account state, localized copy, and customer sign-in actions. @returns email login dialog. */
export function EmailSignInDialog({ account, sendCode, login, register, resetPassword, close, t }: {
  account: AccountSnapshot
  /** @param email - customer mailbox. @param purpose - code purpose. @returns whether the mail was accepted. */
  sendCode: (email: string, purpose: 'register' | 'login' | 'reset_password') => Promise<EmailCodeResult>
  /** @param email - customer mailbox. @param password - account password. @returns the sign-in outcome. */
  login: (email: string, password: string) => Promise<EmailCodeResult & { signedIn: boolean }>
  /** @param email - customer mailbox. @param code - 6-digit mail code. @param password - new account password. @returns the sign-in outcome. */
  register: (email: string, code: string, password: string) => Promise<EmailCodeResult & { signedIn: boolean }>
  /** @param email - customer mailbox. @param code - 6-digit mail code. @param password - new account password. @returns whether the reset was accepted. */
  resetPassword?: ((email: string, code: string, password: string) => Promise<EmailCodeResult>) | undefined
  close: () => void
  t: (key: AccountKey) => string
}) {
  const [tab, setTab] = useState<'login' | 'register' | 'reset'>('login')
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [countdown, setCountdown] = useState(0)
  useEffect(() => { if (account.view?.status === 'credential-stored') close() }, [account.view?.status, close])
  useEffect(() => {
    if (countdown <= 0) return
    const timer = setTimeout(() => { setCountdown(value => value - 1) }, 1000)
    return () => { clearTimeout(timer) }
  }, [countdown])
  const address = email.trim()
  const submit = async () => {
    if (busy) return
    if (!EMAIL_PATTERN.test(address) || address.length > 254) { setError(t('emailInvalid')); return }
    if (password === '') { setError(t('passwordBlank')); return }
    if (tab !== 'login' && !CODE_PATTERN.test(code.trim())) { setError(t('codeInvalid')); return }
    if (tab !== 'login' && password.length < 6) { setError(t('passwordInvalid')); return }
    setBusy(true)
    setError('')
    try {
      if (tab === 'reset') {
        if (resetPassword === undefined) return
        const result = await resetPassword(address, code.trim(), password)
        if (result.ok) {
          setTab('login')
          setCode('')
          setPassword('')
          setNotice(t('resetDone'))
        } else {
          setError(result.message === '' ? t('emailAuthFailed') : result.message)
        }
        return
      }
      const result = tab === 'login' ? await login(address, password)
        : await register(address, code.trim(), password)
      if (!result.signedIn) setError(result.message === '' ? t('emailAuthFailed') : result.message)
    } catch {
      setError(t('emailAuthFailed'))
    } finally {
      setBusy(false)
    }
  }
  const requestCode = async () => {
    if (busy || countdown > 0) return
    if (!EMAIL_PATTERN.test(address) || address.length > 254) { setError(t('emailInvalid')); return }
    setBusy(true)
    setError('')
    try {
      const result = await sendCode(address, tab === 'reset' ? 'reset_password' : 'register')
      if (result.ok) {
        setNotice(t('codeSent'))
        setCountdown(RESEND_SECONDS)
      } else {
        setError(result.message === '' ? t('emailAuthFailed') : result.message)
      }
    } catch {
      setError(t('emailAuthFailed'))
    } finally {
      setBusy(false)
    }
  }
  const switchTab = (next: 'login' | 'register' | 'reset') => {
    if (busy) return
    setTab(next)
    setError('')
    setNotice('')
  }
  const sendLabel = countdown > 0 ? `${t('resend')} (${countdown}s)` : t('sendCode')
  return <Modal open headless title={t('loginTitle')} onClose={busy ? () => undefined : close} className={css.dialog as string}>
    <div className={css.content}>
      <div className={css.header}>
        <h2 className={css.title}>{t('loginTitle')}</h2>
        <button type="button" className={css.close} aria-label={t('close')} disabled={busy} onClick={close}>
          <IconCloseOutlineRegular size={14} />
        </button>
      </div>
      <form className={css.form} noValidate onSubmit={(event) => { event.preventDefault(); void submit() }}>
        {tab === 'reset'
          ? <button type="button" className={css.inlineLink} disabled={busy} onClick={() => { switchTab('login') }}>
            {t('backToSignIn')}
          </button>
          : <div className={css.tabs} role="tablist">
            <button type="button" role="tab" aria-selected={tab === 'login'} className={css.tab} data-active={tab === 'login'}
              disabled={busy} onClick={() => { switchTab('login') }}>{t('signIn')}</button>
            <button type="button" role="tab" aria-selected={tab === 'register'} className={css.tab} data-active={tab === 'register'}
              disabled={busy} onClick={() => { switchTab('register') }}>{t('tabRegister')}</button>
          </div>}
        <div className={css.field}>
          <label className={css.label} htmlFor="account-email">{t('emailLabel')}</label>
          <Input id="account-email" className={css.fieldInput as string} type="email" autoComplete="email"
            autoCapitalize="off" spellCheck={false} placeholder={t('emailPlaceholder')} value={email} disabled={busy}
            aria-invalid={error !== ''} onChange={(event) => { setEmail(event.target.value); setError(''); setNotice('') }} />
        </div>
        {tab !== 'login' && <div className={css.field}>
          <label className={css.label} htmlFor="account-code">{t('codeLabel')}</label>
          <div className={css.codeRow}>
            <Input id="account-code" className={css.fieldInput as string} type="text" inputMode="numeric"
              autoComplete="one-time-code" maxLength={6} placeholder={t('codePlaceholder')} value={code} disabled={busy}
              onChange={(event) => { setCode(event.target.value); setError('') }} />
            <Button variant="outline" type="button" className={css.sendButton as string} disabled={busy || countdown > 0}
              onClick={() => { void requestCode() }}>{sendLabel}</Button>
          </div>
        </div>}
        <div className={css.field}>
          <label className={css.label} htmlFor="account-password">{t('passwordLabel')}</label>
          <Input id="account-password" className={css.fieldInput as string} type="password"
            autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
            placeholder={tab === 'login' ? t('passwordPlaceholder') : t('passwordRegisterPlaceholder')}
            value={password} disabled={busy} onChange={(event) => { setPassword(event.target.value); setError('') }} />
        </div>
        {tab === 'login' && resetPassword !== undefined
          && <button type="button" className={css.inlineLink} disabled={busy} onClick={() => { switchTab('reset') }}>
            {t('forgotPassword')}
          </button>}
        {notice !== '' && <p className={css.notice} role="status">{notice}</p>}
        {error !== '' && <p className={css.error} role="alert">{error}</p>}
      </form>
    </div>
    <div className={css.actions}>
      <Button variant="primary" className={css.primaryButton as string} disabled={busy || account.view === undefined}
        onClick={() => { void submit() }}>
        {busy ? <IconLoadingOutlineRegular className={css.spinner as string} />
          : tab === 'register' ? t('registerSubmit') : tab === 'reset' ? t('resetSubmit') : t('signIn')}
      </Button>
    </div>
  </Modal>
}
