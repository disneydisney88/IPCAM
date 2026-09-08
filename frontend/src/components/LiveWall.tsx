import { useEffect, useState } from 'react'
import { MonitorPlay, RefreshCw } from 'lucide-react'
import { api } from '../lib/api'
import type { Camera, LiveStream } from '../types'

interface Props {
  cameras: Camera[]
  columns: 2 | 3 | 4
  onFullscreen: (camera: Camera) => void
}

export function LiveWall({ cameras, columns, onFullscreen }: Props) {
  const [streams, setStreams] = useState<Record<number, LiveStream>>({})
  const [loading, setLoading] = useState(false)

  const refresh = async () => {
    setLoading(true)
    try {
      const results = await Promise.all(
        cameras.map(async camera => {
          if (camera.is_mock) {
            return [camera.id, { available: false, state: 'mock', message: 'MOCK', player_url: null } as LiveStream]
          }
          try {
            return [camera.id, await api.cameraLive(camera.id)]
          } catch (error) {
            return [camera.id, {
              available: false, state: 'error',
              message: error instanceof Error ? error.message : 'Live unavailable', player_url: null,
            } as LiveStream]
          }
        }),
      )
      setStreams(Object.fromEntries(results))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() /* eslint-disable-line react-hooks/exhaustive-deps */ }, [cameras])

  return (
    <section className="live-wall">
      <div className="live-wall-toolbar">
        <span><MonitorPlay size={15} /> LIVE WALL · {cameras.length} tiles · {columns} columns</span>
        <span className="live-wall-hint">串流走本機 go2rtc（127.0.0.1:1984）— 需與主機同網路；需先設定相機憑證。</span>
        <button className="secondary" onClick={refresh} disabled={loading}><RefreshCw size={14} />{loading ? 'Connecting…' : 'Refresh'}</button>
      </div>
      <div className="live-wall-grid" style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}>
        {cameras.map(camera => {
          const stream = streams[camera.id]
          return (
            <article key={camera.id} className="live-tile">
              <header>
                <strong>{camera.name}</strong>
                <span>{camera.host || camera.ip}</span>
                {stream?.available && stream.player_url && (
                  <button onClick={() => onFullscreen(camera)}>Fullscreen</button>
                )}
              </header>
              {stream?.available && stream.player_url ? (
                <iframe src={stream.player_url} title={`${camera.name} live`} allow="autoplay; fullscreen" />
              ) : (
                <div className="live-tile-fallback">
                  <MonitorPlay size={26} />
                  <span>{camera.is_mock ? 'MOCK' : (stream?.message || stream?.state || 'CONNECTING…')}</span>
                </div>
              )}
            </article>
          )
        })}
      </div>
    </section>
  )
}
