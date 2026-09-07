import { useEffect, useMemo } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { Camera as CameraIcon, Globe, MapPin, MonitorPlay } from 'lucide-react'
import type { Camera } from '../types'

interface Props {
  cameras: Camera[]
  onFullscreen: (camera: Camera) => void
}

const DEFAULT_CENTER: [number, number] = [25.033, 121.5654]

function FitBounds({ points }: { points: Array<[number, number]> }) {
  const map = useMap()
  useEffect(() => {
    if (!points.length) return
    if (points.length === 1) {
      map.setView(points[0], 13)
      return
    }
    map.fitBounds(points, { padding: [48, 48], maxZoom: 14 })
  }, [map, points])
  return null
}

export function CameraMapView({ cameras, onFullscreen }: Props) {
  const pinned = useMemo(
    () => cameras.filter(camera => camera.latitude != null && camera.longitude != null),
    [cameras],
  )
  const localOnly = useMemo(
    () => cameras.filter(camera => camera.latitude == null || camera.longitude == null),
    [cameras],
  )
  const points = useMemo(
    () => pinned.map(camera => [camera.latitude!, camera.longitude!] as [number, number]),
    [pinned],
  )
  const center = useMemo<[number, number]>(() => (points.length ? points[0] : DEFAULT_CENTER), [points])

  return (
    <section className="map-shell">
      <div className="map-canvas">
        <MapContainer center={center} zoom={points.length ? 10 : 4} className="leaflet-dark" scrollWheelZoom>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <FitBounds points={points} />
          {pinned.map(camera => (
            <CircleMarker
              key={camera.id}
              center={[camera.latitude!, camera.longitude!]}
              radius={9}
              pathOptions={{
                color: camera.status === 'LIVE' ? '#39d98a' : '#ff5e6d',
                fillColor: camera.status === 'LIVE' ? '#39d98a' : '#ff5e6d',
                fillOpacity: 0.55,
                weight: 2,
              }}
            >
              <Popup>
                <div className="map-popup">
                  <strong>{camera.name}</strong>
                  <span>{camera.manufacturer} {camera.model}</span>
                  {camera.snapshot_url && <img src={camera.snapshot_url} alt={`${camera.name} snapshot`} />}
                  <small>
                    <MapPin size={10} />
                    {[camera.city, camera.country].filter(Boolean).join(', ') || 'Unknown'}
                    {camera.latitude != null && camera.longitude != null && ` · ${camera.latitude.toFixed(4)}, ${camera.longitude.toFixed(4)}`}
                  </small>
                  {camera.isp && <small><Globe size={10} />{camera.isp}</small>}
                  <button onClick={() => onFullscreen(camera)}><MonitorPlay size={12} />Open Live View</button>
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
        {!pinned.length && (
          <div className="map-empty">
            <MapPin size={30} />
            <strong>No geolocated cameras yet</strong>
            <span>Run an external scan or press “Update GeoIP” on an internet camera.</span>
          </div>
        )}
      </div>
      <aside className="map-side">
        <h3>Local Network <em>{localOnly.length}</em></h3>
        <p>RFC1918 addresses carry no public coordinates and are never sent to GeoIP services.</p>
        <div className="map-side-list">
          {localOnly.map(camera => (
            <div key={camera.id}>
              <CameraIcon size={13} />
              <div>
                <strong>{camera.name}</strong>
                <span>{camera.host || camera.ip} · {camera.status}</span>
              </div>
            </div>
          ))}
          {!localOnly.length && <p className="map-side-empty">Every camera has coordinates.</p>}
        </div>
      </aside>
    </section>
  )
}
