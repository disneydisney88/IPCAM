import { useCallback, useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Bell, ChevronDown, Grid2X2, Lock, Menu, MonitorPlay, Plus, Radar, Save, Search, X } from 'lucide-react'
import { api, auth, setLockHandler } from './lib/api'
import type { Area, Camera, CameraTelemetry, GridPosition, LiveStream, NetworkInterface, SavedView } from './types'
import { Sidebar, type Section } from './components/Sidebar'
import { CameraGrid } from './components/CameraGrid'
import { CameraMapView } from './components/CameraMapView'
import { LockScreen } from './components/LockScreen'
import { ScanPanel } from './components/ScanPanel'
import { SettingsPanel } from './components/SettingsPanel'
import { AddCameraWizard } from './components/AddCameraWizard'

const gridSizes = [1, 4, 9, 16] as const

export default function App() {
  const mock = new URLSearchParams(location.search).get('mock') === 'true'
  const [cameras, setCameras] = useState<Camera[]>([])
  const [areas, setAreas] = useState<Area[]>([])
  const [views, setViews] = useState<SavedView[]>([])
  const [interfaces, setInterfaces] = useState<NetworkInterface[]>([])
  const [cidr, setCidr] = useState('192.168.1.0/24')
  const [gridSize, setGridSize] = useState<1 | 4 | 9 | 16>(4)
  const [section, setSection] = useState<Section>({ type: 'all' })
  const [search, setSearch] = useState('')
  const [layout, setLayout] = useState<GridPosition[]>([])
  const [restoredLayout, setRestoredLayout] = useState<GridPosition[] | undefined>()
  const [layoutEditMode, setLayoutEditMode] = useState(false)
  const [gateway, setGateway] = useState({ available: false, running: false, message: 'CHECKING…' })
  const [scanOpen, setScanOpen] = useState(false)
  const [wizardOpen, setWizardOpen] = useState(false)
  const [fullscreen, setFullscreen] = useState<Camera | null>(null)
  const [liveStream, setLiveStream] = useState<LiveStream | null>(null)
  const [toast, setToast] = useState('')
  const [loading, setLoading] = useState(true)
  const [summary, setSummary] = useState<any>(null)
  const [telemetryMap, setTelemetryMap] = useState<Record<number, CameraTelemetry>>({})
  const [lockState, setLockState] = useState<'pending' | 'setup' | 'locked' | 'open'>('pending')
  const [lockBusy, setLockBusy] = useState(false)
  const [lockError, setLockError] = useState('')

  const refresh = useCallback(async () => {
    const [cameraData, areaData, viewData] = await Promise.all([api.cameras(), api.areas(), api.views()])
    setCameras(cameraData)
    setAreas(areaData)
    setViews(viewData)
  }, [])

  const loadData = useCallback(async () => {
    try {
      if (mock) await api.ensureMock()
      const health = await api.mediaHealth()
      setGateway(health)
      try {
        const networkData = await api.interfaces()
        setInterfaces(networkData)
        if (networkData[0]) setCidr(networkData[0].suggested_cidr)
      } catch {
        /* keep the default CIDR if interface detection fails */
      }
      await refresh()
      setSummary(await api.dashboardSummary())
    } catch (err) {
      setToast(err instanceof Error ? err.message : 'Unable to load dashboard')
    }
  }, [mock, refresh])

  useEffect(() => {
    const check = async () => {
      try {
        const status = await api.adminStatus()
        if (!status.configured) {
          setLockState('setup')
        } else if (auth.token()) {
          try {
            await api.cameras()
            setLockState('open')
            await loadData()
          } catch {
            setLockState('locked')
          }
        } else {
          setLockState('locked')
        }
      } catch {
        setLockState('locked')
      } finally {
        setLoading(false)
      }
    }
    check()
  }, [loadData])

  useEffect(() => {
    setLockHandler(status => {
      setLockBusy(false)
      setLockState(status === 428 ? 'setup' : 'locked')
    })
    return () => setLockHandler(null)
  }, [])

  const unlockDashboard = async (password: string) => {
    setLockBusy(true)
    setLockError('')
    try {
      if (lockState === 'setup') await api.adminSetup(password)
      const result = await api.adminUnlock(password)
      auth.set(result.unlock_token)
      setLockState('open')
      await loadData()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unlock failed'
      setLockError(message.includes('temporarily locked') ? 'Too many attempts · locked for 5 minutes' : message)
    } finally {
      setLockBusy(false)
    }
  }

  const lockDashboard = () => {
    auth.clear()
    setTelemetryMap({})
    setLockState('locked')
  }

  const cameraIds = useMemo(() => cameras.map(camera => camera.id).join(','), [cameras])

  useEffect(() => {
    if (!cameraIds) return
    let cancelled = false
    const poll = async () => {
      try {
        const reports = await api.telemetry(cameraIds.split(',').map(Number))
        if (cancelled) return
        setTelemetryMap(Object.fromEntries(reports.map(report => [report.id, report])))
      } catch {
        /* telemetry is best-effort; keep the previous snapshot */
      }
    }
    poll()
    const timer = window.setInterval(poll, 30_000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [cameraIds])

  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => setToast(''), 3200)
    return () => clearTimeout(timer)
  }, [toast])

  useEffect(() => {
    setLiveStream(null)
    if (!fullscreen || fullscreen.is_mock) return
    api.cameraLive(fullscreen.id).then(setLiveStream).catch(error => setLiveStream({ available: false, state: 'error', message: error instanceof Error ? error.message : 'Live stream unavailable', player_url: null }))
  }, [fullscreen])

  const selectedView = section.type === 'view' ? views.find(view => view.id === section.id) : undefined
  const filtered = useMemo(() => {
    let result = cameras
    if (section.type === 'favorites') result = result.filter(camera => camera.favorite)
    if (section.type === 'area') result = result.filter(camera => camera.area_id === section.id)
    if (section.type === 'internet') result = result.filter(camera => camera.connection_type === 'internet')
    if (selectedView) {
      const order = new Map(selectedView.items.map(item => [item.camera_id, item.position]))
      result = result.filter(camera => order.has(camera.id)).sort((a, b) => order.get(a.id)! - order.get(b.id)!)
    }
    const query = search.trim().toLowerCase()
    if (query) {
      result = result.filter(camera => `${camera.name} ${camera.ip} ${camera.host || ''} ${camera.model} ${camera.manufacturer} ${camera.resolved_ip || ''}`.toLowerCase().includes(query))
    }
    return result.slice(0, gridSize)
  }, [cameras, section, selectedView, search, gridSize])

  const chooseSection = (next: Section) => {
    setSection(next)
    setRestoredLayout(undefined)
    if (next.type === 'view') {
      const view = views.find(item => item.id === next.id)
      if (view) {
        setGridSize(view.grid_size)
        const restored = view.items.map(item => ({
          i: String(item.camera_id),
          x: Number(item.layout.x ?? 0),
          y: Number(item.layout.y ?? 0),
          w: Number(item.layout.w ?? 6),
          h: Number(item.layout.h ?? 7),
          minW: 3,
          minH: 5,
        }))
        setRestoredLayout(restored)
      }
    }
  }

  const toggleFavorite = async (camera: Camera) => {
    setCameras(current => current.map(item => item.id === camera.id ? { ...item, favorite: !item.favorite } : item))
    try {
      await api.favorite(camera.id, !camera.favorite)
      setToast(!camera.favorite ? 'Added to My Favorites' : 'Removed from My Favorites')
    } catch {
      setCameras(current => current.map(item => item.id === camera.id ? camera : item))
      setToast('Could not save favorite')
    }
  }

  const captureSnapshot = async (camera: Camera) => {
    try {
      const result = await api.captureSnapshot(camera.id)
      if (result.available) {
        await refresh()
        setToast('Snapshot captured')
      } else {
        setToast(result.message || 'Camera did not return a snapshot')
      }
    } catch (err) {
      setToast(err instanceof Error ? err.message : 'Snapshot failed')
    }
  }

  const refreshGeoip = async (camera: Camera) => {
    try {
      const updated = await api.refreshGeoip(camera.id)
      setCameras(current => current.map(item => item.id === camera.id ? updated : item))
      setToast(updated.latitude != null ? `Location: ${updated.city || ''}, ${updated.country || ''}` : 'No public coordinates for this camera')
    } catch (err) {
      setToast(err instanceof Error ? err.message : 'GeoIP refresh failed')
    }
  }

  const saveView = async () => {
    const name = prompt('Name this saved view', `New View ${views.length + 1}`)
    if (!name?.trim()) return
    try {
      const positions = layout.length ? layout : filtered.map((camera, index) => ({ i: String(camera.id), x: (index % 2) * 6, y: Math.floor(index / 2) * 7, w: 6, h: 7 }))
      await api.createView({
        name: name.trim(),
        grid_size: gridSize,
        filters: section.type === 'area' ? { area_id: section.id } : {},
        stream_preference: 'sub',
        items: filtered.map((camera, position) => {
          const item = positions.find(value => value.i === String(camera.id))
          return { camera_id: camera.id, position, layout: item || {} }
        }),
      })
      await refresh()
      setToast('Saved view created')
    } catch (err) {
      setToast(err instanceof Error ? err.message : 'Could not save view')
    }
  }

  const title = section.type === 'favorites'
    ? 'My Favorites'
    : section.type === 'area'
      ? areas.find(area => area.id === section.id)?.name || 'Area'
      : section.type === 'internet'
        ? 'Internet Cameras'
        : section.type === 'map'
          ? 'Camera Map'
          : selectedView?.name || 'All Cameras'

  const internetCount = cameras.filter(camera => camera.connection_type === 'internet').length

  if (loading) {
    return (
      <div className="app-loading">
        <div className="brand-mark"><MonitorPlay /></div>
        <strong>IPCAM MONITOR</strong>
        <span>Starting local dashboard…</span>
      </div>
    )
  }

  if (lockState !== 'open') {
    return <LockScreen mode={lockState === 'setup' ? 'setup' : 'locked'} busy={lockBusy} error={lockError} onSubmit={unlockDashboard} />
  }

  return (
    <div className="app-shell">
      <Sidebar areas={areas} views={views} active={section} onSelect={chooseSection} internetCount={internetCount} />
      <main className="main-panel">
        <header className="topbar">
          <div className="mobile-brand"><Menu /><strong>IPCAM</strong></div>
          <button className="scan-button" onClick={() => setScanOpen(true)}><Radar size={17} />Scan Network</button>
          <label className="network-select">
            <span>Network</span>
            <select value={cidr} onChange={e => setCidr(e.target.value)}>
              {interfaces.map(item => <option key={item.name + item.subnet} value={item.suggested_cidr}>{item.suggested_cidr} · {item.name}</option>)}
              {!interfaces.length && <option>{cidr}</option>}
            </select>
            <ChevronDown size={15} />
          </label>
          <div className="topbar-spacer" />
          <div className="search-box"><Search size={17} /><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Camera name / IP / host" /></div>
          <button className="icon-button" onClick={lockDashboard} title="Lock dashboard"><Lock size={18} /></button>
          <button className="icon-button"><Bell size={18} /></button>
          <div className="local-avatar">KL</div>
        </header>

        {section.type === 'settings' ? (
          <SettingsPanel areas={areas} cameras={cameras} dataDir="%LOCALAPPDATA%\\IPCAM" gatewayMessage={gateway.message} onRefresh={refresh} />
        ) : (
          <>
            <section className="content-heading">
              <div>
                <span className="eyebrow">{mock ? 'MOCK MODE · LOCAL ONLY' : 'LOCAL MONITOR'}</span>
                <h1>{title}</h1>
                <p>{filtered.length} visible · {cameras.filter(camera => camera.status === 'LIVE').length} live · Grid streams prefer sub profiles</p>
              </div>
              <div className="heading-actions">
                <button className={`secondary ${layoutEditMode ? 'active' : ''}`} onClick={() => setLayoutEditMode(value => !value)}>{layoutEditMode ? 'Lock Layout' : 'Edit Layout'}</button>
                <button className="secondary" onClick={() => setWizardOpen(true)}><Plus size={16} />Add Camera</button>
                <button className="secondary" onClick={saveView}><Save size={16} />Save View</button>
              </div>
            </section>
            {section.type === 'map' ? (
              <CameraMapView cameras={cameras} telemetryMap={telemetryMap} onFullscreen={setFullscreen} />
            ) : (
              <>
                <section className="view-toolbar">
                  <div className="grid-picker">
                    <span>VIEW</span>
                    {gridSizes.map(size => (
                      <button key={size} className={gridSize === size ? 'active' : ''} onClick={() => { setGridSize(size); setRestoredLayout(undefined) }}>
                        {size}
                      </button>
                    ))}
                  </div>
                  <div className={`gateway-state ${gateway.running ? 'ready' : ''}`}><i />{gateway.message}</div>
                </section>
                {section.type === 'all' && summary && <section className="dashboard-summary"><div><strong>{summary.total_cameras}</strong><span>Total Cameras</span></div><div><strong>{summary.online}</strong><span>Online</span></div><div><strong>{summary.offline}</strong><span>Offline</span></div><div><strong>{summary.last_scan ? new Date(summary.last_scan).toLocaleString() : 'Never'}</strong><span>Last Scan</span></div><div><strong>{summary.scheduler.state}</strong><span>Scheduler</span></div><div><strong>{summary.recent_discoveries.length}</strong><span>Recent Discoveries</span></div><div><strong>{summary.recent_offline.length}</strong><span>Recent Offline</span></div><div><strong>{summary.recent_scan_jobs.length}</strong><span>Recent Scan Jobs</span></div><div><strong>{summary.public_scan.state}</strong><span>Public Scan</span></div><div><strong>{summary.go2rtc.message}</strong><span>go2rtc</span></div></section>}
                {filtered.length ? (
                  <CameraGrid
                    cameras={filtered}
                    gridSize={gridSize}
                    gatewayReady={gateway.running}
                    restoredLayout={restoredLayout}
                    layoutEditMode={layoutEditMode}
                    telemetryMap={telemetryMap}
                    onLayoutChange={setLayout}
                    onFavorite={toggleFavorite}
                    onFullscreen={setFullscreen}
                    onSnapshot={captureSnapshot}
                    onGeoRefresh={refreshGeoip}
                  />
                ) : (
                  <div className="empty-state">
                    <Grid2X2 size={36} />
                    <h2>No cameras in this view</h2>
                    <p>{section.type === 'favorites' ? 'Select the star on any camera to keep it here.' : 'Run a private-network scan or add a camera manually.'}</p>
                    <button className="primary" onClick={() => setWizardOpen(true)}><Plus size={16} />Add Camera</button>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </main>

      <AnimatePresence>{scanOpen && <ScanPanel cidr={cidr} mock={mock} onClose={() => setScanOpen(false)} onComplete={refresh} />}</AnimatePresence>
      <AnimatePresence>{wizardOpen && <AddCameraWizard mock={mock} onClose={() => setWizardOpen(false)} onSaved={refresh} />}</AnimatePresence>
      <AnimatePresence>
        {fullscreen && (
          <motion.div className="fullscreen-view" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <button onClick={() => setFullscreen(null)}><X /></button>
            {fullscreen.is_mock ? <div className={`mock-feed feed-${fullscreen.id % 6}`}><div className="scanlines" /><span className="timestamp">{fullscreen.name} · MOCK STREAM</span></div> : liveStream?.available && liveStream.player_url ? <iframe className="live-frame" src={liveStream.player_url} title={`${fullscreen.name} live stream`} allow="autoplay; fullscreen" /> : <div className="live-fallback"><MonitorPlay size={44} /><strong>{liveStream?.message || 'Connecting to stream gateway…'}</strong><span>{liveStream?.state || 'loading'}</span>{fullscreen.snapshot_url && <img src={fullscreen.snapshot_url} alt={`${fullscreen.name} snapshot fallback`} />}</div>}
            <footer>
              <strong>{fullscreen.name}</strong>
              <span>{fullscreen.host || fullscreen.ip} · {fullscreen.manufacturer} {fullscreen.model}</span>
            </footer>
          </motion.div>
        )}
      </AnimatePresence>
      <AnimatePresence>{toast && <motion.div className="toast" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>{toast}</motion.div>}</AnimatePresence>
    </div>
  )
}
