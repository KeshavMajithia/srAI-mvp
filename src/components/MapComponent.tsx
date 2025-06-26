import { useEffect, useRef } from 'react';
import { useRouteStore } from '@/store/routeStore';
import { GridOverlay } from './GridOverlay';
import { useTheme } from './ThemeProvider';

export const MapComponent = () => {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const markersRef = useRef<any[]>([]);
  const routeLayerRef = useRef<any>(null);
  const tileLayerRef = useRef<any>(null);

  const {
    startCoords,
    endCoords,
    isSelecting,
    routeCoords,
    roadConditions,
    setStartCoords,
    setEndCoords,
    setSelecting,
    loadGridData
  } = useRouteStore();

  const { theme } = useTheme();

  useEffect(() => {
    if (!mapRef.current) return;

    // Dynamic import of Leaflet to avoid SSR issues
    Promise.all([
      import('leaflet'),
      import('leaflet/dist/leaflet.css')
    ]).then(([L]) => {
      // Fix for default markers
      delete (L.Icon.Default.prototype as any)._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
        iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
      });

      // Initialize map
      if (!mapInstanceRef.current) {
        mapInstanceRef.current = L.map(mapRef.current!, {
          center: [28.6139, 77.2090], // Delhi coordinates
          zoom: 10, // Reduced zoom to show more area
          zoomControl: true,
          attributionControl: true
        });
      }

      // Remove previous tile layer if exists
      if (tileLayerRef.current) {
        mapInstanceRef.current.removeLayer(tileLayerRef.current);
        tileLayerRef.current = null;
      }

      // Add tile layer based on theme
      if (theme === 'dark') {
        tileLayerRef.current = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
          subdomains: 'abcd',
          maxZoom: 20
        }).addTo(mapInstanceRef.current);
      } else {
        tileLayerRef.current = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
          subdomains: 'abcd',
          maxZoom: 20
        }).addTo(mapInstanceRef.current);
      }

      // Add click handler
      mapInstanceRef.current.on('click', (e: any) => {
        const { lat, lng } = e.latlng;
        
        if (isSelecting === 'start') {
          setStartCoords([lat, lng]);
          // Automatically switch to end location selection
          setSelecting('end');
        } else if (isSelecting === 'end') {
          setEndCoords([lat, lng]);
          setSelecting(null);
        }
      });

      // Load grid data on map initialization
      loadGridData();

      // Clear existing markers
      markersRef.current.forEach(marker => {
        mapInstanceRef.current.removeLayer(marker);
      });
      markersRef.current = [];

      // Add start marker
      if (startCoords) {
        const startIcon = L.icon({
          iconUrl: 'data:image/svg+xml;base64,' + btoa(`
            <svg width="25" height="41" viewBox="0 0 25 41" xmlns="http://www.w3.org/2000/svg">
              <path d="M12.5 0C5.6 0 0 5.6 0 12.5C0 19.4 12.5 41 12.5 41S25 19.4 25 12.5C25 5.6 19.4 0 12.5 0Z" fill="#22c55e"/>
              <circle cx="12.5" cy="12.5" r="4" fill="white"/>
            </svg>
          `),
          iconSize: [25, 41],
          iconAnchor: [12, 41],
          popupAnchor: [1, -34]
        });

        const startMarker = L.marker(startCoords, { icon: startIcon })
          .bindPopup('<b>Start Location</b><br>Click to begin your journey')
          .addTo(mapInstanceRef.current);
        
        markersRef.current.push(startMarker);
      }

      // Add end marker
      if (endCoords) {
        const endIcon = L.icon({
          iconUrl: 'data:image/svg+xml;base64,' + btoa(`
            <svg width="25" height="41" viewBox="0 0 25 41" xmlns="http://www.w3.org/2000/svg">
              <path d="M12.5 0C5.6 0 0 5.6 0 12.5C0 19.4 12.5 41 12.5 41S25 19.4 25 12.5C25 5.6 19.4 0 12.5 0Z" fill="#ef4444"/>
              <circle cx="12.5" cy="12.5" r="4" fill="white"/>
            </svg>
          `),
          iconSize: [25, 41],
          iconAnchor: [12, 41],
          popupAnchor: [1, -34]
        });

        const endMarker = L.marker(endCoords, { icon: endIcon })
          .bindPopup('<b>Destination</b><br>Your journey ends here')
          .addTo(mapInstanceRef.current);
        
        markersRef.current.push(endMarker);
      }

      // Add route with road condition colors
      if (routeCoords.length > 0) {
        if (routeLayerRef.current) {
          mapInstanceRef.current.removeLayer(routeLayerRef.current);
        }

        // Create a feature group to hold all route segments
        routeLayerRef.current = L.featureGroup();

        // Color mapping for road conditions
        const getConditionColor = (condition: string) => {
          switch (condition) {
            case 'Good': return '#22c55e';
            case 'Satisfactory': return '#f97316';
            case 'Poor': return '#ef4444';
            case 'Very Poor': return '#000000';
            default: return '#3b82f6';
          }
        };

        // Draw route segments with different colors based on road conditions
        for (let i = 0; i < routeCoords.length - 1; i++) {
          const condition = roadConditions[i % roadConditions.length] || 'Good';
          const color = getConditionColor(condition);
          
          const segment = L.polyline(
            [routeCoords[i], routeCoords[i + 1]], 
            {
              color: color,
              weight: 6,
              opacity: 0.8
            }
          );
          
          routeLayerRef.current.addLayer(segment);
        }

        routeLayerRef.current.addTo(mapInstanceRef.current);

        // Fit map bounds to show entire route
        const group = L.featureGroup([routeLayerRef.current, ...markersRef.current]);
        mapInstanceRef.current.fitBounds(group.getBounds(), { padding: [20, 20] });
      }

      // Update cursor style
      if (mapInstanceRef.current) {
        const container = mapInstanceRef.current.getContainer();
        if (isSelecting) {
          container.style.cursor = 'crosshair';
        } else {
          container.style.cursor = '';
        }
      }
    });

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, [startCoords, endCoords, isSelecting, routeCoords, roadConditions, setStartCoords, setEndCoords, setSelecting, loadGridData, theme]);

  return (
    <div className="relative w-full h-full">
      <div 
        ref={mapRef} 
        className="w-full h-full"
        style={{ minHeight: '400px' }}
      />
      
      {/* Grid Overlay Component */}
      {mapInstanceRef.current && (
        <GridOverlay mapInstance={mapInstanceRef.current} />
      )}
      
      {isSelecting && (
        <div className="absolute top-4 left-1/2 transform -translate-x-1/2 bg-background border border-border rounded-lg px-4 py-2 shadow-lg z-[1000]">
          <p className="text-sm font-medium">
            {isSelecting === 'start' 
              ? 'Click on the map to select your start location (then automatically select destination)'
              : 'Click on the map to select your destination location'
            }
          </p>
        </div>
      )}
    </div>
  );
};
