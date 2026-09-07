import { memo, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Camera as CameraIcon, Expand, Info, Move, Star, Volume2, VolumeX, Wifi, Globe } from 'lucide-react'
import type { Camera } from '../types'
import { useVisibility } from '../hooks/useVisibility'

interface Props {
  camera: Camera
  gatewayReady: boolean
  onFavorite: (camera: Camera) => void
  onFullscreen: (camera: Camera) => void
}

const statusClass: Record<string, string> = {
  LIVE: 'live',
  OFFLINE: 'offline',
  'AUTH REQUIRED': 'auth',
  'STREAM ERROR': 'error',
  NEW: 'new',
  SCANNING: 'scanning',
}

function CameraCardComponent({ camera, gatewayReady, onFavorite, onFullscreen }: Props) {
  const { ref, visible } = useVisibility()
  const [snapshotReady, setSnapshotReady] = useState(false)
  const stream = camera.streams.find(item => item.kind === 'sub') || camera.streams[0]
  const specs = camera.model_specs && typeof camera.model_specs === 'object' ? camera.model_specs : null
  const tags = useMemo(() => {
    const raw = specs && 'tags' in specs ? (specs as { tags?: unknown }).tags : []
    return Array.isArray(raw) ? raw.filter((value): value is string => typeof value === 'string') : []
  }, [specs])
  const sourceLabel = camera.connection_type === 'internet' ? 'INTERNET' : 'LAN'
  const sourceIcon = camera.connection_type === 'internet' ? <Globe size={12} /> : <Wifi size={12} />
  const hasSnapshot = Boolean(camera.snapshot_url)
  const canRenderMock = camera.is_mock && camera.status === 'LIVE' && visible
  const showSnapshot = Boolean(hasSnapshot && visible && !canRenderMock)

  return (
    <motion.article ref={ref} className="camera-card" initial={{ opacity: 0, scale: 0.985 }} animate={{ opacity: 1, scale: 1 }}>
      <header className="camera-head drag-handle">
        <div className="camera-title">
          <Move size={14} className="move-icon" />
          <div>
            <strong>{camera.name}</strong>
            <span>{camera.manufacturer} {camera.model}</span>
          </div>
        </div>
        <button className={`icon-button favorite ${camera.favorite ? 'active' : ''}`} onClick={() => onFavorite(camera)} aria-label="Toggle favorite">
          <Star size={18} fill={camera.favorite ? 'currentColor' : 'none'} />
        </button>
      </header>

      <div className="video-stage">
        <AnimatePresence mode="wait">
          {showSnapshot ? (
            <motion.img
              key="snapshot"
              className="snapshot-feed"
              src={camera.snapshot_url || undefined}
              alt={camera.name}
              initial={{ opacity: 0 }}
              animate={{ opacity: snapshotReady ? 1 : 0 }}
              exit={{ opacity: 0 }}
              onLoad={() => setSnapshotReady(true)}
            />
          ) : canRenderMock ? (
            <motion.div key="mock" className={`mock-feed feed-${camera.id % 6}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <div className="scanlines" />
              <span className="timestamp">{new Date().toLocaleTimeString([], { hour12: false })}</span>
              <span className="feed-label">LIVE / SUB</span>
            </motion.div>
          ) : (
            <motion.div key="placeholder" className="stream-placeholder" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <CameraIcon size={28} />
              <span>{!visible ? 'STREAM PAUSED' : camera.status !== 'LIVE' ? camera.status : gatewayReady ? 'STREAM NOT REGISTERED' : 'STREAM GATEWAY NOT AVAILABLE'}</span>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="camera-badges">
          <span className={`badge ${camera.connection_type === 'internet' ? 'badge-internet' : 'badge-lan'}`}>
            {sourceIcon}
            {sourceLabel}
          </span>
          {tags.map(tag => (
            <span key={tag} className="badge badge-spec">{tag}</span>
          ))}
        </div>

        <span className={`status-pill ${statusClass[camera.status] || 'offline'}`}>
          <i />
          {camera.status}
        </span>
      </div>

      <div className="camera-meta">
        <span>{camera.host || camera.ip}</span>
        <span>{stream?.width || '—'}×{stream?.height || '—'} / {stream?.codec || '—'}</span>
      </div>

      <footer className="camera-actions">
        <button onClick={() => onFullscreen(camera)}><Expand size={15} /><span>Fullscreen</span></button>
        <button><CameraIcon size={15} /><span>Snapshot</span></button>
        <button disabled={!camera.audio_support}>{camera.audio_support ? <Volume2 size={15} /> : <VolumeX size={15} />}<span>Audio</span></button>
        <button><Info size={15} /><span>Info</span></button>
      </footer>
    </motion.article>
  )
}

export const CameraCard = memo(CameraCardComponent)
