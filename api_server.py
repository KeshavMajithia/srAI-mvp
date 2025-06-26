from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import random
import math
import requests
import os
import datetime
from RoadHealth.grid_update_agent import GridUpdateAgent
from RoadHealth.routing_agent import RoutingAgent
from werkzeug.utils import secure_filename
from RoadHealth.generate_grid_colors import predict_image
from collections import Counter
import string

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# --- LOAD MODEL-BASED GRID COLORS ---
model_grid_path = os.path.join(os.path.dirname(__file__), 'RoadHealth', 'grid_colors.json')
def regenerate_grid_if_unknown():
    from RoadHealth.generate_grid_colors import GRID_COLORS_PATH
    import subprocess
    print('Regenerating grid_colors.json with model predictions...')
    subprocess.run(['python', os.path.join(os.path.dirname(__file__), 'RoadHealth', 'generate_grid_colors.py')])
    with open(GRID_COLORS_PATH, 'r') as f:
        return json.load(f)

if os.path.exists(model_grid_path):
    with open(model_grid_path, 'r') as f:
        model_grid_colors = json.load(f)
    # Convert keys to 'row,col' format
    model_grid_colors = {k.replace('(', '').replace(')', '').replace(' ', ''): v for k, v in model_grid_colors.items()}
    # Check if most cells are 'Unknown' and regenerate if so
    unknown_count = sum(1 for v in model_grid_colors.values() if v.get('quality', '').lower() == 'unknown')
    if unknown_count > 0.8 * len(model_grid_colors):
        model_grid_colors = regenerate_grid_if_unknown()
        model_grid_colors = {k.replace('(', '').replace(')', '').replace(' ', ''): v for k, v in model_grid_colors.items()}
else:
    model_grid_colors = regenerate_grid_if_unknown()
    model_grid_colors = {k.replace('(', '').replace(')', '').replace(' ', ''): v for k, v in model_grid_colors.items()}

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

# Initialize grid
for row in range(grid_size):
    for col in range(grid_size):
        lat_min = delhi_bounds['lat_min'] + row * lat_step
        lat_max = lat_min + lat_step
        lng_min = delhi_bounds['lng_min'] + col * lng_step
        lng_max = lng_min + lng_step
        cell_key = f'{row},{col}'
        if model_grid_colors and cell_key in model_grid_colors:
            model_value = model_grid_colors[cell_key]
            if isinstance(model_value, dict):
                model_label = model_value.get('quality', 'unknown')
                confidence = model_value.get('confidence', 0.5)
                last_updated = model_value.get('last_updated', None)
                num_images = model_value.get('num_images', 0)
                color = model_value.get('color', '#6b7280')  # Use color from JSON
            else:
                model_label = model_value
                confidence = 0.5
                last_updated = None
                num_images = 0
                color = '#6b7280'
            quality = model_label if model_label in ['Good', 'Satisfactory', 'Poor', 'Very Poor'] else 'Unknown'
        else:
            # fallback to random
            quality = random.choices(qualities, weights=weights)[0]
            color = quality_colors.get(quality, '#6b7280')
            confidence = 0.5
            last_updated = None
            num_images = 0
        grid[cell_key] = {
            'row': row, 'col': col,
            'center_lat': (lat_min + lat_max) / 2,
            'center_lng': (lng_min + lng_max) / 2,
            'quality': quality,
            'lat_bounds': [lat_min, lat_max],
            'lng_bounds': [lng_min, lng_max],
            'color': color,
            'confidence': confidence,
            'last_updated': last_updated,
            'num_images': num_images
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

# --- FLASK ROUTES ---
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'})

@app.route('/grid', methods=['GET'])
def get_grid():
    grid_data = {
        'grid_size': grid_size, 
        'delhi_bounds': delhi_bounds, 
        'cells': list(grid.values()),
        'fields': ['row', 'col', 'center_lat', 'center_lng', 'quality', 'color', 'confidence', 'last_updated', 'num_images']
    }
    return jsonify({'success': True, 'data': grid_data})

@app.route('/route', methods=['POST'])
def find_route():
    try:
        data = request.get_json()
        
        start_lat = data.get('start_lat')
        start_lng = data.get('start_lng')
        end_lat = data.get('end_lat')
        end_lng = data.get('end_lng')

        if not all([start_lat, start_lng, end_lat, end_lng]):
            return jsonify({'success': False, 'message': 'Missing coordinates'}), 400

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
        
        log_route_request(start_lat, start_lng, end_lat, end_lng, response['route_coordinates'], response['route_qualities'], user_feedback=None)
        
        return jsonify(response)
    
    except Exception as e:
        print(f"Error processing route request: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/logs', methods=['GET'])
def get_logs():
    log_type = request.args.get('type', 'route')
    if log_type == 'grid':
        log_file = LOG_GRID_UPDATE_FILE
    else:
        log_file = LOG_ROUTE_FILE
    try:
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                logs = json.load(f)
        else:
            logs = []
        return jsonify({'success': True, 'logs': logs})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        'message': 'SmartRoute AI API',
        'endpoints': {
            'GET /health': 'Health check',
            'GET /grid': 'Get grid data',
            'POST /route': 'Find route between coordinates'
        }
    })

@app.route('/logs/feedback', methods=['GET'])
def get_feedback_logs():
    try:
        if os.path.exists(FEEDBACK_LOG_FILE):
            with open(FEEDBACK_LOG_FILE, 'r') as f:
                logs = json.load(f)
        else:
            logs = []
        return jsonify({'success': True, 'logs': logs[-50:]})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/logs/cross-agent', methods=['GET'])
def get_cross_agent_logs():
    try:
        if os.path.exists(CROSS_AGENT_LOG_FILE):
            with open(CROSS_AGENT_LOG_FILE, 'r') as f:
                logs = json.load(f)
        else:
            logs = []
        return jsonify({'success': True, 'logs': logs[-50:]})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/logs/routes', methods=['GET'])
def get_route_logs():
    try:
        if os.path.exists(LOG_ROUTE_FILE):
            with open(LOG_ROUTE_FILE, 'r') as f:
                logs = json.load(f)
        else:
            logs = []
        return jsonify({'success': True, 'logs': logs[-50:]})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/monitor/rl-agent', methods=['GET'])
def monitor_rl_agent():
    try:
        # Compute average green percentage and reward from recent routes
        if os.path.exists(LOG_ROUTE_FILE):
            with open(LOG_ROUTE_FILE, 'r') as f:
                logs = json.load(f)[-100:]
        else:
            logs = []
        green_percentages = []
        rewards = []
        for log in logs:
            coords = log.get('route', [])
            qualities = log.get('qualities', [])
            if qualities:
                green_pct = sum(1 for q in qualities if q == 'Good') / len(qualities)
                green_percentages.append(green_pct)
            if 'reward' in log:
                rewards.append(log['reward'])
        avg_green_pct = sum(green_percentages) / len(green_percentages) if green_percentages else 0
        avg_reward = sum(rewards) / len(rewards) if rewards else 0
        return jsonify({'success': True, 'avg_green_percentage': avg_green_pct, 'avg_reward': avg_reward})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/monitor/rl-feedback', methods=['GET'])
def monitor_rl_feedback():
    try:
        if os.path.exists(FEEDBACK_LOG_FILE):
            with open(FEEDBACK_LOG_FILE, 'r') as f:
                logs = json.load(f)
        else:
            logs = []
        pos = sum(1 for log in logs if log.get('feedback') == 'positive')
        neg = sum(1 for log in logs if log.get('feedback') == 'negative')
        total = pos + neg
        avg_feedback = (pos / total) if total > 0 else None
        return jsonify({'success': True, 'avg_feedback': avg_feedback, 'positive': pos, 'negative': neg, 'total': total})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# Logging utilities
LOG_ROUTE_FILE = os.path.join(os.path.dirname(__file__), 'route_logs.json')
LOG_GRID_UPDATE_FILE = os.path.join(os.path.dirname(__file__), 'grid_update_logs.json')
CROSS_AGENT_LOG_FILE = os.path.join(os.path.dirname(__file__), 'cross_agent_logs.json')
FEEDBACK_LOG_FILE = os.path.join(os.path.dirname(__file__), 'feedback_logs.json')

def log_route_request(start_lat, start_lng, end_lat, end_lng, route, qualities, user_feedback=None, reward=None):
    log_entry = {
        'timestamp': datetime.datetime.utcnow().isoformat(),
        'start': [start_lat, start_lng],
        'end': [end_lat, end_lng],
        'route': route,
        'qualities': qualities,
        'user_feedback': user_feedback
    }
    if reward is not None:
        log_entry['reward'] = reward
    try:
        if os.path.exists(LOG_ROUTE_FILE):
            with open(LOG_ROUTE_FILE, 'r') as f:
                logs = json.load(f)
        else:
            logs = []
        logs.append(log_entry)
        with open(LOG_ROUTE_FILE, 'w') as f:
            json.dump(logs, f, indent=2)
    except Exception as e:
        print(f"Failed to log route request: {e}")

def log_grid_update(cell_key, old_quality, new_quality, confidence, reason):
    log_entry = {
        'timestamp': datetime.datetime.utcnow().isoformat(),
        'cell': cell_key,
        'old_quality': old_quality,
        'new_quality': new_quality,
        'confidence': confidence,
        'reason': reason
    }
    try:
        if os.path.exists(LOG_GRID_UPDATE_FILE):
            with open(LOG_GRID_UPDATE_FILE, 'r') as f:
                logs = json.load(f)
        else:
            logs = []
        logs.append(log_entry)
        with open(LOG_GRID_UPDATE_FILE, 'w') as f:
            json.dump(logs, f, indent=2)
    except Exception as e:
        print(f"Failed to log grid update: {e}")

def log_cross_agent_event(event):
    log_entry = {
        'timestamp': datetime.datetime.utcnow().isoformat(),
        **event
    }
    try:
        if os.path.exists(CROSS_AGENT_LOG_FILE):
            with open(CROSS_AGENT_LOG_FILE, 'r') as f:
                logs = json.load(f)
        else:
            logs = []
        logs.append(log_entry)
        with open(CROSS_AGENT_LOG_FILE, 'w') as f:
            json.dump(logs, f, indent=2)
    except Exception as e:
        print(f"Failed to log cross-agent event: {e}")

def log_feedback(feedback_entry):
    feedback_entry['timestamp'] = datetime.datetime.utcnow().isoformat()
    try:
        if os.path.exists(FEEDBACK_LOG_FILE):
            with open(FEEDBACK_LOG_FILE, 'r') as f:
                logs = json.load(f)
        else:
            logs = []
        logs.append(feedback_entry)
        with open(FEEDBACK_LOG_FILE, 'w') as f:
            json.dump(logs, f, indent=2)
    except Exception as e:
        print(f"Failed to log feedback: {e}")

# Reward calculation utilities (stubs for now)
def calculate_grid_agent_reward(route_success, prediction_accuracy):
    # Example: weighted sum of route success and prediction accuracy
    return 0.7 * route_success + 0.3 * prediction_accuracy

def calculate_routing_agent_reward(efficiency, user_satisfaction, road_quality):
    # Example: weighted sum of efficiency, satisfaction, and quality
    return 0.4 * efficiency + 0.4 * user_satisfaction + 0.2 * road_quality

# RL agent instance (singleton for now)
grid_update_agent = GridUpdateAgent()

def update_grid_cell_with_agent(cell_key):
    cell = grid.get(cell_key)
    if not cell:
        return {'success': False, 'message': 'Cell not found'}
    old_quality = cell['quality']
    old_confidence = cell['confidence']
    action, new_cell = grid_update_agent.act_on_cell(cell)
    # Simulate reward: +1 if confidence increases, -1 if decreases
    reward = 1 if new_cell['confidence'] > old_confidence else -1
    grid_update_agent.train_on_feedback(cell, action, reward, new_cell)
    grid[cell_key] = new_cell
    log_grid_update(cell_key, old_quality, new_cell['quality'], new_cell['confidence'], f'RL agent action: {action}')
    grid_update_agent.save_q_table()
    return {'success': True, 'cell_key': cell_key, 'old_quality': old_quality, 'new_quality': new_cell['quality'], 'action': action, 'reward': reward}

@app.route('/grid/update-agent', methods=['POST'])
def update_grid_agent_endpoint():
    data = request.get_json()
    cell_key = data.get('cell_key')
    if not cell_key:
        return jsonify({'success': False, 'message': 'Missing cell_key'}), 400
    result = update_grid_cell_with_agent(cell_key)
    return jsonify(result)

# RL routing agent instance
rl_routing_agent = RoutingAgent()

def find_rl_route(start_lat, start_lng, end_lat, end_lng):
    # Map coordinates to grid cells
    start_row = max(0, min(int((start_lat - delhi_bounds['lat_min']) / lat_step), grid_size - 1))
    start_col = max(0, min(int((start_lng - delhi_bounds['lng_min']) / lng_step), grid_size - 1))
    end_row = max(0, min(int((end_lat - delhi_bounds['lat_min']) / lat_step), grid_size - 1))
    end_col = max(0, min(int((end_lng - delhi_bounds['lng_min']) / lng_step), grid_size - 1))
    start_cell = grid[f'{start_row},{start_col}']
    end_cell = grid[f'{end_row},{end_col}']
    route = [start_cell]
    cell = start_cell
    steps = 0
    total_reward = 0
    max_steps = grid_size * 2
    while (cell['row'], cell['col']) != (end_cell['row'], end_cell['col']) and steps < max_steps:
        action, next_cell = rl_routing_agent.act(cell, end_cell, grid, grid_size)
        # Reward: -1 per step, +5 for good quality, -5 for very poor, +20 for reaching goal
        reward = -1
        if next_cell['quality'] == 'Good':
            reward += 5
        elif next_cell['quality'] == 'Very Poor':
            reward -= 5
        if (next_cell['row'], next_cell['col']) == (end_cell['row'], end_cell['col']):
            reward += 20
        rl_routing_agent.train_on_feedback(cell, end_cell, action, reward, next_cell, grid)
        route.append(next_cell)
        cell = next_cell
        steps += 1
        total_reward += reward
        if steps > grid_size * 2:
            break
    rl_routing_agent.save_q_table()
    # Convert route to coordinates
    route_coords = [[c['center_lat'], c['center_lng']] for c in route]
    return route_coords, total_reward, route

def analyze_route_quality(route_cells):
    # Returns True if route is poor (>=30% poor/very poor cells)
    poor_count = sum(1 for c in route_cells if c['quality'] in ['Poor', 'Very Poor'])
    if len(route_cells) == 0:
        return False
    return (poor_count / len(route_cells)) >= 0.3

def trigger_grid_agent_on_bad_route(route_cells):
    updated_cells = []
    for cell in route_cells:
        if cell['quality'] in ['Poor', 'Very Poor']:
            cell_key = f"{cell['row']},{cell['col']}"
            result = update_grid_cell_with_agent(cell_key)
            updated_cells.append({
                'cell_key': cell_key,
                'old_quality': result.get('old_quality'),
                'new_quality': result.get('new_quality'),
                'action': result.get('action'),
                'reward': result.get('reward')
            })
    return updated_cells

@app.route('/route/rl', methods=['POST'])
def rl_route_endpoint():
    try:
        data = request.get_json()
        start_lat = data.get('start_lat')
        start_lng = data.get('start_lng')
        end_lat = data.get('end_lat')
        end_lng = data.get('end_lng')
        if not all([start_lat, start_lng, end_lat, end_lng]):
            return jsonify({'success': False, 'message': 'Missing coordinates'}), 400
        # Map coordinates to grid cells
        start_row = max(0, min(int((start_lat - delhi_bounds['lat_min']) / lat_step), grid_size - 1))
        start_col = max(0, min(int((start_lng - delhi_bounds['lng_min']) / lng_step), grid_size - 1))
        end_row = max(0, min(int((end_lat - delhi_bounds['lat_min']) / lat_step), grid_size - 1))
        end_col = max(0, min(int((end_lng - delhi_bounds['lng_min']) / lng_step), grid_size - 1))
        start_cell = grid[f'{start_row},{start_col}']
        end_cell = grid[f'{end_row},{end_col}']
        # Check if a green path is feasible
        explanation = ""
        if not rl_routing_agent.is_green_path_feasible(start_cell, end_cell, grid, grid_size):
            explanation = "No feasible green route available. All possible paths pass through non-green zones."
            return jsonify({'success': False, 'message': explanation})
        # RL routing
        route = [start_cell]
        cell = start_cell
        steps = 0
        max_steps = grid_size * 2
        while (cell['row'], cell['col']) != (end_cell['row'], end_cell['col']) and steps < max_steps:
            action, next_cell = rl_routing_agent.act(cell, end_cell, grid, grid_size)
            route.append(next_cell)
            cell = next_cell
            steps += 1
            if steps > max_steps:
                break
        route_coords = [[c['center_lat'], c['center_lng']] for c in route]
        qualities = [c['quality'] for c in route]
        # Calculate green cell percentage and shaped reward
        green_pct = rl_routing_agent.calculate_green_percentage(route)
        reward, _ = rl_routing_agent.shaped_reward(route, end_cell, max_steps)
        for i in range(len(route)-1):
            rl_routing_agent.train_on_feedback(route[i], end_cell, 0, reward, route[i+1], grid)
        rl_routing_agent.save_q_table()
        log_route_request(start_lat, start_lng, end_lat, end_lng, route_coords, qualities, user_feedback=None, reward=reward)
        # Cross-agent coordination: If route is poor, trigger grid agent
        cross_agent_info = None
        if green_pct < 0.8:
            updated_cells = trigger_grid_agent_on_bad_route(route)
            cross_agent_info = {
                'event': 'bad_route_grid_update',
                'route_cells': [f"{c['row']},{c['col']}" for c in route],
                'updated_cells': updated_cells
            }
            log_cross_agent_event(cross_agent_info)
        if green_pct >= 0.8:
            explanation = "This route was chosen because it maximizes green (Good) zones while minimizing distance."
        else:
            explanation = "No fully green route was available, so the safest and shortest possible path was chosen."
        return jsonify({
            'success': True,
            'route_coordinates': route_coords,
            'qualities': qualities,
            'green_percentage': green_pct,
            'reward': reward,
            'steps': len(route),
            'cross_agent_info': cross_agent_info,
            'explanation': explanation
        })
    except Exception as e:
        print(f"Error in RL route endpoint: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/feedback', methods=['POST'])
def feedback_endpoint():
    try:
        data = request.get_json()
        route_coords = data.get('route_coordinates')
        feedback = data.get('feedback')  # 'positive' or 'negative'
        notes = data.get('notes', '')
        if not route_coords or feedback not in ['positive', 'negative']:
            return jsonify({'success': False, 'message': 'Missing or invalid feedback data'}), 400
        # Find grid cells for the route
        route_cells = []
        for lat, lng in route_coords:
            row = max(0, min(int((lat - delhi_bounds['lat_min']) / lat_step), grid_size - 1))
            col = max(0, min(int((lng - delhi_bounds['lng_min']) / lng_step), grid_size - 1))
            cell = grid.get(f'{row},{col}')
            if cell:
                route_cells.append(cell)
        # Log feedback
        log_feedback({'route_coordinates': route_coords, 'feedback': feedback, 'notes': notes})
        # Update agents based on feedback
        reward = 5 if feedback == 'positive' else -5
        for i in range(len(route_cells)-1):
            rl_routing_agent.train_on_feedback(route_cells[i], route_cells[-1], 0, reward, route_cells[i+1], grid)
        rl_routing_agent.save_q_table()
        if feedback == 'negative':
            updated_cells = trigger_grid_agent_on_bad_route(route_cells)
        else:
            updated_cells = []
        return jsonify({'success': True, 'message': 'Feedback received', 'updated_cells': updated_cells})
    except Exception as e:
        print(f"Error in feedback endpoint: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploaded_images')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
EVIDENCE_LOG_FILE = os.path.join(os.path.dirname(__file__), 'evidence_logs.json')

@app.route('/upload-image', methods=['POST'])
def upload_image():
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'message': 'No image file provided'}), 400
        image = request.files['image']
        cell = request.form.get('cell')  # e.g., '3,5'
        if not cell:
            return jsonify({'success': False, 'message': 'No cell location provided'}), 400
        filename = secure_filename(image.filename)
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        image.save(save_path)
        # Run model prediction
        pred_class, conf, all_probs = predict_image(save_path)
        evidence_entry = {
            'cell': cell.replace(' ', ''),
            'image_filename': filename,
            'prediction': pred_class,
            'confidence': conf,
            'timestamp': datetime.datetime.now(datetime.UTC).isoformat()
        }
        # Log evidence
        try:
            if os.path.exists(EVIDENCE_LOG_FILE):
                with open(EVIDENCE_LOG_FILE, 'r') as f:
                    logs = json.load(f)
            else:
                logs = []
            logs.append(evidence_entry)
            with open(EVIDENCE_LOG_FILE, 'w') as f:
                json.dump(logs, f, indent=2)
        except Exception as e:
            print(f"Failed to log evidence: {e}")
        # Aggregate evidence for this cell
        cell_key = cell.replace(' ', '')
        cell_evidence = [e for e in logs if e['cell'].replace(' ', '') == cell_key]
        # Use only the last 10 pieces of evidence
        recent_evidence = cell_evidence[-10:]
        predictions = [e['prediction'] for e in recent_evidence]
        confidences = [e['confidence'] for e in recent_evidence]
        most_common_pred, count = Counter(predictions).most_common(1)[0] if predictions else (None, 0)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        # Only update if at least 3 recent predictions agree and avg confidence > 0.7
        should_update = (count >= 3 and avg_conf > 0.7)
        if cell_key in grid:
            grid_cell = grid[cell_key]
            old_quality = grid_cell['quality']
            old_confidence = grid_cell['confidence']
            if should_update:
                grid_cell['quality'] = most_common_pred.capitalize() if most_common_pred else grid_cell['quality']
                grid_cell['confidence'] = avg_conf
                grid_cell['last_updated'] = evidence_entry['timestamp']
                grid_cell['num_images'] = len(cell_evidence)
                quality_colors = {'Good': '#22c55e', 'Satisfactory': '#f97316', 'Poor': '#ef4444', 'Very Poor': '#8b4513', 'Unknown': '#6b7280'}
                grid_cell['color'] = quality_colors.get(grid_cell['quality'], grid_cell['color'])
                print(f"Updated cell {cell_key}: {grid_cell}")
            # Trigger RL grid update agent for this cell, passing in evidence
            # (For now, just call as before; you can enhance agent to use evidence if desired)
            result = update_grid_cell_with_agent(cell_key)
            # Save updated grid to grid_colors.json
            try:
                with open(model_grid_path, 'w') as f:
                    json.dump({k: v for k, v in grid.items()}, f, indent=2)
            except Exception as e:
                print(f"Failed to save updated grid: {e}")
            return jsonify({
                'success': True,
                'prediction': pred_class,
                'confidence': conf,
                'cell': cell_key,
                'filename': filename,
                'updated_cell': grid_cell,
                'rl_result': result,
                'evidence_aggregation': {
                    'recent_predictions': predictions,
                    'recent_confidences': confidences,
                    'most_common_prediction': most_common_pred,
                    'count': count,
                    'avg_confidence': avg_conf,
                    'should_update': should_update
                }
            })
        else:
            return jsonify({'success': False, 'message': f'Cell {cell} not found in grid'}), 400
    except Exception as e:
        print(f"Error in upload_image endpoint: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/evidence/<cell>', methods=['GET'])
def get_cell_evidence(cell):
    try:
        cell_key = cell.replace(' ', '')
        if os.path.exists(EVIDENCE_LOG_FILE):
            with open(EVIDENCE_LOG_FILE, 'r') as f:
                logs = json.load(f)
        else:
            logs = []
        cell_evidence = [e for e in logs if e['cell'].replace(' ', '') == cell_key]
        return jsonify({'success': True, 'cell': cell, 'evidence': cell_evidence})
    except Exception as e:
        print(f"Error in get_cell_evidence endpoint: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/evidence/analytics', methods=['GET'])
def evidence_analytics():
    try:
        if os.path.exists(EVIDENCE_LOG_FILE):
            with open(EVIDENCE_LOG_FILE, 'r') as f:
                logs = json.load(f)
        else:
            logs = []
        # Aggregate by cell
        from collections import defaultdict, Counter
        cell_evidence = defaultdict(list)
        for e in logs:
            cell_evidence[e['cell']].append(e)
        analytics = {}
        for cell, evidences in cell_evidence.items():
            predictions = [e['prediction'] for e in evidences]
            confidences = [e['confidence'] for e in evidences]
            timestamps = [e['timestamp'] for e in evidences]
            if predictions:
                most_common_pred, count = Counter(predictions).most_common(1)[0]
                consensus = count / len(predictions)
            else:
                most_common_pred, consensus = None, 0.0
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            analytics[cell] = {
                'num_evidence': len(evidences),
                'avg_confidence': avg_conf,
                'most_common_prediction': most_common_pred,
                'consensus': consensus,
                'confidence_trend': confidences[-10:],
                'timestamps': timestamps[-10:],
                'low_confidence': avg_conf < 0.7,
                'high_disagreement': consensus < 0.6
            }
        # Find top N cells for various stats
        most_evidence = sorted(analytics.items(), key=lambda x: -x[1]['num_evidence'])[:10]
        least_evidence = sorted(analytics.items(), key=lambda x: x[1]['num_evidence'])[:10]
        low_conf_cells = [cell for cell, a in analytics.items() if a['low_confidence']]
        high_disagree_cells = [cell for cell, a in analytics.items() if a['high_disagreement']]
        return jsonify({
            'success': True,
            'analytics': analytics,
            'most_evidence': most_evidence,
            'least_evidence': least_evidence,
            'low_confidence_cells': low_conf_cells,
            'high_disagreement_cells': high_disagree_cells
        })
    except Exception as e:
        print(f"Error in evidence_analytics: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/feedback/analytics', methods=['GET'])
def feedback_analytics():
    try:
        if os.path.exists(FEEDBACK_LOG_FILE):
            with open(FEEDBACK_LOG_FILE, 'r') as f:
                logs = json.load(f)
        else:
            logs = []
        from collections import defaultdict, Counter
        cell_feedback = defaultdict(list)
        for fdbk in logs:
            route = fdbk.get('route_coordinates', [])
            for latlng in route:
                cell_feedback[str(latlng)].append(fdbk['feedback'])
        analytics = {}
        for cell, feedbacks in cell_feedback.items():
            pos = sum(1 for f in feedbacks if f == 'positive')
            neg = sum(1 for f in feedbacks if f == 'negative')
            total = len(feedbacks)
            analytics[cell] = {
                'positive': pos,
                'negative': neg,
                'total': total,
                'neg_ratio': (neg / total) if total else 0.0
            }
        most_negative = sorted(analytics.items(), key=lambda x: -x[1]['neg_ratio'])[:10]
        feedback_trend = Counter([f['feedback'] for f in logs])
        return jsonify({
            'success': True,
            'analytics': analytics,
            'most_negative_cells': most_negative,
            'feedback_trend': dict(feedback_trend)
        })
    except Exception as e:
        print(f"Error in feedback_analytics: {e}")
        return jsonify({'success': False, 'message': str(e)})

# Utility to convert backend cell key (e.g., '3,5') to UI format (e.g., 'E3')
def cell_key_to_ui(cell_key):
    try:
        row, col = map(int, cell_key.split(','))
        col_letter = string.ascii_uppercase[col - 1]  # A=0
        return f"{col_letter}{row}"
    except Exception:
        return cell_key

@app.route('/admin/analytics', methods=['GET'])
def admin_analytics():
    # --- Load evidence analytics ---
    evidence_analytics = {}
    try:
        with open('evidence_logs.json', 'r') as f:
            evidence_logs = json.load(f)
    except Exception:
        evidence_logs = []

    from collections import defaultdict, Counter
    cell_evidence = defaultdict(list)
    for e in evidence_logs:
        cell_evidence[e['cell']].append(e)
    analytics = {}
    for cell, evidences in cell_evidence.items():
        predictions = [e['prediction'] for e in evidences]
        confidences = [e['confidence'] for e in evidences]
        if predictions:
            most_common_pred, count = Counter(predictions).most_common(1)[0]
            consensus = count / len(predictions)
        else:
            most_common_pred, consensus = None, 0.0
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        analytics[cell] = {
            'num_evidence': len(evidences),
            'avg_confidence': avg_conf,
            'most_common_prediction': most_common_pred,
            'consensus': consensus,
            'low_confidence': avg_conf < 0.7,
            'high_disagreement': consensus < 0.6,
            'predictions': dict(Counter(predictions))
        }

    low_confidence_cells = [
        {
            'key': cell_key_to_ui(cell),
            'avgConfidence': cell_data['avg_confidence'],
            'prediction': cell_data['most_common_prediction'],
            'evidenceCount': cell_data['num_evidence']
        }
        for cell, cell_data in analytics.items() if cell_data['low_confidence']
    ]
    high_disagreement_cells = [
        {
            'key': cell_key_to_ui(cell),
            'consensus': cell_data['consensus'],
            'predictions': cell_data['predictions'],
            'evidenceCount': cell_data['num_evidence']
        }
        for cell, cell_data in analytics.items() if cell_data['high_disagreement']
    ]

    sorted_evidence = sorted(analytics.items(), key=lambda x: x[1]['num_evidence'], reverse=True)
    most_evidence = [
        {
            'key': cell_key_to_ui(cell),
            'evidenceCount': cell_data['num_evidence'],
            'avgConfidence': cell_data['avg_confidence']
        }
        for cell, cell_data in sorted_evidence[:10]
    ]
    least_evidence = [
        {
            'key': cell_key_to_ui(cell),
            'evidenceCount': cell_data['num_evidence'],
            'avgConfidence': cell_data['avg_confidence']
        }
        for cell, cell_data in sorted_evidence[-10:]
    ]

    try:
        with open('feedback_logs.json', 'r') as f:
            feedback_logs = json.load(f)
    except Exception:
        feedback_logs = []

    feedback_by_cell = defaultdict(list)
    for log in feedback_logs:
        if log.get('route_coordinates'):
            first = log['route_coordinates'][0]
            feedback_by_cell[str(first)].append(log)

    feedback_analytics = {}
    for cell, logs in feedback_by_cell.items():
        pos = sum(1 for l in logs if l['feedback'] == 'positive')
        neg = sum(1 for l in logs if l['feedback'] == 'negative')
        total = len(logs)
        feedback_analytics[cell] = {
            'neg_ratio': (neg / total) if total else 0.0,
            'negative': neg,
            'positive': pos,
            'total': total
        }

    negative_resistance_data = [
        {
            'key': cell,
            'negativeRatio': cell_data['neg_ratio'],
            'totalFeedback': cell_data['total'],
            'negativeFeedback': cell_data['negative']
        }
        for cell, cell_data in sorted(feedback_analytics.items(), key=lambda x: x[1]['neg_ratio'], reverse=True)[:10]
    ]

    from collections import Counter
    feedback_trend_counter = Counter()
    for log in feedback_logs:
        date = log['timestamp'][:10] if 'timestamp' in log else 'unknown'
        feedback_trend_counter[(date, log['feedback'])] += 1
    feedback_trend = []
    for date in sorted(set(date for date, _ in feedback_trend_counter)):
        feedback_trend.append({
            'date': date,
            'positive': feedback_trend_counter.get((date, 'positive'), 0),
            'negative': feedback_trend_counter.get((date, 'negative'), 0)
        })

    total_cells = len(analytics)
    high_conf_cells = sum(1 for c in analytics.values() if c['avg_confidence'] > 0.8)
    recent_evidence_cells = sum(1 for c in analytics.values() if c['num_evidence'] > 5)
    problematic_cells = len(low_confidence_cells) + len(high_disagreement_cells)
    avg_feedback_per_cell = (sum(c['total'] for c in feedback_analytics.values()) / total_cells) if total_cells else 0

    grid_health = {
        'highConfidencePercent': int((high_conf_cells / total_cells) * 100) if total_cells else 0,
        'recentEvidencePercent': int((recent_evidence_cells / total_cells) * 100) if total_cells else 0,
        'avgFeedbackPerCell': round(avg_feedback_per_cell, 1),
        'totalCells': total_cells,
        'problematicCells': problematic_cells
    }

    return jsonify({
        'lowConfidenceCells': low_confidence_cells,
        'highDisagreementCells': high_disagreement_cells,
        'evidenceCells': {
            'most': most_evidence,
            'least': least_evidence
        },
        'negativeResistanceData': negative_resistance_data,
        'confidenceTrend': [],
        'feedbackTrend': feedback_trend,
        'gridHealth': grid_health,
        'evidenceHistory': [],
        'feedbackHistory': []
    })

@app.route('/admin/cell/<cell_ui_key>', methods=['GET'])
def admin_cell_detail(cell_ui_key):
    import re
    match = re.match(r'([A-Z])(\d+)', cell_ui_key)
    if not match:
        return jsonify({'evidenceHistory': [], 'feedbackHistory': [], 'confidenceTrend': []})
    col_letter, row = match.groups()
    col = string.ascii_uppercase.index(col_letter) + 1
    backend_key = f'{int(row)},{col}'

    try:
        with open('evidence_logs.json', 'r') as f:
            evidence_logs = json.load(f)
    except Exception:
        evidence_logs = []
    evidence_history = [
        {
            'id': i,
            'timestamp': e['timestamp'],
            'prediction': e['prediction'],
            'confidence': e['confidence'],
            'thumbnail': f"/uploaded_images/{e['image_filename']}" if 'image_filename' in e else ''
        }
        for i, e in enumerate(evidence_logs) if e.get('cell') == backend_key
    ]

    try:
        with open('feedback_logs.json', 'r') as f:
            feedback_logs = json.load(f)
    except Exception:
        feedback_logs = []
    feedback_history = [
        {
            'id': i,
            'type': log['feedback'],
            'notes': log.get('notes', ''),
            'timestamp': log.get('timestamp', '')
        }
        for i, log in enumerate(feedback_logs)
        if any(isinstance(coord, list) and f'{coord[0]},{coord[1]}' == backend_key for coord in log.get('route_coordinates', []))
    ]

    confidences = [e['confidence'] for e in evidence_logs if e.get('cell') == backend_key]
    confidence_trend = [{'time': str(i), 'confidence': c} for i, c in enumerate(confidences)]

    return jsonify({
        'evidenceHistory': evidence_history,
        'feedbackHistory': feedback_history,
        'confidenceTrend': confidence_trend
    })

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8001))
    app.run(host='0.0.0.0', port=port, debug=False)

# For production deployment
if __name__ != "__main__":
    # Configure for gunicorn
    app.config['DEBUG'] = False