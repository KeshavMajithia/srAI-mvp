import random
import json
import os
import numpy as np
from collections import defaultdict, deque

# Possible qualities and actions
QUALITIES = ['Good', 'Satisfactory', 'Poor', 'Very Poor']

# Q-learning parameters
ALPHA = 0.1  # learning rate
GAMMA = 0.9  # discount factor
EPSILON = 0.2  # exploration rate

class RoutingAgent:
    def __init__(self, q_table_path='routing_q_table.json'):
        self.q_table_path = q_table_path
        self.q_table = defaultdict(lambda: np.zeros(4))  # 4 directions: up, down, left, right
        self.load_q_table()

    def state_to_key(self, cell, end_cell, grid):
        # Discretize state: current cell, end cell, quality, confidence
        quality = cell['quality']
        conf = int(cell['confidence'] * 10)
        return f"{cell['row']},{cell['col']}|{end_cell['row']},{end_cell['col']}|{quality}|{conf}"

    def choose_action(self, state_key, cell, grid, grid_size, end_cell):
        # Prefer actions that move toward 'Good' cells, but balance with Q-values
        if random.random() < EPSILON:
            return random.choice(range(4))
        # Bias toward greener cells
        q_values = self.q_table[state_key].copy()
        for i, (dr, dc) in enumerate([(-1,0),(1,0),(0,-1),(0,1)]):
            nr, nc = cell['row']+dr, cell['col']+dc
            if 0 <= nr < grid_size and 0 <= nc < grid_size:
                neighbor = grid.get(f"{nr},{nc}")
                if neighbor and neighbor['quality'] == 'Good':
                    q_values[i] += 2  # bias toward green
        return int(np.argmax(q_values))

    def update_q(self, state_key, action, reward, next_state_key):
        best_next = np.max(self.q_table[next_state_key])
        self.q_table[state_key][action] += ALPHA * (reward + GAMMA * best_next - self.q_table[state_key][action])

    def save_q_table(self):
        with open(self.q_table_path, 'w') as f:
            json.dump({k: v.tolist() for k, v in self.q_table.items()}, f, indent=2)

    def load_q_table(self):
        if os.path.exists(self.q_table_path):
            with open(self.q_table_path, 'r') as f:
                data = json.load(f)
                for k, v in data.items():
                    self.q_table[k] = np.array(v)

    def get_next_cell(self, cell, action, grid_size):
        # 0: up, 1: down, 2: left, 3: right
        row, col = cell['row'], cell['col']
        if action == 0 and row > 0:
            return row - 1, col
        elif action == 1 and row < grid_size - 1:
            return row + 1, col
        elif action == 2 and col > 0:
            return row, col - 1
        elif action == 3 and col < grid_size - 1:
            return row, col + 1
        return row, col  # stay if invalid

    def act(self, cell, end_cell, grid, grid_size):
        state_key = self.state_to_key(cell, end_cell, grid)
        action = self.choose_action(state_key, cell, grid, grid_size, end_cell)
        next_row, next_col = self.get_next_cell(cell, action, grid_size)
        next_cell = grid.get(f"{next_row},{next_col}", cell)
        return action, next_cell

    def train_on_feedback(self, cell, end_cell, action, reward, next_cell, grid):
        state_key = self.state_to_key(cell, end_cell, grid)
        next_state_key = self.state_to_key(next_cell, end_cell, grid)
        self.update_q(state_key, action, reward, next_state_key)

    def calculate_green_percentage(self, route_cells):
        if not route_cells:
            return 0.0
        green_count = sum(1 for c in route_cells if c['quality'] == 'Good')
        return green_count / len(route_cells)

    def is_green_path_feasible(self, start_cell, end_cell, grid, grid_size):
        # BFS to check if any path exists with at least one green cell
        visited = set()
        queue = deque([(start_cell['row'], start_cell['col'], False)])
        while queue:
            row, col, seen_green = queue.popleft()
            if (row, col) == (end_cell['row'], end_cell['col']) and seen_green:
                return True
            for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                nr, nc = row+dr, col+dc
                if 0 <= nr < grid_size and 0 <= nc < grid_size and (nr, nc) not in visited:
                    neighbor = grid.get(f"{nr},{nc}")
                    if neighbor:
                        queue.append((nr, nc, seen_green or neighbor['quality'] == 'Good'))
                        visited.add((nr, nc))
        return False

    def shaped_reward(self, route_cells, end_cell, max_steps):
        # Balanced reward for green, short, successful routes
        if not route_cells:
            return 0, 0.0
        green_pct = self.calculate_green_percentage(route_cells)
        reached_goal = (route_cells[-1]['row'], route_cells[-1]['col']) == (end_cell['row'], end_cell['col'])
        reward = 0
        for cell in route_cells:
            if cell['quality'] == 'Good':
                reward += 1
            elif cell['quality'] == 'Satisfactory':
                reward += 0.2
            elif cell['quality'] == 'Poor':
                reward -= 0.5
            elif cell['quality'] == 'Very Poor':
                reward -= 1
            reward -= 0.5  # step penalty
        if reached_goal:
            reward += 10
            if green_pct >= 0.8:
                reward += 5
        else:
            reward -= 5
        return reward, green_pct

# Example simulation loop
if __name__ == "__main__":
    # Load a sample grid (simulate)
    grid_path = os.path.join(os.path.dirname(__file__), 'grid_colors.json')
    with open(grid_path, 'r') as f:
        grid_data = json.load(f)
    # Convert to dict with string keys
    grid = {k.replace('(', '').replace(')', '').replace(' ', ''): v for k, v in grid_data.items()}
    grid_size = 20
    agent = RoutingAgent()
    start = grid['0,0']
    end = grid['19,19']
    if not agent.is_green_path_feasible(start, end, grid, grid_size):
        print("No feasible green path available.")
    else:
        for episode in range(50):
            cell = start
            steps = 0
            route_cells = [cell]
            max_steps = grid_size * 2
            while (cell['row'], cell['col']) != (end['row'], end['col']) and steps < max_steps:
                action, next_cell = agent.act(cell, end, grid, grid_size)
                route_cells.append(next_cell)
                cell = next_cell
                steps += 1
            reward, green_pct = agent.shaped_reward(route_cells, end, max_steps)
            for i in range(len(route_cells)-1):
                agent.train_on_feedback(route_cells[i], end, 0, reward, route_cells[i+1], grid)
            print(f"Episode {episode}: steps={steps}, green_pct={green_pct:.2f}, reward={reward}")
        agent.save_q_table()
        print("Routing agent training complete. Q-table saved.") 