/** Sidebar brand slots populated from AgentPanel public system settings. */
import { useEffect, useState } from 'react'
import { FishLogo } from '@deepseek-ai/dsh-client-ui-primitives'
import type { InjectFace, PropsRuntime } from '@deepseek-ai/dsh-client-ui-slots'
import type {} from '@deepseek-ai/dsh-client-ui-sidebar/client'
import type { BrandStore, BrandView } from './brand.ts'

/** Operations injected into both brand slot occupants. */
export interface BrandInjected {
  readonly brand: BrandStore
}

type MarkProps = PropsRuntime<'sidebar.brand.mark'> & InjectFace<BrandInjected>
type NameProps = PropsRuntime<'sidebar.brand.name'> & InjectFace<BrandInjected>

function useBrand(brand: BrandStore): BrandView {
  const [, bump] = useState(0)
  useEffect(() => {
    const unsubscribe = brand.subscribe(() => bump((n) => n + 1))
    void brand.refresh()
    return unsubscribe
  }, [brand])
  return brand.getSnapshot()
}

/** @param props - slot geometry plus the shared brand store. @returns the operator logo or the built-in fallback. */
export function BrandMark({ size, brand }: MarkProps) {
  const { logo } = useBrand(brand)
  if (logo !== undefined) {
    return <img src={logo} alt="" width={size} height={size} style={{ display: 'block', objectFit: 'contain' }} />
  }
  return <FishLogo size={size} />
}

/** @param props - slot runtime plus the shared brand store. @returns the operator brand text. */
export function BrandName({ brand }: NameProps) {
  const { name } = useBrand(brand)
  return <span>{name}</span>
}
