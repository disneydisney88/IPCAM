import { useEffect, useMemo, useState } from 'react'
import { GridLayout, verticalCompactor, type Layout } from 'react-grid-layout'
import type { Camera, CameraTelemetry, GridPosition } from '../types'
import { useStableContainerWidth } from '../hooks/useStableContainerWidth'
import { CameraCard } from './CameraCard'

interface Props {
  cameras: Camera[]
  gridSize: 1 | 4 | 6 | 9 | 12 | 16
  gatewayReady: boolean
  restoredLayout?: GridPosition[]
  layoutEditMode: boolean
  telemetryMap?: Record<number, CameraTelemetry>
  onLayoutChange: (layout: GridPosition[]) => void
  onFavorite: (camera: Camera) => void
  onFullscreen: (camera: Camera) => void
  onSnapshot?: (camera: Camera) => void
  onGeoRefresh?: (camera: Camera) => void
}

function buildLayout(cameras: Camera[], gridSize: 1 | 4 | 6 | 9 | 12 | 16, restoredLayout?: GridPosition[]) {
  const columns = gridSize === 1 ? 1 : gridSize === 16 ? 4 : gridSize === 12 ? 3 : gridSize === 9 ? 3 : 2
  const width = 12 / columns
  const height = gridSize === 1 ? 11 : gridSize === 4 || gridSize === 6 ? 8 : gridSize === 12 ? 5 : 6
  const restoredById = new Map((restoredLayout || []).map(item => [item.i, item]))

  return cameras.map((camera, index) => {
    const restored = restoredById.get(String(camera.id))
    return restored ? { ...restored, minW: restored.minW ?? 3, minH: restored.minH ?? 5 } : {
      i: String(camera.id),
      x: (index % columns) * width,
      y: Math.floor(index / columns) * 6,
      w: width,
      h: height,
      minW: 3,
      minH: 5,
    }
  })
}

function sameLayout(left: GridPosition[], right: GridPosition[]) {
  if (left.length !== right.length) return false
  return left.every((item, index) => {
    const other = right[index]
    return item.i === other.i && item.x === other.x && item.y === other.y && item.w === other.w && item.h === other.h
  })
}

export function CameraGrid({
  cameras,
  gridSize,
  gatewayReady,
  restoredLayout,
  layoutEditMode,
  telemetryMap,
  onLayoutChange,
  onFavorite,
  onFullscreen,
  onSnapshot,
  onGeoRefresh,
}: Props) {
  const { width, containerRef, mounted } = useStableContainerWidth(1200)
  const cameraSignature = cameras.map(camera => String(camera.id)).join('|')
  const restoredSignature = restoredLayout?.map(item => `${item.i}:${item.x},${item.y},${item.w},${item.h}`).join('|') ?? ''
  const layoutSeed = useMemo(() => buildLayout(cameras, gridSize, restoredLayout), [cameraSignature, gridSize, restoredSignature])
  const [layout, setLayout] = useState<GridPosition[]>(layoutSeed)

  useEffect(() => {
    setLayout(layoutSeed)
  }, [layoutSeed])

  const handleChange = (next: Layout) => {
    const normalized = next.map(item => ({
      i: item.i,
      x: item.x,
      y: item.y,
      w: item.w,
      h: item.h,
      minW: item.minW,
      minH: item.minH,
    }))
    setLayout(current => {
      if (sameLayout(current, normalized)) return current
      onLayoutChange(normalized)
      return normalized
    })
  }

  if (!mounted) {
    return (
      <div ref={containerRef} className="grid-shell">
        <div className="grid-shell-placeholder">
          <div className="grid-shell-skeleton" />
          <div className="grid-shell-skeleton" />
          <div className="grid-shell-skeleton" />
          <div className="grid-shell-skeleton" />
        </div>
      </div>
    )
  }

  return (
    <div ref={containerRef} className="grid-shell">
      <GridLayout
        width={width}
        layout={layout}
        gridConfig={{ cols: 12, rowHeight: 38, margin: [14, 14], containerPadding: [0, 0] }}
        dragConfig={{ enabled: layoutEditMode, handle: '.drag-handle', cancel: 'button' }}
        resizeConfig={{ enabled: layoutEditMode, handles: ['se'] }}
        compactor={verticalCompactor}
        onLayoutChange={handleChange}
      >
        {cameras.map(camera => (
          <div key={String(camera.id)}>
            <CameraCard
              camera={camera}
              gatewayReady={gatewayReady}
              telemetry={telemetryMap?.[camera.id]}
              onFavorite={onFavorite}
              onFullscreen={onFullscreen}
              onSnapshot={onSnapshot}
              onGeoRefresh={onGeoRefresh}
            />
          </div>
        ))}
      </GridLayout>
    </div>
  )
}
