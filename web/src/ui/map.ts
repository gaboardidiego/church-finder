import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { displayLanguage } from '../language';
import type { Position, Result } from '../types';

const NEAREST_WITH_PIN = 4;
const LOCATION_ZOOM = 13;
const AUSTRIA: L.LatLngTuple = [47.5162, 14.5501];

// Default Leaflet icons break under bundlers, so use simple divIcons.
const CROSS =
  '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M10.5 2h3v6.5H20v3h-6.5V22h-3V11.5H4v-3h6.5z"/></svg>';
const churchIcon = (active: boolean): L.DivIcon =>
  L.divIcon({
    className: `church-marker${active ? ' active' : ''}`,
    html: `<span class="pin">${CROSS}</span>`,
    iconSize: active ? [40, 48] : [32, 40],
    iconAnchor: active ? [20, 48] : [16, 40],
    popupAnchor: [0, -38],
  });
const originIcon = L.divIcon({
  className: 'origin-marker',
  html: '<span class="pulse"></span><span class="dot"></span>',
  iconSize: [28, 28],
  iconAnchor: [14, 14],
});

export interface MapHandlers {
  onPick: (position: Position) => void;
  onSelect: (id: string) => void;
}

export class ChurchMap {
  private map: L.Map;
  private markers = new Map<string, L.Marker>();
  private layer = L.layerGroup();
  private origin: L.Marker | null = null;

  constructor(
    element: HTMLElement,
    private handlers: MapHandlers,
  ) {
    this.map = L.map(element).setView(AUSTRIA, 7);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(this.map);
    this.layer.addTo(this.map);
    this.map.on('click', (e: L.LeafletMouseEvent) =>
      this.handlers.onPick({ latitude: e.latlng.lat, longitude: e.latlng.lng }),
    );
  }

  invalidate(): void {
    this.map.invalidateSize();
  }

  setOrigin(position: Position | null): void {
    if (this.origin) {
      this.origin.remove();
      this.origin = null;
    }
    if (!position) return;
    const latlng: L.LatLngTuple = [position.latitude, position.longitude];
    this.origin = L.marker(latlng, { icon: originIcon, draggable: true, zIndexOffset: 1000 })
      .on('dragend', (e) => {
        const { lat, lng } = (e.target as L.Marker).getLatLng();
        this.handlers.onPick({ latitude: lat, longitude: lng });
      })
      .addTo(this.map);
  }

  setResults(results: Result[]): void {
    this.layer.clearLayers();
    this.markers.clear();
    for (const { church, services } of results) {
      const marker = L.marker([church.position.latitude, church.position.longitude], {
        icon: churchIcon(false),
        title: church.name,
      });
      const popup = document.createElement('div');
      const title = document.createElement('strong');
      title.textContent = church.name;
      popup.append(title);
      const serviceLabels = services
        .map((s) => [s.startTime, displayLanguage(s.language)].filter(Boolean).join(' '))
        .filter(Boolean)
        .slice(0, 4);
      if (serviceLabels.length > 0) {
        popup.append(document.createElement('br'));
        popup.append(serviceLabels.join(' · '));
      }
      marker.bindPopup(popup);
      marker.on('click', () => this.handlers.onSelect(church.id));
      marker.addTo(this.layer);
      this.markers.set(church.id, marker);
    }
  }

  fitToResults(results: Result[], focus?: Position): void {
    // Results are distance-sorted when framing a location.
    const origin = focus ? L.latLng(focus.latitude, focus.longitude) : this.origin?.getLatLng();
    const nearby = origin ? results.slice(0, NEAREST_WITH_PIN) : results;
    const points = nearby.map((r): L.LatLngTuple => [
      r.church.position.latitude,
      r.church.position.longitude,
    ]);
    if (origin) {
      if (points.length === 0) {
        this.map.setView(origin, LOCATION_ZOOM);
        return;
      }
      points.push([origin.lat, origin.lng]);
    }
    if (points.length > 0) {
      this.map.fitBounds(L.latLngBounds(points), {
        padding: [30, 30],
        maxZoom: origin ? 16 : 15,
        animate: false,
      });
    }
  }

  highlight(id: string | null): void {
    for (const [key, marker] of this.markers) {
      marker.setIcon(churchIcon(key === id));
      marker.setZIndexOffset(key === id ? 500 : 0);
    }
  }
}
