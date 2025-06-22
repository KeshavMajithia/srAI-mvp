import os
import random
import json
from collections import Counter, defaultdict
from PIL import Image
import torch
import torch.nn.functional as F
import torchvision.transforms as transforms
from torchvision import models

# Set random seed for reproducibility
random.seed(42)

# Grid size
GRID_ROWS = 20
GRID_COLS = 20
IMAGES_PER_CELL = 5

# Dataset paths
DATASET_DIR = os.path.join(os.path.dirname(__file__), 'dataset')
CATEGORY_MAP = {
    'good': 'good',
    'poor': 'poor',
    'satisfactory': 'satisfactory',
    'very_poor': 'very_poor',
}

# Class names and mapping (ensure order matches model)
CLASS_NAMES = ['good', 'poor', 'satisfactory', 'very_poor']

# Collect all image paths
def collect_image_paths(dataset_dir):
    image_paths = []
    for class_name in CLASS_NAMES:
        class_dir = os.path.join(dataset_dir, class_name)
        if not os.path.isdir(class_dir):
            continue
        for fname in os.listdir(class_dir):
            if fname.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                image_paths.append(os.path.join(class_dir, fname))
    return image_paths

all_image_paths = collect_image_paths(DATASET_DIR)
if len(all_image_paths) < GRID_ROWS * GRID_COLS * IMAGES_PER_CELL:
    print("Warning: Not enough images to guarantee unique images per cell. Sampling with replacement.")

# For each cell, randomly assign 5 images (with replacement, fully mixed from all classes)
def sample_images_for_grid():
    # Sample with replacement from the entire mixed pool
    return random.choices(all_image_paths, k=IMAGES_PER_CELL)

# Device
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# Load model
model_path = os.path.join(os.path.dirname(__file__), 'resnet50_road_health_model.pth')
from collections import OrderedDict
checkpoint = torch.load(model_path, map_location=device)
class_names = checkpoint.get('class_names', ['good', 'poor', 'satisfactory', 'very_poor'])
model = models.resnet50(pretrained=False)
num_ftrs = model.fc.in_features
model.fc = torch.nn.Sequential(
    torch.nn.Dropout(0.5),
    torch.nn.Linear(num_ftrs, 512),
    torch.nn.ReLU(),
    torch.nn.Dropout(0.3),
    torch.nn.Linear(512, len(class_names))
)
model.load_state_dict(checkpoint['model_state_dict'])
model.eval()
model.to(device)
CLASS_NAMES = class_names

# Preprocessing (same as training)
transform = transforms.Compose([
    transforms.Resize((256, 256)),
    transforms.ToTensor(),
])

def predict_image(img_path):
    img = Image.open(img_path).convert('RGB')
    img_tensor = transform(img).unsqueeze(0).to(device)
    with torch.no_grad():
        output = model(img_tensor)
        probabilities = F.softmax(output, dim=1)
        confidence, pred = torch.max(probabilities, 1)
        return CLASS_NAMES[pred.item()], confidence.item(), probabilities.cpu().numpy().tolist()[0]

# Main grid assignment and prediction
results = {}
detailed_results = defaultdict(list)
print(f"Starting grid prediction for {GRID_ROWS}x{GRID_COLS} grid, {IMAGES_PER_CELL} images per cell...")
for row in range(GRID_ROWS):
    for col in range(GRID_COLS):
        cell_key = (row, col)
        # Assign 5 random images to this cell (from the full mixed pool)
        images = sample_images_for_grid()
        preds = []
        confidences = []
        for img_path in images:
            pred_class, conf, all_probs = predict_image(img_path)
            preds.append(pred_class)
            confidences.append({'class': pred_class, 'confidence': conf, 'all_probabilities': all_probs, 'image': os.path.basename(img_path)})
        # Take the most repeated value (majority vote) as the output
        most_common = Counter(preds).most_common(1)[0][0]
        results[cell_key] = most_common
        detailed_results[cell_key] = confidences
        print(f"Cell ({row},{col}): {most_common} (votes: {Counter(preds)})")
print("Grid prediction complete. Saving results...")

# Save as JSON
with open(os.path.join(os.path.dirname(__file__), 'grid_colors.json'), 'w') as f:
    json.dump({str(k): v for k, v in results.items()}, f, indent=2)

# Optionally, save detailed results
with open(os.path.join(os.path.dirname(__file__), 'grid_colors_detailed.json'), 'w') as f:
    json.dump({str(k): v for k, v in detailed_results.items()}, f, indent=2)

# Also keep as Python dict for direct use
grid_colors = results

def get_color_map():
    return {
        'good': 'green',
        'satisfactory': 'orange',
        'poor': 'red',
        'very_poor': 'brown',
    }

if __name__ == "__main__":
    print("Sample output for (0,0):", grid_colors[(0,0)])
    print("Color map:", get_color_map())
    print("Results saved to grid_colors.json and grid_colors_detailed.json.") 