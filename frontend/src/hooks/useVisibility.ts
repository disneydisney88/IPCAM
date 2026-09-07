import { useEffect, useRef, useState } from 'react'

export function useVisibility() {
  const ref = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(true)
  useEffect(() => {
    if (!ref.current || !('IntersectionObserver' in window)) return
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { rootMargin: '120px' })
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [])
  return { ref, visible }
}

