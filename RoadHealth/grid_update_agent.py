import random
import json
import os
import numpy as np
from collections import defaultdict

# Possible qualities and actions
QUALITIES = ['Good', 'Satisfactory', 'Poor', 'Very Poor']
ACTIONS = ['upgrade', 'downgrade', 'maintain']

# Q-learning parameters
ALPHA = 0.1  # learning rate
GAMMA = 0.9  # discount factor
EPSILON = 0.2  # exploration rate

class GridUpdateAgent:
    def __init__(self, q_table_path='grid_update_q_table.json'):
        self.q_table_path = q_table_path
        self.q_table = defaultdict(lambda: np.zeros(len(ACTIONS)))
        self.load_q_table()

    def state_to_key(self, cell):
        # Discretize state for Q-table
        quality = cell['quality']
        conf = int(cell['confidence'] * 10)  # bucketed
        num_images = min(cell['num_images'], 10)
        return f"{quality}|{conf}|{num_images}"

    def choose_action(self, state_key):
        if random.random() < EPSILON:
            return random.choice(range(len(ACTIONS)))
        return int(np.argmax(self.q_table[state_key]))

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

    def act_on_cell(self, cell):
        state_key = self.state_to_key(cell)
        action_idx = self.choose_action(state_key)
        action = ACTIONS[action_idx]
        # Simulate effect of action
        new_cell = cell.copy()
        if action == 'upgrade':
            if new_cell['quality'] != QUALITIES[0]:
                new_cell['quality'] = QUALITIES[max(0, QUALITIES.index(new_cell['quality']) - 1)]
                new_cell['confidence'] = min(1.0, new_cell['confidence'] + 0.1)
        elif action == 'downgrade':
            if new_cell['quality'] != QUALITIES[-1]:
                new_cell['quality'] = QUALITIES[min(len(QUALITIES)-1, QUALITIES.index(new_cell['quality']) + 1)]
                new_cell['confidence'] = max(0.0, new_cell['confidence'] - 0.1)
        # maintain: do nothing
        return action, new_cell

    def train_on_feedback(self, cell, action, reward, next_cell):
        state_key = self.state_to_key(cell)
        next_state_key = self.state_to_key(next_cell)
        action_idx = ACTIONS.index(action)
        self.update_q(state_key, action_idx, reward, next_state_key)

# Example simulation loop
if __name__ == "__main__":
    # Load a sample grid (simulate)
    grid_path = os.path.join(os.path.dirname(__file__), 'grid_colors.json')
    with open(grid_path, 'r') as f:
        grid = json.load(f)
    agent = GridUpdateAgent()
    for step in range(100):
        # Pick a random cell
        cell_key = random.choice(list(grid.keys()))
        cell = grid[cell_key]
        # Simulate agent action
        action, new_cell = agent.act_on_cell(cell)
        # Simulate reward: +1 if confidence increases, -1 if decreases
        reward = 1 if new_cell['confidence'] > cell['confidence'] else -1
        agent.train_on_feedback(cell, action, reward, new_cell)
        # Optionally update grid
        grid[cell_key] = new_cell
        print(f"Step {step}: {cell_key} {cell['quality']}->{new_cell['quality']} action={action} reward={reward}")
    agent.save_q_table()
    print("Training complete. Q-table saved.") 