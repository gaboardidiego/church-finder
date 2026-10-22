import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Position, Result } from '../types';

const VIENNA: L.LatLngTuple = [48.2082, 16.3738];

// Default Leaflet icons break under bundlers, so use simple divIcons.
const churchIcon = (active: boolean): L.DivIcon =>
  L.divIcon({
    className: `church-marker${active ? ' active' : ''}`,
    html: '⛪',
    iconSize: [30, 30],
  });
const originIcon = L.divIcon({ className: 'origin-marker', html: '📍', iconSize: [30, 30] });

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
    this.map = L.map(element).setView(VIENNA, 12);
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

  setOrigin(position: Position | null, fly = false): void {
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
    if (fly) this.map.setView(latlng, Math.max(this.map.getZoom(), 14));
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
      if (services.length > 0) {
        popup.append(document.createElement('br'));
        popup.append(
          services
            .slice(0, 4)
            .map((s) => `${s.startTime} ${s.language}`)
            .join(' · '),
        );
      }
      marker.bindPopup(popup);
      marker.on('click', () => this.handlers.onSelect(church.id));
      marker.addTo(this.layer);
      this.markers.set(church.id, marker);
    }
  }

  fitToResults(results: Result[]): void {
    const points = results
      .slice(0, 30)
      .map((r): L.LatLngTuple => [r.church.position.latitude, r.church.position.longitude]);
    if (this.origin) {
      const { lat, lng } = this.origin.getLatLng();
      points.push([lat, lng]);
    }
    if (points.length > 0)
      this.map.fitBounds(L.latLngBounds(points), { padding: [30, 30], maxZoom: 15 });
  }

  highlight(id: string | null, pan = false): void {
    for (const [key, marker] of this.markers) {
      marker.setIcon(churchIcon(key === id));
      marker.setZIndexOffset(key === id ? 500 : 0);
    }
    const marker = id ? this.markers.get(id) : undefined;
    if (marker && pan) this.map.panTo(marker.getLatLng());
  }
}
