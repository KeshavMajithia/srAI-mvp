import { useEffect, useRef, useState } from 'react';
import { useRouteStore } from '@/store/routeStore';

interface GridOverlayProps {
  mapInstance: any;
}

// Add a helper to format timestamps
function formatTimestamp(ts?: number) {
  if (!ts) return 'Unknown';
  const date = new Date(ts * 1000);
  return date.toLocaleString();
}

export const GridOverlay = ({ mapInstance }: GridOverlayProps) => {
  const { gridData, gridCells } = useRouteStore();
  const gridLayersRef = useRef<any[]>([]);
  const [tooltip, setTooltip] = useState<{ visible: boolean, x: number, y: number, cell: any | null }>({ visible: false, x: 0, y: 0, cell: null });
  const hoverTimerRef = useRef<NodeJS.Timeout | null>(null);
  const lastCellKeyRef = useRef<string | null>(null);

  // --- Tooltip logic using map mousemove ---
  useEffect(() => {
    if (!mapInstance || !gridData) return;

    function onMapMouseMove(e: any) {
      // Convert lat/lng to cell row/col
      const { lat, lng } = e.latlng;
      const gridSize = gridData.grid_size;
      const delhiBounds = gridData.delhi_bounds;
      const latStep = (delhiBounds.lat_max - delhiBounds.lat_min) / gridSize;
      const lngStep = (delhiBounds.lng_max - delhiBounds.lng_min) / gridSize;
      const row = Math.max(0, Math.min(Math.floor((lat - delhiBounds.lat_min) / latStep), gridSize - 1));
      const col = Math.max(0, Math.min(Math.floor((lng - delhiBounds.lng_min) / lngStep), gridSize - 1));
      const cellKey = `${row},${col}`;
      const cell = gridData.cells.find((c: any) => c.row === row && c.col === col);
      if (!cell) {
        if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
        setTooltip(t => t.visible ? { visible: false, x: 0, y: 0, cell: null } : t);
        lastCellKeyRef.current = null;
        return;
      }
      // If moved to a new cell, reset timer
      if (lastCellKeyRef.current !== cellKey) {
        if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
        setTooltip(t => t.visible ? { visible: false, x: 0, y: 0, cell: null } : t);
        hoverTimerRef.current = setTimeout(() => {
          setTooltip({
            visible: true,
            x: e.containerPoint.x + 20,
            y: e.containerPoint.y + 20,
            cell
          });
        }, 3000);
        lastCellKeyRef.current = cellKey;
      } else {
        // If already showing, update position
        setTooltip(t => t.visible ? { ...t, x: e.containerPoint.x + 20, y: e.containerPoint.y + 20 } : t);
      }
    }
    function onMapMouseOut() {
      if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
      setTooltip({ visible: false, x: 0, y: 0, cell: null });
      lastCellKeyRef.current = null;
    }
    mapInstance.on('mousemove', onMapMouseMove);
    mapInstance.on('mouseout', onMapMouseOut);
    return () => {
      mapInstance.off('mousemove', onMapMouseMove);
      mapInstance.off('mouseout', onMapMouseOut);
      if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
    };
  }, [mapInstance, gridData]);

  useEffect(() => {
    if (!mapInstance || !gridData) return;

    // Import Leaflet dynamically
    import('leaflet').then((L) => {
      // Clear existing grid layers
      gridLayersRef.current.forEach(layer => {
        mapInstance.removeLayer(layer);
      });
      gridLayersRef.current = [];

      // Add grid cells to map
      gridData.cells.forEach((cell: any) => {
        const lat_bounds = cell.lat_bounds;
        const lng_bounds = cell.lng_bounds;
        const quality = cell.quality;
        const color = cell.color;

        // Create rectangle coordinates
        const rectCoords = [
          [lat_bounds[0], lng_bounds[0]],
          [lat_bounds[0], lng_bounds[1]],
          [lat_bounds[1], lng_bounds[1]],
          [lat_bounds[1], lng_bounds[0]],
          [lat_bounds[0], lng_bounds[0]]
        ];

        // Create polygon for grid cell
        const polygon = L.polygon(rectCoords, {
          color: 'black',
          weight: 1,
          fillColor: color,
          fillOpacity: 0.3,
          opacity: 0.8,
          interactive: false,
        });

        // Custom mouseover/mouseout for floating tooltip
        polygon.on('mouseover', (e: any) => {
          if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
          const { containerPoint } = e;
          hoverTimerRef.current = setTimeout(() => {
            setTooltip({
              visible: true,
              x: containerPoint.x + 20,
              y: containerPoint.y + 20,
              cell
            });
          }, 3000); // 3 seconds
        });
        polygon.on('mousemove', (e: any) => {
          if (tooltip.visible) {
            setTooltip(t => ({ ...t, x: e.containerPoint.x + 20, y: e.containerPoint.y + 20 }));
          }
        });
        polygon.on('mouseout', () => {
          if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
          setTooltip({ visible: false, x: 0, y: 0, cell: null });
        });

        // Add popup with cell information
        const confidence = cell.confidence !== undefined ? (cell.confidence * 100).toFixed(0) + '%' : 'N/A';
        const lastUpdated = formatTimestamp(cell.last_updated);
        const numImages = cell.num_images !== undefined ? cell.num_images : 'N/A';
        const lowConfidence = cell.confidence !== undefined && cell.confidence < 0.7;
        polygon.bindPopup(`
          <div class="grid-cell-popup">
            <h4>Grid Cell (${cell.row}, ${cell.col})</h4>
            <p><strong>Quality:</strong> ${quality}</p>
            <p><strong>Confidence:</strong> ${confidence} ${lowConfidence ? '<span style=\'color:red\'>⚠️ Low</span>' : ''}</p>
            <p><strong>Last Updated:</strong> ${lastUpdated}</p>
            <p><strong>Images Used (Evidence):</strong> ${numImages}</p>
            <p><strong>Center:</strong> ${cell.center_lat.toFixed(4)}, ${cell.center_lng.toFixed(4)}</p>
          </div>
        `);

        polygon.addTo(mapInstance);
        gridLayersRef.current.push(polygon);
      });
    });

  }, [mapInstance, gridData]);

  useEffect(() => {
    if (!mapInstance || !gridCells.length) return;

    // Import Leaflet dynamically
    import('leaflet').then((L) => {
      // Highlight the path cells
      gridCells.forEach((cell, index) => {
        const lat_bounds = [cell.center_lat - 0.01, cell.center_lat + 0.01];
        const lng_bounds = [cell.center_lng - 0.01, cell.center_lng + 0.01];

        const rectCoords = [
          [lat_bounds[0], lng_bounds[0]],
          [lat_bounds[0], lng_bounds[1]],
          [lat_bounds[1], lng_bounds[1]],
          [lat_bounds[1], lng_bounds[0]],
          [lat_bounds[0], lng_bounds[0]]
        ];

        // Create highlighted polygon for path cell
        const pathPolygon = L.polygon(rectCoords, {
          color: '#3b82f6',
          weight: 3,
          fillColor: cell.color,
          fillOpacity: 0.7,
          opacity: 1,
          interactive: false,
        });

        // Add popup with path information
        pathPolygon.bindPopup(`
          <div class="path-cell-popup">
            <h4>Path Cell ${index + 1}</h4>
            <p><strong>Quality:</strong> ${cell.quality}</p>
            <p><strong>Position:</strong> (${cell.row}, ${cell.col})</p>
          </div>
        `);

        pathPolygon.addTo(mapInstance);
        gridLayersRef.current.push(pathPolygon);
      });
    });

  }, [mapInstance, gridCells]);

  // Floating tooltip component
  return (
    <>
      {tooltip.visible && tooltip.cell && (
        <div
          style={{
            position: 'fixed',
            left: tooltip.x,
            top: tooltip.y,
            background: 'rgba(30,30,30,0.97)',
            color: 'white',
            padding: '12px 16px',
            borderRadius: 8,
            zIndex: 99999,
            pointerEvents: 'none',
            minWidth: 220,
            boxShadow: '0 2px 12px rgba(0,0,0,0.35)',
            border: '2px solid #fff',
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Grid Cell ({tooltip.cell.row}, {tooltip.cell.col})</div>
          <div><strong>Quality:</strong> {tooltip.cell.quality}</div>
          <div>
            <strong>Confidence:</strong> {(tooltip.cell.confidence * 100).toFixed(0)}%
            {tooltip.cell.confidence < 0.7 && <span style={{ color: 'red', marginLeft: 6 }}>⚠️ Low</span>}
          </div>
          <div><strong>Last Updated:</strong> {formatTimestamp(tooltip.cell.last_updated)}</div>
          <div><strong>Images Used (Evidence):</strong> {tooltip.cell.num_images}</div>
          <div style={{ fontSize: 12, marginTop: 4, opacity: 0.7 }}>
            Center: {tooltip.cell.center_lat.toFixed(4)}, {tooltip.cell.center_lng.toFixed(4)}
          </div>
        </div>
      )}
    </>
  );
}; 