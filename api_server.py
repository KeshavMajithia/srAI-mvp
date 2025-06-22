import json
import random
import math
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests
import os

# --- LOAD MODEL-BASED GRID COLORS ---
model_grid_path = os.path.join(os.path.dirname(__file__), 'RoadHealth', 'grid_colors.json')
if os.path.exists(model_grid_path):
    with open(model_grid_path, 'r') as f:
        model_grid_colors = json.load(f)
else:
    model_grid_colors = None
    print('Warning: Model-based grid_colors.json not found. Using random grid.')

# Mapping from model label to display label and color
label_map = {
    'good': ('Good', '#22c55e'),
    'satisfactory': ('Satisfactory', '#f97316'),
    'poor': ('Poor', '#ef4444'),
    'very_poor': ('Very Poor', '#8b4513'),
}

# Updated Delhi NCR bounds to cover all satellite cities
delhi_bounds = {
    'lat_min': 28.25,  # Extends south to cover Faridabad
    'lat_max': 29.05,  # Extends north to cover Ghaziabad
    'lng_min': 76.65,  # Extends west to cover parts of Haryana
    'lng_max': 77.75   # Extends east to cover Greater Noida
}
grid_size = 20
grid = {}
lat_step = (delhi_bounds['lat_max'] - delhi_bounds['lat_min']) / grid_size
lng_step = (delhi_bounds['lng_max'] - delhi_bounds['lng_min']) / grid_size
qualities = ['Good', 'Satisfactory', 'Poor', 'Very Poor']
weights = [0.4, 0.3, 0.2, 0.1]
quality_colors = {'Good': '#22c55e', 'Satisfactory': '#f97316', 'Poor': '#ef4444', 'Very Poor': '#8b4513', 'Unknown': '#6b7280'}

for row in range(grid_size):
    for col in range(grid_size):
        lat_min = delhi_bounds['lat_min'] + row * lat_step
        lat_max = lat_min + lat_step
        lng_min = delhi_bounds['lng_min'] + col * lng_step
        lng_max = lng_min + lng_step
        cell_key = f'({row}, {col})'
        if model_grid_colors and cell_key in model_grid_colors:
            model_label = model_grid_colors[cell_key]
            quality, color = label_map.get(model_label, ('Unknown', '#6b7280'))
        else:
            # fallback to random
            quality = random.choices(qualities, weights=weights)[0]
            color = quality_colors.get(quality, '#6b7280')
        grid[f'{row},{col}'] = {
            'row': row, 'col': col,
            'center_lat': (lat_min + lat_max) / 2,
            'center_lng': (lng_min + lng_max) / 2,
            'quality': quality,
            'lat_bounds': [lat_min, lat_max],
            'lng_bounds': [lng_min, lng_max],
            'color': color
        }
print("Grid created successfully (model-based if available).")

# --- IMPROVED PATHFINDING & ROUTING LOGIC ---
def find_quality_constrained_cells(start_row, start_col, end_row, end_col):
    """
    Find cells that form a quality-constrained corridor between start and end.
    Instead of forcing paths through centers, we identify good-quality regions.
    """
    quality_priority = {"Good": 4, "Satisfactory": 3, "Poor": 2, "Very Poor": 1, "Unknown": 0}
    
    # Create bounding box around start and end with some buffer
    min_row = max(0, min(start_row, end_row) - 2)
    max_row = min(grid_size - 1, max(start_row, end_row) + 2)
    min_col = max(0, min(start_col, end_col) - 2)
    max_col = min(grid_size - 1, max(start_col, end_col) + 2)
    
    quality_cells = set()
    
    # Add all cells in the corridor that meet quality standards
    for row in range(min_row, max_row + 1):
        for col in range(min_col, max_col + 1):
            cell_quality = quality_priority.get(grid[f'{row},{col}']['quality'], 0)
            
            # Calculate if cell is roughly in the direction from start to end
            # This creates a "cone" of acceptable cells
            if start_row == end_row and start_col == end_col:
                direction_score = 1.0
            else:
                # Vector from start to current cell
                start_to_cell = (row - start_row, col - start_col)
                # Vector from start to end
                start_to_end = (end_row - start_row, end_col - start_col)
                
                # Calculate how aligned the vectors are
                if start_to_end[0] == 0 and start_to_end[1] == 0:
                    direction_score = 1.0
                else:
                    dot_product = start_to_cell[0] * start_to_end[0] + start_to_cell[1] * start_to_end[1]
                    magnitude_end = (start_to_end[0]**2 + start_to_end[1]**2)**0.5
                    magnitude_cell = (start_to_cell[0]**2 + start_to_cell[1]**2)**0.5
                    
                    if magnitude_cell == 0:
                        direction_score = 1.0
                    else:
                        direction_score = max(0, dot_product / (magnitude_end * magnitude_cell))
            
            # Include cell if it has decent quality OR is well-aligned with destination
            if cell_quality >= 2 or (cell_quality >= 1 and direction_score > 0.7):
                quality_cells.add((row, col))
    
    # Always include start and end
    quality_cells.add((start_row, start_col))
    quality_cells.add((end_row, end_col))
    
    return quality_cells

def get_direct_osrm_route_with_avoidance(start_lat, start_lng, end_lat, end_lng):
    """
    Get a direct route from OSRM, then check which grid cells it passes through.
    If it passes through too many poor-quality cells, we'll need to guide it.
    """
    # First, get the direct route
    url = f"http://router.project-osrm.org/route/v1/driving/{start_lng},{start_lat};{end_lng},{end_lat}?overview=full&geometries=geojson"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('routes'):
            route_coords_lng_lat = data['routes'][0]['geometry']['coordinates']
            route_coords = [[coord[1], coord[0]] for coord in route_coords_lng_lat]  # Convert to [lat, lng]
            
            # Analyze route quality
            poor_quality_count = 0
            total_segments = 0
            
            for lat, lng in route_coords[::10]:  # Sample every 10th point to avoid over-sampling
                row = max(0, min(int((lat - delhi_bounds['lat_min']) / lat_step), grid_size - 1))
                col = max(0, min(int((lng - delhi_bounds['lng_min']) / lng_step), grid_size - 1))
                cell = grid.get(f'{row},{col}')
                if cell and cell['quality'] in ['Poor', 'Very Poor']:
                    poor_quality_count += 1
                total_segments += 1
            
            # If less than 30% of the route is poor quality, use the direct route
            if total_segments == 0 or (poor_quality_count / total_segments) < 0.3:
                return route_coords, "direct"
            else:
                return route_coords, "needs_guidance"
                
    except requests.exceptions.RequestException as e:
        print(f"OSRM request failed: {e}")
    
    return [[start_lat, start_lng], [end_lat, end_lng]], "fallback"

def get_guided_route_with_waypoints(start_lat, start_lng, end_lat, end_lng, quality_cells):
    """
    Create strategic waypoints that guide the route through better quality areas
    without forcing it through cell centers.
    """
    start_row = max(0, min(int((start_lat - delhi_bounds['lat_min']) / lat_step), grid_size - 1))
    start_col = max(0, min(int((start_lng - delhi_bounds['lng_min']) / lng_step), grid_size - 1))
    end_row = max(0, min(int((end_lat - delhi_bounds['lat_min']) / lat_step), grid_size - 1))
    end_col = max(0, min(int((end_lng - delhi_bounds['lng_min']) / lng_step), grid_size - 1))
    
    # Find 1-2 strategic waypoints that guide through good quality areas
    waypoints = [(start_lat, start_lng)]
    
    # Calculate the journey distance
    total_distance = ((end_row - start_row)**2 + (end_col - start_col)**2)**0.5
    
    if total_distance > 3:  # Only add waypoints for longer journeys
        # Find a good intermediate cell roughly 1/3 and 2/3 of the way
        intermediate_points = []
        
        for fraction in [0.4, 0.7]:  # Slightly offset from exact thirds for more natural routing
            target_row = start_row + (end_row - start_row) * fraction
            target_col = start_col + (end_col - start_col) * fraction
            
            # Find the best quality cell near this target position
            best_cell = None
            best_quality_score = -1
            search_radius = 2
            
            for dr in range(-search_radius, search_radius + 1):
                for dc in range(-search_radius, search_radius + 1):
                    check_row = int(target_row + dr)
                    check_col = int(target_col + dc)
                    
                    if (0 <= check_row < grid_size and 0 <= check_col < grid_size and 
                        (check_row, check_col) in quality_cells):
                        
                        cell = grid[f'{check_row},{check_col}']
                        quality_scores = {"Good": 4, "Satisfactory": 3, "Poor": 2, "Very Poor": 1, "Unknown": 0}
                        quality_score = quality_scores.get(cell['quality'], 0)
                        
                        # Prefer cells closer to the target position among good quality ones
                        distance_penalty = (dr**2 + dc**2)**0.5
                        combined_score = quality_score - distance_penalty * 0.1
                        
                        if combined_score > best_quality_score:
                            best_quality_score = combined_score
                            best_cell = cell
            
            if best_cell and best_quality_score >= 2:  # Only add waypoint if it's decent quality
                # Add a point within the cell, but not necessarily at center
                # Use slight randomization to make routing more natural
                lat_offset = (random.random() - 0.5) * 0.3  # 30% of cell size
                lng_offset = (random.random() - 0.5) * 0.3
                
                waypoint_lat = best_cell['center_lat'] + lat_offset * lat_step
                waypoint_lng = best_cell['center_lng'] + lng_offset * lng_step
                
                # Ensure waypoint is within cell bounds
                waypoint_lat = max(best_cell['lat_bounds'][0], min(best_cell['lat_bounds'][1], waypoint_lat))
                waypoint_lng = max(best_cell['lng_bounds'][0], min(best_cell['lng_bounds'][1], waypoint_lng))
                
                intermediate_points.append((waypoint_lat, waypoint_lng))
        
        waypoints.extend(intermediate_points)
    
    waypoints.append((end_lat, end_lng))
    
    # Route through waypoints
    if len(waypoints) <= 2:
        # Direct route
        return get_direct_osrm_route_with_waypoints(waypoints)
    else:
        # Multi-waypoint route
        return get_direct_osrm_route_with_waypoints(waypoints)

def get_direct_osrm_route_with_waypoints(waypoints):
    """Get route through specific waypoints using OSRM"""
    if len(waypoints) < 2:
        return waypoints
        
    coords = ";".join([f"{lng},{lat}" for lat, lng in waypoints])
    url = f"http://router.project-osrm.org/route/v1/driving/{coords}?overview=full&geometries=geojson"
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if data.get('routes'):
            route_coords_lng_lat = data['routes'][0]['geometry']['coordinates']
            return [[coord[1], coord[0]] for coord in route_coords_lng_lat]
            
    except requests.exceptions.RequestException as e:
        print(f"OSRM waypoint routing failed: {e}")
    
    # Fallback: connect waypoints with straight lines
    return waypoints

# --- HTTP SERVER ---
class SmartRouteHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path == '/grid':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self._send_cors_headers()
            self.end_headers()
            grid_data = {'grid_size': grid_size, 'delhi_bounds': delhi_bounds, 'cells': list(grid.values())}
            self.wfile.write(json.dumps({'success': True, 'data': grid_data}).encode())
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'healthy'}).encode())
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Not Found'}).encode())

    def do_POST(self):
        if self.path == '/route':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                start_lat = data.get('start_lat')
                start_lng = data.get('start_lng')
                end_lat = data.get('end_lat')
                end_lng = data.get('end_lng')

                if not all([start_lat, start_lng, end_lat, end_lng]):
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self._send_cors_headers()
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'message': 'Missing coordinates'}).encode())
                    return

                # Determine start and end grid positions
                start_row = max(0, min(int((start_lat - delhi_bounds['lat_min']) / lat_step), grid_size - 1))
                start_col = max(0, min(int((start_lng - delhi_bounds['lng_min']) / lng_step), grid_size - 1))
                end_row = max(0, min(int((end_lat - delhi_bounds['lat_min']) / lat_step), grid_size - 1))
                end_col = max(0, min(int((end_lng - delhi_bounds['lng_min']) / lng_step), grid_size - 1))

                # First, try direct route and analyze its quality
                direct_route, route_status = get_direct_osrm_route_with_avoidance(start_lat, start_lng, end_lat, end_lng)
                
                if route_status == "direct":
                    # Direct route is good enough
                    full_route = direct_route
                    routing_method = "direct"
                else:
                    # Need to guide through better quality areas
                    quality_cells = find_quality_constrained_cells(start_row, start_col, end_row, end_col)
                    full_route = get_guided_route_with_waypoints(start_lat, start_lng, end_lat, end_lng, quality_cells)
                    routing_method = "guided"

                # Analyze route quality for response
                route_qualities = []
                quality_summary = {"Good": 0, "Satisfactory": 0, "Poor": 0, "Very Poor": 0, "Unknown": 0}
                
                for lat, lng in full_route[::5]:  # Sample every 5th point
                    row = max(0, min(int((lat - delhi_bounds['lat_min']) / lat_step), grid_size - 1))
                    col = max(0, min(int((lng - delhi_bounds['lng_min']) / lng_step), grid_size - 1))
                    cell = grid.get(f'{row},{col}')
                    quality = cell['quality'] if cell else 'Unknown'
                    route_qualities.append(quality)
                    quality_summary[quality] += 1

                # Calculate total distance
                total_distance = 0
                if len(full_route) > 1:
                    for i in range(len(full_route) - 1):
                        lat1, lon1 = full_route[i]
                        lat2, lon2 = full_route[i + 1]
                        # Approximate distance calculation
                        distance = math.sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2) * 111  # Rough km conversion
                        total_distance += distance

                response = {
                    'success': True,
                    'route_coordinates': full_route,
                    'distance': round(total_distance, 2),
                    'duration': round(total_distance * 2, 1),  # Rough duration estimate
                    'route_qualities': route_qualities,
                    'quality_summary': quality_summary,
                    'routing_method': routing_method,
                    'start_cell': {'row': start_row, 'col': start_col, 'quality': grid[f'{start_row},{start_col}']['quality']},
                    'end_cell': {'row': end_row, 'col': end_col, 'quality': grid[f'{end_row},{end_col}']['quality']}
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            
            except Exception as e:
                print(f"Error processing route request: {e}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'message': str(e)}).encode())
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Not Found'}).encode())


if __name__ == "__main__":
    server_address = ('localhost', 8001)
    httpd = HTTPServer(server_address, SmartRouteHandler)
    print("🚀 Starting SmartRoute AI API Server...")
    print(f"🌐 API available at: http://{server_address[0]}:{server_address[1]}")
    print("  GET /grid     - Get grid data")
    print("  POST /route   - Find route between coordinates")
    print("  GET /health   - Health check")
    print("\nPress Ctrl+C to stop the server")
    httpd.serve_forever()