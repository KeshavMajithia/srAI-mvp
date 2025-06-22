import { useEffect, useRef } from 'react';
import { useRouteStore } from '@/store/routeStore';

interface GridOverlayProps {
  mapInstance: any;
}

export const GridOverlay = ({ mapInstance }: GridOverlayProps) => {
  const { gridData, gridCells } = useRouteStore();
  const gridLayersRef = useRef<any[]>([]);

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

        // Add popup with cell information
        polygon.bindPopup(`
          <div class="grid-cell-popup">
            <h4>Grid Cell (${cell.row}, ${cell.col})</h4>
            <p><strong>Quality:</strong> ${quality}</p>
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

  return null; // This component doesn't render anything visible
}; 