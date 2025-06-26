import { create } from 'zustand';

export interface RouteData {
  distance: string;
  duration: string;
  qualityScore: number;
  conditions: {
    good: number;
    moderate: number;
    poor: number;
  };
}

export interface GridCell {
  row: number;
  col: number;
  center_lat: number;
  center_lng: number;
  quality: string;
  color: string;
}

interface RouteStore {
  startCoords: [number, number] | null;
  endCoords: [number, number] | null;
  isSelecting: 'start' | 'end' | null;
  routeCoords: [number, number][];
  routeData: RouteData | null;
  roadConditions: string[];
  gridCells: GridCell[];
  gridData: any;
  isLoading: boolean;
  setStartCoords: (coords: [number, number]) => void;
  setEndCoords: (coords: [number, number]) => void;
  setSelecting: (mode: 'start' | 'end' | null) => void;
  setRouteCoords: (coords: [number, number][]) => void;
  resetRoute: () => void;
  generateRoute: () => Promise<void>;
  addRoadCondition: (condition: string) => void;
  loadGridData: () => Promise<void>;
}

// SmartRoute AI API base URL
const API_BASE_URL = 'https://smartroute-ai.onrender.com';

// Function to fetch route from SmartRoute AI API
const fetchSmartRoute = async (start: [number, number], end: [number, number]): Promise<{
  coordinates: [number, number][];
  distance: number;
  duration: number;
  gridPath: GridCell[];
}> => {
  try {
    console.log('Fetching route from SmartRoute AI API...');
    console.log('Start:', start, 'End:', end);
    
    const response = await fetch(`${API_BASE_URL}/route`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify({
        start_lat: start[0],
        start_lng: start[1],
        end_lat: end[0],
        end_lng: end[1]
      })
    });
    
    console.log('Response status:', response.status);
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('API Error:', errorText);
      throw new Error(`API returned ${response.status}: ${errorText}`);
    }
    
    const data = await response.json();
    console.log('SmartRoute AI Response:', data);
    
    if (!data.success) {
      throw new Error(data.message || 'Route generation failed');
    }
    
    return {
      coordinates: data.route_coordinates,
      distance: data.distance,
      duration: data.duration,
      gridPath: data.grid_path
    };
  } catch (error) {
    console.error('SmartRoute AI failed, trying fallback routing:', error);
    
    // Fallback to original routing method
    return await fetchRouteFromAPI(start, end);
  }
};

// Function to fetch route from OpenRouteService with proper format (fallback)
const fetchRouteFromAPI = async (start: [number, number], end: [number, number]): Promise<{
  coordinates: [number, number][];
  distance: number;
  duration: number;
  gridPath: GridCell[];
}> => {
  try {
    console.log('Fetching route from OpenRouteService API...');
    console.log('Start:', start, 'End:', end);
    
    // Use the correct OpenRouteService API format
    const url = `https://api.openrouteservice.org/v2/directions/driving-car/geojson`;
    
    const requestBody = {
      coordinates: [[start[1], start[0]], [end[1], end[0]]], // longitude, latitude format
      format: "geojson",
      instructions: false,
      elevation: false
    };

    console.log('Request body:', requestBody);

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify(requestBody)
    });
    
    console.log('Response status:', response.status);
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('API Error:', errorText);
      throw new Error(`API returned ${response.status}: ${errorText}`);
    }
    
    const data = await response.json();
    console.log('API Response:', data);
    
    if (!data.features || !data.features[0] || !data.features[0].geometry) {
      throw new Error('Invalid response format from routing API');
    }
    
    const coordinates = data.features[0].geometry.coordinates.map((coord: [number, number]) => [coord[1], coord[0]]);
    const distance = data.features[0].properties.summary.distance / 1000; // Convert to km
    const duration = data.features[0].properties.summary.duration / 60; // Convert to minutes
    
    console.log('Parsed route:', { coordinates: coordinates.length, distance, duration });
    
    return { coordinates, distance, duration, gridPath: [] };
  } catch (error) {
    console.error('OpenRouteService failed, trying alternative approach:', error);
    
    // Alternative: Try OSRM routing service as backup
    try {
      console.log('Trying OSRM routing service...');
      const osrmUrl = `https://router.project-osrm.org/route/v1/driving/${start[1]},${start[0]};${end[1]},${end[0]}?overview=full&geometries=geojson`;
      
      const osrmResponse = await fetch(osrmUrl);
      if (osrmResponse.ok) {
        const osrmData = await osrmResponse.json();
        console.log('OSRM Response:', osrmData);
        
        if (osrmData.routes && osrmData.routes[0]) {
          const coordinates = osrmData.routes[0].geometry.coordinates.map((coord: [number, number]) => [coord[1], coord[0]]);
          const distance = osrmData.routes[0].distance / 1000;
          const duration = osrmData.routes[0].duration / 60;
          
          console.log('OSRM route successful:', { coordinates: coordinates.length, distance, duration });
          return { coordinates, distance, duration, gridPath: [] };
        }
      }
    } catch (osrmError) {
      console.error('OSRM also failed:', osrmError);
    }
    
    console.log('All routing services failed, using enhanced interpolation...');
    
    // Enhanced fallback with more realistic road-like curves
    const coordinates: [number, number][] = [];
    const steps = 50; // More points for smoother curves
    
    // Calculate bearing for more realistic routing
    const deltaLat = end[0] - start[0];
    const deltaLng = end[1] - start[1];
    
    for (let i = 0; i <= steps; i++) {
      const progress = i / steps;
      
      // Add realistic waypoints that simulate road networks
      let latOffset = 0;
      let lngOffset = 0;
      
      // Create curved path that resembles real roads
      if (progress > 0.1 && progress < 0.9) {
        // Add some curves that simulate typical road patterns
        const curve1 = Math.sin(progress * Math.PI * 3) * 0.001;
        const curve2 = Math.cos(progress * Math.PI * 2) * 0.0008;
        
        latOffset = curve1 + (Math.random() - 0.5) * 0.0005;
        lngOffset = curve2 + (Math.random() - 0.5) * 0.0005;
      }
      
      const lat = start[0] + deltaLat * progress + latOffset;
      const lng = start[1] + deltaLng * progress + lngOffset;
      
      coordinates.push([lat, lng]);
    }
    
    // Calculate distance using Haversine formula
    const R = 6371;
    const dLat = (end[0] - start[0]) * Math.PI / 180;
    const dLon = (end[1] - start[1]) * Math.PI / 180;
    const a = 
      Math.sin(dLat/2) * Math.sin(dLat/2) +
      Math.cos(start[0] * Math.PI / 180) * Math.cos(end[0] * Math.PI / 180) * 
      Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    const distance = R * c;
    const duration = distance * 1.5; // More realistic estimate
    
    console.log('Fallback route generated:', { coordinates: coordinates.length, distance, duration });
    
    return { coordinates, distance, duration, gridPath: [] };
  }
};

export const useRouteStore = create<RouteStore>((set, get) => ({
  startCoords: null,
  endCoords: null,
  isSelecting: null,
  routeCoords: [],
  routeData: null,
  roadConditions: [],
  gridCells: [],
  gridData: null,
  isLoading: false,

  setStartCoords: (coords) => set({ startCoords: coords }),
  setEndCoords: (coords) => set({ endCoords: coords }),
  setSelecting: (mode) => set({ isSelecting: mode }),
  setRouteCoords: (coords) => set({ routeCoords: coords }),

  resetRoute: () => set({
    startCoords: null,
    endCoords: null,
    isSelecting: null,
    routeCoords: [],
    routeData: null,
    roadConditions: [],
    gridCells: [],
    isLoading: false
  }),

  loadGridData: async () => {
    try {
      console.log('Loading grid data from SmartRoute AI API...');
      const response = await fetch(`${API_BASE_URL}/grid`);
      
      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          set({ gridData: data.data });
          console.log('Grid data loaded successfully');
        }
      }
    } catch (error) {
      console.error('Failed to load grid data:', error);
    }
  },

  generateRoute: async () => {
    const { startCoords, endCoords, roadConditions } = get();
    if (!startCoords || !endCoords) return;

    console.log('Starting SmartRoute AI route generation...');
    set({ isLoading: true });

    try {
      // Fetch route from SmartRoute AI API
      const routeResult = await fetchSmartRoute(startCoords, endCoords);
      
      console.log('Route result:', routeResult);
      
      // Set grid path if available
      if (routeResult.gridPath && routeResult.gridPath.length > 0) {
        set({ gridCells: routeResult.gridPath });
        
        // Extract road conditions from grid path
        const conditions = routeResult.gridPath.map(cell => cell.quality);
        set({ roadConditions: conditions });
        console.log('Grid path conditions:', conditions);
      } else {
        // If no grid path, generate some mock conditions based on route segments
        let conditions = roadConditions;
        if (conditions.length === 0) {
          const segmentCount = Math.min(Math.max(Math.floor(routeResult.coordinates.length / 5), 3), 10);
          const mockConditions = ['Good', 'Satisfactory', 'Poor', 'Very Poor'];
          conditions = Array.from({ length: segmentCount }, () => 
            mockConditions[Math.floor(Math.random() * mockConditions.length)]
          );
          set({ roadConditions: conditions });
          console.log('Generated mock conditions:', conditions);
        }
      }

      // Generate route data based on road conditions
      const conditions = get().roadConditions;
      const goodCount = conditions.filter(c => c === 'Good').length;
      const satisfactoryCount = conditions.filter(c => c === 'Satisfactory').length;
      const poorCount = conditions.filter(c => c === 'Poor').length;
      const veryPoorCount = conditions.filter(c => c === 'Very Poor').length;
      
      const total = conditions.length;
      const good = Math.round((goodCount / total) * 100);
      const moderate = Math.round((satisfactoryCount / total) * 100);
      const poor = Math.round(((poorCount + veryPoorCount) / total) * 100);

      // Calculate quality score based on road conditions
      const qualityScore = Math.round(
        (goodCount * 100 + satisfactoryCount * 70 + poorCount * 40 + veryPoorCount * 10) / total
      );

      // Adjust duration based on road conditions (poor roads = slower travel)
      const conditionMultiplier = (goodCount * 1.0 + satisfactoryCount * 1.3 + poorCount * 1.6 + veryPoorCount * 2.0) / total;
      const adjustedDuration = Math.ceil(routeResult.duration * conditionMultiplier);

      const routeData: RouteData = {
        distance: routeResult.distance.toFixed(1),
        duration: `${adjustedDuration} min`,
        qualityScore,
        conditions: { good, moderate, poor }
      };

      console.log('Final route data:', routeData);

      set({ 
        routeCoords: routeResult.coordinates, 
        routeData,
        isLoading: false 
      });
    } catch (error) {
      console.error('Route generation failed completely:', error);
      set({ isLoading: false });
    }
  },

  addRoadCondition: (condition) => set((state) => ({
    roadConditions: [...state.roadConditions, condition]
  }))
}));
