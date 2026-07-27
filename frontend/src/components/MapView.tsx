import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Viewport } from '../types';
import { Maximize2, Layers } from 'lucide-react';

interface MapViewProps {
  geojson: string | null;
  viewport: Viewport;
  onViewportChange: (vp: Viewport) => void;
}

export const MapView: React.FC<MapViewProps> = ({ geojson, viewport, onViewportChange }) => {
  const mapRef = useRef<L.Map | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const geojsonGroupRef = useRef<L.GeoJSON | null>(null);

  // Initialize Leaflet Map once
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current, {
      center: viewport.center,
      zoom: viewport.zoom,
      zoomControl: false,
    });

    // Dark Matter CartoDB tiles for tactical dark aesthetics
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
      subdomains: 'abcd',
      maxZoom: 19,
    }).addTo(map);

    L.control.zoom({ position: 'bottomright' }).addTo(map);

    map.on('moveend', () => {
      const center = map.getCenter();
      const zoom = map.getZoom();
      const bounds = map.getBounds();
      onViewportChange({
        center: [center.lat, center.lng],
        zoom,
        bounds: [
          [bounds.getSouthWest().lat, bounds.getSouthWest().lng],
          [bounds.getNorthEast().lat, bounds.getNorthEast().lng],
        ],
      });
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Update GeoJSON layer on map when geojson changes
  useEffect(() => {
    if (!mapRef.current) return;

    if (geojsonGroupRef.current) {
      mapRef.current.removeLayer(geojsonGroupRef.current);
      geojsonGroupRef.current = null;
    }

    if (!geojson) return;

    try {
      const parsed = JSON.parse(geojson);
      if (!parsed || (parsed.type === 'FeatureCollection' && (!parsed.features || parsed.features.length === 0))) {
        return;
      }

      const layer = L.geoJSON(parsed, {
        style: () => ({
          color: '#f59e0b',
          weight: 3,
          opacity: 0.85,
          fillColor: '#d97706',
          fillOpacity: 0.35,
        }),
        pointToLayer: (_feature, latlng) => {
          return L.circleMarker(latlng, {
            radius: 7,
            fillColor: '#f59e0b',
            color: '#ffffff',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.85,
          });
        },
        onEachFeature: (feature, l) => {
          if (feature.properties && Object.keys(feature.properties).length > 0) {
            const popupContent = Object.entries(feature.properties)
              .map(([k, v]) => `<strong style="color: #f59e0b; text-transform: uppercase;">${k}:</strong> <span style="color: #ffffff;">${v}</span>`)
              .join('<br/>');
            l.bindPopup(`
              <div style="font-family: 'Courier New', Courier, monospace; font-size: 11px; color: #ffffff;">
                <div style="color: #f59e0b; font-weight: bold; border-bottom: 1px solid rgba(245, 158, 11, 0.3); padding-bottom: 3px; margin-bottom: 5px; font-size: 9px; letter-spacing: 1px;">&gt; GEOJSON_FEATURE_INTEL</div>
                <div>${popupContent}</div>
              </div>
            `);
          }
        },
      }).addTo(mapRef.current);

      geojsonGroupRef.current = layer;

      // Fit map bounds to show rendered GeoJSON
      const bounds = layer.getBounds();
      if (bounds.isValid()) {
        mapRef.current.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 });
      }
    } catch (e) {
      console.error('Failed to parse GeoJSON for Leaflet:', e);
    }
  }, [geojson]);

  const handleResetView = () => {
    if (mapRef.current) {
      mapRef.current.setView([45.4642, 9.19], 13);
    }
  };

  return (
    <div className="relative w-full h-full bg-[#050505] overflow-hidden select-none font-mono">
      <div ref={containerRef} className="w-full h-full z-0" />

      {/* Tactical Corner Bracket Overlays */}
      <div className="absolute inset-3 pointer-events-none z-10">
        <div className="absolute top-0 left-0 w-5 h-5 border-t-2 border-l-2 border-[#f59e0b] opacity-60" />
        <div className="absolute top-0 right-0 w-5 h-5 border-t-2 border-r-2 border-[#f59e0b] opacity-60" />
        <div className="absolute bottom-0 left-0 w-5 h-5 border-b-2 border-l-2 border-[#f59e0b] opacity-60" />
        <div className="absolute bottom-0 right-0 w-5 h-5 border-b-2 border-r-2 border-[#f59e0b] opacity-60" />
      </div>

      {/* Map Control Bar Overlay */}
      <div className="absolute top-4 right-4 z-10 flex items-center space-x-2">
        <button
          onClick={handleResetView}
          className="p-2 rounded bg-[#050505]/90 border border-[#f59e0b]/40 hover:bg-[#f59e0b] hover:text-black text-[#f59e0b] transition-all shadow-lg backdrop-blur-md"
          title="Reset to Milan Center"
        >
          <Maximize2 className="w-4 h-4" />
        </button>
      </div>

      {/* Viewport Coordinates Telemetry Overlay matching Auth Portal */}
      <div className="absolute bottom-4 left-4 z-10 px-3.5 py-2 rounded bg-[#050505]/90 border border-[#f59e0b]/30 border-r-4 border-r-[#f59e0b] text-[10px] font-mono text-[#f59e0b] backdrop-blur-md flex items-center space-x-3 shadow-2xl">
        <span className="flex items-center space-x-1.5 font-bold">
          <Layers className="w-3.5 h-3.5 text-[#f59e0b]" />
          <span>MAP_TELEMETRY</span>
        </span>
        <span>LAT: {viewport.center[0].toFixed(4)}</span>
        <span>LON: {viewport.center[1].toFixed(4)}</span>
        <span className="text-[#4ade80] font-bold">ZOOM: {viewport.zoom}x</span>
      </div>
    </div>
  );
};
