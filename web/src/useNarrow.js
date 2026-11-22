import { useEffect, useState } from 'react'

// Phone layout: the map sits in a band under the timeline and the story scrolls below it.
// Keep in step with the @media (max-width: 640px) block at the end of styles.css.
export const NARROW = '(max-width: 640px)'

export const isNarrow = () => window.matchMedia(NARROW).matches

export function useNarrow() {
  const [narrow, setNarrow] = useState(isNarrow)
  useEffect(() => {
    const mq = window.matchMedia(NARROW)
    const on = () => setNarrow(mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])
  return narrow
}
