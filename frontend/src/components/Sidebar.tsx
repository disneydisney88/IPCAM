import type { ReactNode } from 'react'
import { Camera, ChevronRight, Grid2X2, Layers3, Map as MapIcon, Settings, Star, Video } from 'lucide-react'
import type { Area, SavedView } from '../types'

export type Section = { type: 'all' | 'favorites' | 'area' | 'view' | 'settings' | 'internet' | 'map'; id?: number }

interface Props {
  areas: Area[]
  views: SavedView[]
  active: Section
  onSelect: (section: Section) => void
  internetCount: number
}

const activeMatch = (a: Section, b: Section) => a.type === b.type && a.id === b.id

export function Sidebar({ areas, views, active, onSelect, internetCount }: Props) {
  const nav = (section: Section, icon: ReactNode, label: string, count?: number) => (
    <button className={`nav-item ${activeMatch(active, section) ? 'active' : ''}`} onClick={() => onSelect(section)}>
      {icon}<span>{label}</span>{count !== undefined && <em>{count}</em>}
    </button>
  )
  return (
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Video size={23} /></div><div><strong>IPCAM</strong><span>MONITOR</span></div></div>
      <nav>
        <span className="nav-label">CAMERAS</span>
        {nav({ type: 'all' }, <Camera size={17} />, 'All Cameras')}
        {nav({ type: 'favorites' }, <Star size={17} />, 'My Favorites')}
        {nav({ type: 'internet' }, <Layers3 size={17} />, 'Internet Cameras', internetCount)}
        {nav({ type: 'map' }, <MapIcon size={17} />, 'Map View')}
        <span className="nav-label section-label">AREAS</span>
        {areas.map(area => nav({ type: 'area', id: area.id }, <span className="area-dot" />, area.name, area.camera_count))}
        <span className="nav-label section-label">MY VIEWS</span>
        {views.length ? views.map(view => nav({ type: 'view', id: view.id }, <Grid2X2 size={16} />, view.name)) : <p className="nav-empty">No saved views yet</p>}
      </nav>
      <button className={`settings-link ${active.type === 'settings' ? 'active' : ''}`} onClick={() => onSelect({ type: 'settings' })}><Settings size={17} />Settings<ChevronRight size={15} /></button>
    </aside>
  )
}
