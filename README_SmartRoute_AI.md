# 🛣️ SmartRoute AI - Grid-Based Intelligent Routing System

SmartRoute AI is an innovative routing system that uses a 20x20 grid overlay on Delhi NCR to find the cleanest possible paths based on road surface conditions. The system combines machine learning-based road quality classification with intelligent pathfinding algorithms to provide optimal routes.

## 🎯 Project Overview

### What We Have:
- **Trained PyTorch Model**: Classifies road surface images into 4 quality classes:
  - 🟢 **Good**
  - 🟠 **Satisfactory** 
  - 🔴 **Poor**
  - 🟤 **Very Poor**
- **Frontend**: React + TypeScript + Leaflet map interface
- **Dataset**: ~2000 labeled road images for training and simulation

### What We Built:
- **20x20 Grid System**: Divides Delhi NCR into 400 cells with quality assignments
- **Quality-Aware Pathfinding**: Finds routes prioritizing better road conditions
- **Real-World Integration**: Converts grid paths to actual road routes using OSRM
- **Interactive Visualization**: Shows grid overlay and route quality on map

## 🏗️ Architecture

### Backend (Python)
```
smartroute_grid.py      # Core grid system and pathfinding
api_server.py           # FastAPI server for frontend integration
grid_visualizer.py      # Visualization and analysis tools
requirements.txt        # Python dependencies
```

### Frontend (React + TypeScript)
```
src/
├── components/
│   ├── MapComponent.tsx    # Main map interface
│   ├── GridOverlay.tsx     # Grid visualization overlay
│   └── ...
├── store/
│   └── routeStore.ts       # State management with API integration
└── ...
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Python dependencies
pip install -r requirements.txt

# Frontend dependencies
npm install
```

### 2. Start the Backend API Server

```bash
python api_server.py
```

The API server will start at `http://localhost:8000` with automatic documentation at `http://localhost:8000/docs`.

### 3. Start the Frontend

```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`.

### 4. Test the System

```bash
# Run the grid visualizer to see the system in action
python grid_visualizer.py
```

This will generate:
- `grid_visualization.png` - Static grid visualization
- `smartroute_interactive_map.html` - Interactive map with grid
- `grid_data.json` - Grid data export

## 🧠 How It Works

### 1. Grid Generation
- **Delhi NCR Bounds**: Latitude 28.4-28.9, Longitude 76.8-77.4
- **Grid Size**: 20x20 = 400 cells total
- **Cell Properties**: row, col, lat_bounds, lng_bounds, quality, center_coordinates

### 2. Quality Assignment
- **Realistic Distribution**: 40% Good, 30% Satisfactory, 20% Poor, 10% Very Poor
- **Spatial Correlation**: Adjacent cells tend to have similar qualities
- **Color Coding**:
  - 🟢 Green: Good roads
  - 🟠 Orange: Satisfactory roads  
  - 🔴 Red: Poor roads
  - 🟤 Brown: Very Poor roads
  - ⚫ Gray: Unknown/Unclassified

### 3. Pathfinding Algorithm
The system uses a quality-aware pathfinding algorithm that:

1. **Starts** at the source grid cell
2. **Evaluates** neighboring cells based on:
   - Distance to goal (30% weight)
   - Road quality (70% weight)
3. **Selects** the best neighbor using combined scoring
4. **Continues** until reaching the destination
5. **Returns** the complete grid path

### 4. Route Generation
- **Grid Path → Real Route**: Uses OSRM routing service
- **Waypoints**: Converts grid cell centers to routing waypoints
- **Fallback**: Generates approximate routes if API fails

## 📊 API Endpoints

### GET `/grid`
Returns the complete 20x20 grid data with quality assignments.

### POST `/route`
Finds the cleanest route between two coordinates.

**Request:**
```json
{
  "start_lat": 28.6139,
  "start_lng": 77.2090,
  "end_lat": 28.7041,
  "end_lng": 77.1025
}
```

**Response:**
```json
{
  "success": true,
  "route_coordinates": [[lat, lng], ...],
  "distance": 12.5,
  "duration": 18.7,
  "grid_path": [
    {
      "row": 10,
      "col": 15,
      "center_lat": 28.65,
      "center_lng": 77.15,
      "quality": "Good",
      "color": "#22c55e"
    }
  ],
  "message": "Route generated successfully"
}
```

### GET `/grid/statistics`
Returns grid statistics and quality distribution.

### GET `/health`
Health check endpoint.

## 🎨 Frontend Features

### Interactive Map
- **Grid Overlay**: Shows 20x20 grid with color-coded quality
- **Route Visualization**: Displays routes with quality-based coloring
- **Click Selection**: Select start and destination points
- **Real-time Updates**: Grid and route updates as you interact

### Route Information
- **Distance & Duration**: Calculated based on route and road conditions
- **Quality Score**: Overall route quality (0-100)
- **Condition Breakdown**: Percentage of each road quality type

## 🔧 Customization

### Grid Configuration
```python
# In smartroute_grid.py
grid = SmartRouteGrid(grid_size=20)  # Change grid size
```

### Quality Weights
```python
# Adjust pathfinding priorities
quality_weights = {
    RoadQuality.GOOD: 100,        # Highest priority
    RoadQuality.SATISFACTORY: 70,
    RoadQuality.POOR: 40,
    RoadQuality.VERY_POOR: 10     # Lowest priority
}
```

### Pathfinding Algorithm
```python
# In find_cleanest_path method
combined_score = quality_score * 0.7 + distance_score * 0.3
# Adjust weights: 0.7 for quality, 0.3 for distance
```

## 📈 Analysis Tools

### Grid Statistics
```bash
python grid_visualizer.py
```

Provides:
- Quality distribution analysis
- Overall network quality score
- Visual grid representation
- Pathfinding demonstrations

### Sample Dataset
The system includes a sample dataset of 2000 road images with realistic quality distribution for testing and demonstration.

## 🚧 Future Enhancements

### Planned Features
1. **Real-time Updates**: Live road condition updates
2. **Machine Learning Integration**: Connect to actual road classification model
3. **Traffic Integration**: Combine with real-time traffic data
4. **Multi-modal Routing**: Support for different transportation modes
5. **User Feedback**: Allow users to report road conditions

### Technical Improvements
1. **Performance Optimization**: Caching and parallel processing
2. **Scalability**: Support for larger regions and finer grids
3. **Mobile App**: Native mobile application
4. **Offline Support**: Local routing without internet

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **OpenStreetMap**: For map data and routing
- **OSRM**: For routing services
- **Leaflet**: For interactive maps
- **FastAPI**: For the backend API framework

---

**SmartRoute AI** - Making every journey smoother through intelligent routing! 🛣️✨ 