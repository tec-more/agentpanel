/** Account choice inside the model credential onboarding step. */
import { useEffect } from 'react'
import type { InjectFace, PropsLocale, PropsRuntime } from '@deepseek-ai/dsh-client-ui-slots'
import type {} from '@deepseek-ai/dsh-client-ui-settings-models/client'
import type { AccountSectionInjected } from './AccountSection.tsx'
import { SignInDialog } from './SignInDialog.tsx'
import { EmailSignInDialog } from './EmailSignInDialog.tsx'

/** @param props - onboarding completion, account state and actions. @returns account dialog while signed out. */
export function AccountOnboarding({ complete, useAccount, useTheme, setOnboarding, showLogin, start, cancel,
  sendCode, login, register, resetPassword, t }:
  PropsRuntime<'settings.models.sign-in'> & PropsLocale<'settings.account'> & InjectFace<AccountSectionInjected>) {
  const account = useAccount(value => value)
  const colorScheme = useTheme(snapshot => snapshot.active.colorScheme)
  useEffect(() => { setOnboarding(true); return () => { setOnboarding(false) } }, [setOnboarding])
  useEffect(() => { if (account.view?.status === 'credential-stored') complete() }, [account.view?.status, complete])
  if (!account.view || account.view.status === 'credential-stored' || account.customerAuth === undefined) return null
  if (account.customerAuth && sendCode !== undefined && login !== undefined && register !== undefined) {
    return <EmailSignInDialog account={account} sendCode={sendCode} login={login} register={register} resetPassword={resetPassword} t={t}
      close={() => { showLogin(false); complete() }} />
  }
  return <SignInDialog account={account} colorScheme={colorScheme} start={start} cancel={cancel} t={t}
    close={() => { showLogin(false); complete() }} />
}
