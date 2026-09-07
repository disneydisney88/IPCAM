import { useEffect, useRef, useState } from 'react'

const WIDTH_JITTER_THRESHOLD = 3
const WIDTH_DEBOUNCE_MS = 120

export function useStableContainerWidth(initialWidth = 1200) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(initialWidth)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    const element = containerRef.current
    if (!element || typeof ResizeObserver === 'undefined') return

    let timeout: ReturnType<typeof setTimeout> | null = null
    let lastWidth = 0
    let cancelled = false

    const commit = (nextWidth: number) => {
      if (cancelled) return
      const rounded = Math.round(nextWidth)
      if (!rounded) return
      if (lastWidth && Math.abs(rounded - lastWidth) < WIDTH_JITTER_THRESHOLD) return
      lastWidth = rounded
      setWidth(rounded)
      setMounted(true)
    }

    const observer = new ResizeObserver(entries => {
      const nextWidth = entries[0]?.contentRect.width ?? 0
      if (!nextWidth) return
      if (timeout) clearTimeout(timeout)
      timeout = setTimeout(() => commit(nextWidth), WIDTH_DEBOUNCE_MS)
    })

    observer.observe(element)
    commit(element.getBoundingClientRect().width)

    return () => {
      cancelled = true
      if (timeout) clearTimeout(timeout)
      observer.disconnect()
    }
  }, [])

  return { width, containerRef, mounted }
}
