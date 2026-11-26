/** Home-hero slots populated from AgentPanel public system settings. */
import { useEffect, useState } from 'react'
import { FishLogo } from '@deepseek-ai/dsh-client-ui-primitives'
import type { InjectFace, PropsRuntime } from '@deepseek-ai/dsh-client-ui-slots'
import type {} from '@deepseek-ai/dsh-client-ui-conversation/client'
import type { BrandStore, BrandView } from './brand.ts'

/** Operations injected into the hero slot occupants. */
export interface HeroInjected {
  readonly brand: BrandStore
  /** Default localized copy from the conversation namespace. */
  readonly t: (key: string) => string
}

type MarkProps = PropsRuntime<'conversation.hero.brand.mark'> & InjectFace<HeroInjected>
type TextProps = PropsRuntime<'conversation.hero.headline'> & InjectFace<HeroInjected>
type PreviewProps = PropsRuntime<'conversation.hero.preview'> & InjectFace<HeroInjected>

function useBrand(brand: BrandStore): BrandView {
  const [, bump] = useState(0)
  useEffect(() => {
    const unsubscribe = brand.subscribe(() => bump((n) => n + 1))
    void brand.refresh()
    return unsubscribe
  }, [brand])
  return brand.getSnapshot()
}

/** @param props - slot geometry and shared brand store. @returns the operator hero logo or the built-in fish. */
export function HeroMark({ size, className, brand }: MarkProps) {
  const view = useBrand(brand)
  const logo = view.heroLogo ?? view.logo
  if (logo !== undefined) {
    return <img src={logo} alt="" width={size} height={size} className={className}
      style={{ display: 'block', objectFit: 'contain' }} />
  }
  return <FishLogo size={size} className={className} />
}

/** @param props - slot runtime and shared brand store. @returns the operator headline text. */
export function HeroHeadline({ brand, t }: TextProps) {
  const view = useBrand(brand)
  return <span>{view.heroHeadline ?? t('hero.headline')}</span>
}

/** @param props - slot runtime and shared brand store. @returns the version badge, or nothing when cleared. */
export function HeroPreview({ brand }: PreviewProps) {
  const view = useBrand(brand)
  const label = view.heroBeta
  if (label === undefined || label === '') return null
  return <span style={{
    alignSelf: 'flex-start', marginTop: 2, padding: '1px 7px 0',
    border: '0.5px solid var(--dsw-alias-interactive-bg-hover)', borderRadius: 999,
    background: 'var(--dsw-alias-state-business-tertiary)', color: 'var(--dsw-alias-label-primary-bluish)',
    fontFamily: 'var(--ds-font-family-code)', fontSize: 12, lineHeight: '18px', fontWeight: 500,
  }}>{label}</span>
}
