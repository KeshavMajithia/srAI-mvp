# SmartRoute AI

SmartRoute AI is an MVP for intelligent, road health-aware route planning. It combines a Flask backend (Python) with a modern React frontend (TypeScript, Vite, Tailwind, shadcn-ui) to deliver:
- Real-time route planning and visualization
- Road quality analytics and evidence collection
- Reinforcement learning agents for grid and routing updates
- Mobile-friendly, dark mode-enabled UI

---

## Table of Contents
- [Project Overview](#project-overview)
- [Backend (Flask API)](#backend-flask-api)
- [Frontend (React App)](#frontend-react-app)
- [State Management](#state-management)
- [Key Features](#key-features)
- [Setup & Development](#setup--development)
- [Deployment](#deployment)
- [Custom Domain](#custom-domain)

---

## Project Overview
SmartRoute AI divides the Delhi NCR region into a grid, predicts road quality for each cell, and allows users to:
- Plan routes that avoid poor-quality roads
- Upload images as evidence to improve road quality predictions
- Give feedback on routes, which is used to improve the RL agents
- View a color-coded map and interact with the grid

---

## Backend (Flask API)
- **Grid Initialization:**
  - Loads or generates a 20x20 grid for Delhi NCR, with each cell assigned a road quality (Good, Satisfactory, Poor, Very Poor, Unknown).
  - Uses a model-based script to predict initial qualities, and updates as new evidence arrives.
- **Endpoints:**
  - `/grid`: Returns the current grid with all cell data.
  - `/route`: Returns a route between two coordinates, optimizing for road quality.
  - `/route/rl`: Uses a reinforcement learning agent for route planning.
  - `/upload-image`: Accepts image uploads, runs model prediction, and updates the grid/evidence logs.
  - `/feedback`: Accepts user feedback on routes, updates logs and agents.
  - `/logs/*`: Returns logs for routes, feedback, grid updates, and cross-agent events.
  - `/monitor/rl-agent` and `/monitor/rl-feedback`: Returns RL agent performance and feedback stats.
  - `/evidence/analytics` and `/feedback/analytics`: Returns analytics for evidence and feedback.
- **RL Agents:**
  - Grid update agent: Decides when/how to update cell qualities based on evidence and feedback.
  - Routing agent: Learns to plan routes that maximize good road segments and user satisfaction.
- **Data Storage:**
  - Uses JSON files for logs, grid state, and evidence.
  - Uploaded images are stored in `uploaded_images/`.

---

## Frontend (React App)
- **Map View:**
  - Interactive map (Leaflet) with color-coded grid overlay.
  - Start/end pin selection by tapping/clicking the map.
  - Route visualization with segments colored by road quality.
  - Fully responsive and mobile-friendly.
  - Dark mode support (map tiles and UI adapt to theme).
- **Sidebar:**
  - Route planning controls (select start/end, generate/reset route).
  - Road analysis: Upload images for AI-based road quality prediction.
  - Route summary: Distance, duration, quality score, and breakdown.
  - RL route summary and feedback (thumbs up/down for route quality).
  - Analytics: Shows RL agent stats and feedback trends.
  - On mobile, the sidebar acts as a drawer overlaying the map.
- **Header:**
  - App branding and title.
  - Sidebar toggle (always visible on mobile).
  - Theme toggle (light/dark mode).

---

## State Management
- Uses [Zustand](https://github.com/pmndrs/zustand) for global state:
  - Stores start/end coordinates, route data, grid data, and UI state.
  - Handles async actions for route generation, grid loading, and feedback.
  - Ensures state is synced between map, sidebar, and overlays.

---

## Key Features
- **Grid-based Road Health:**
  - Each cell in the grid is colored by predicted road quality.
  - Hover/click on cells to see details (confidence, last updated, evidence count).
- **Route Planning:**
  - Click/tap to select start and end points.
  - Route is calculated to avoid poor/very poor roads when possible.
  - RL agent can be used for advanced route planning.
- **Evidence Collection:**
  - Upload images for any grid cell; backend predicts quality and updates the grid.
  - Evidence is logged and used to improve model predictions.
- **User Feedback:**
  - After a route is generated, users can give positive/negative feedback.
  - Feedback is logged and used to train RL agents and update grid cells.
- **Analytics:**
  - View RL agent performance, feedback trends, and evidence stats in the sidebar.
- **Mobile & Dark Mode:**
  - Fully responsive layout; sidebar becomes a drawer on mobile.
  - Map and UI adapt to dark mode instantly.

---

## Setup & Development

### Prerequisites
- Node.js & npm (for frontend)
- Python 3.x (for backend)
- (Optional) PyTorch and model weights for advanced grid prediction

### Frontend
```sh
cd <project_root>
npm install
npm run dev
```
- Visit `http://localhost:5173` (or as shown in your terminal)

### Backend
```sh
cd <project_root>
python api_server.py
```
- Backend runs on `http://localhost:8001`

### Model/Evidence
- Place model weights in `RoadHealth/` as needed.
- Upload images via the sidebar to generate evidence and update the grid.

---

## Deployment
- Build the frontend with `npm run build` and serve the `dist/` folder.
- Deploy the backend (Flask app) to your preferred server or cloud platform.
- Set up CORS and environment variables as needed for production.

---

## Custom Domain
- You can connect a custom domain using your hosting provider's instructions.

---

## Credits
- Developed as an MVP for intelligent, road health-aware routing.
- Combines open-source geospatial, ML, and UI technologies.
