import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { displayLanguage } from '../language';
import { messages, type Locale, type Messages } from '../i18n';
import type { Position, Result } from '../types';
import { serviceLabel } from './list';
import { verificationLabel } from './verification';

const NEAREST_WITH_PIN = 4;
const LOCATION_ZOOM = 13;
const IP_LOCATION_ZOOM = 9;
const AUSTRIA_AND_ITALY: L.LatLngTuple = [44.5, 13];

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
    this.map = L.map(element).setView(AUSTRIA_AND_ITALY, 5);
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

  showApproximateLocation(position: Position): void {
    this.map.setView([position.latitude, position.longitude], IP_LOCATION_ZOOM, { animate: false });
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

  setResults(
    results: Result[],
    text: Messages = messages.en,
    onRetry?: (id: string) => void,
    locale: Locale = 'en',
  ): void {
    this.layer.clearLayers();
    this.markers.clear();
    for (const { church, services } of results) {
      const marker = L.marker([church.position.latitude, church.position.longitude], {
        icon: churchIcon(false),
        title: church.name,
      });
      marker.bindPopup(
        this.popupContent({ church, services, distanceKm: null }, text, onRetry, locale),
        { autoPan: false },
      );
      marker.on('click', () => this.handlers.onSelect(church.id));
      marker.addTo(this.layer);
      this.markers.set(church.id, marker);
    }
  }

  updateSchedule(
    result: Result,
    text: Messages,
    onRetry: (id: string) => void,
    locale: Locale,
  ): void {
    this.markers
      .get(result.church.id)
      ?.setPopupContent(this.popupContent(result, text, onRetry, locale));
  }

  private popupContent(
    result: Result,
    text: Messages,
    onRetry: ((id: string) => void) | undefined,
    locale: Locale,
  ): HTMLElement {
    const { church, services } = result;
    const popup = document.createElement('div');
    const title = document.createElement('strong');
    title.textContent = church.name;
    popup.append(title);
    const verification = verificationLabel(church, locale);
    if (verification) popup.append(document.createElement('br'), verification);
    const status = church.scheduleStatus;
    if (status === 'unloaded' || status === 'loading' || status === 'error') {
      popup.append(document.createElement('br'));
      popup.append(
        status === 'error'
          ? text.schedulesFailed
          : status === 'loading'
            ? text.schedulesLoading
            : text.schedulesPending,
      );
      if (status === 'error') {
        const retry = document.createElement('button');
        retry.type = 'button';
        retry.textContent = text.retry;
        retry.addEventListener('click', (event) => {
          event.stopPropagation();
          onRetry?.(church.id);
        });
        popup.append(' ', retry);
      }
    } else {
      const labels = services
        .map((s) =>
          church.serviceIndex
            ? serviceLabel(s, true, locale)
            : [s.startTime, displayLanguage(s.language)].filter(Boolean).join(' '),
        )
        .filter(Boolean)
        .slice(0, 4);
      if (labels.length) popup.append(document.createElement('br'), labels.join(' · '));
      else if (church.serviceIndex)
        popup.append(document.createElement('br'), text.noServicesListed);
    }
    return popup;
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

  focusChurch(results: Result[], position: Position): void {
    if (
      this.map.getZoom() >= LOCATION_ZOOM &&
      this.map.getBounds().contains([position.latitude, position.longitude])
    )
      return;
    this.fitToResults(results, position);
  }

  highlight(id: string | null): void {
    for (const [key, marker] of this.markers) {
      marker.setIcon(churchIcon(key === id));
      marker.setZIndexOffset(key === id ? 500 : 0);
    }
  }
}
