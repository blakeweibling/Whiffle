# YOLO Model Training Guide

This guide explains how to update your YOLO model to detect a new type of ball on a different playfield.

## Overview

Your current model (`data/whiffle_new_best.pt`) detects 3 ball types:
- `white`: White balls
- `red`: Red balls  
- `half`: Half red/half white balls

To add a new ball type or adapt to a new playfield, you'll need to:
1. Prepare a labeled dataset
2. Train a new YOLO model
3. Update the code to use the new model

## Step 1: Prepare Your Dataset

### Dataset Structure

Create a dataset directory with the following structure:

```
your_dataset/
├── images/
│   ├── train/          # Training images (70-80% of data)
│   ├── val/            # Validation images (10-15% of data)
│   └── test/           # Test images (10-15% of data, optional)
└── labels/
    ├── train/          # Training labels (YOLO format)
    ├── val/            # Validation labels (YOLO format)
    └── test/           # Test labels (YOLO format, optional)
```

### Image Collection Tips

1. **Capture diverse scenarios:**
   - Different lighting conditions
   - Various ball positions on the playfield
   - Multiple balls in frame
   - Different angles and distances
   - Motion blur (if balls are moving)

2. **Recommended dataset size:**
   - Minimum: 100-200 images per class
   - Good: 500-1000 images per class
   - Excellent: 1000+ images per class

3. **For a new playfield:**
   - Capture images from the actual playfield you'll be using
   - Include background variations
   - Capture edge cases (balls near boundaries, overlapping, etc.)

### Labeling Images

You need to label each image with bounding boxes in YOLO format.

#### Option 1: Use LabelImg (Recommended)

1. Install LabelImg:
   ```bash
   pip install labelimg
   ```

2. Open LabelImg:
   ```bash
   labelimg
   ```

3. Configure:
   - Open the directory containing your images
   - Set "Save Dir" to the corresponding labels folder
   - Choose "YOLO" format (not PascalVOC)
   - Create classes: `white`, `red`, `half`, and your new ball type (e.g., `blue`, `yellow`, etc.)

4. Label each image:
   - Draw bounding boxes around each ball
   - Assign the correct class
   - Save (creates a `.txt` file with the same name as the image)

#### Option 2: Use Roboflow

1. Go to [roboflow.com](https://roboflow.com)
2. Create a new project
3. Upload images
4. Label online (free tier available)
5. Export in YOLO format

#### YOLO Label Format

Each image should have a corresponding `.txt` file with the same name.

Format: `class_id center_x center_y width height`

All values are normalized (0-1):
- `class_id`: Integer (0=white, 1=red, 2=half, 3=your_new_type, etc.)
- `center_x`: X coordinate of box center / image width
- `center_y`: Y coordinate of box center / image height
- `width`: Box width / image width
- `height`: Box height / image height

Example (`image001.txt`):
```
0 0.5 0.3 0.1 0.1
1 0.7 0.6 0.08 0.08
2 0.2 0.8 0.12 0.12
```

## Step 2: Train the Model

### Quick Start

1. **Prepare your dataset** following the structure above

2. **Run the training script:**
   ```bash
   python train_yolo_model.py --data path/to/your_dataset --classes white red half blue --epochs 100
   ```

   Replace:
   - `path/to/your_dataset` with your dataset path
   - `white red half blue` with your actual class names (add your new ball type)
   - `--epochs 100` with desired number of epochs

### Training Options

#### Fine-tune Existing Model (Recommended for New Playfield)

If you want to adapt the existing model to a new playfield while keeping the same ball types:

```bash
python train_yolo_model.py \
    --data path/to/your_dataset \
    --model data/whiffle_new_best.pt \
    --classes white red half \
    --epochs 50 \
    --name new_playfield
```

#### Train New Model with New Ball Type

To add a completely new ball type (e.g., "blue"):

```bash
python train_yolo_model.py \
    --data path/to/your_dataset \
    --classes white red half blue \
    --epochs 100 \
    --name new_ball_type
```

#### Advanced Training Options

```bash
python train_yolo_model.py \
    --data path/to/your_dataset \
    --classes white red half blue \
    --model yolov8n.pt \
    --epochs 200 \
    --imgsz 640 \
    --batch 32 \
    --device 0 \
    --name my_experiment
```

Parameters:
- `--model`: Pretrained model (use `yolov8n.pt` for nano, `yolov8s.pt` for small, etc.)
- `--epochs`: Number of training iterations
- `--imgsz`: Image size (640 is standard, can use 416, 512, 640, 1280)
- `--batch`: Batch size (adjust based on GPU memory)
- `--device`: GPU ID (`0` for first GPU, `cpu` for CPU)
- `--name`: Experiment name (saved in `runs/detect/`)

### Training Output

After training, you'll find:
- `runs/detect/your_experiment_name/weights/best.pt` - Best model (use this!)
- `runs/detect/your_experiment_name/weights/last.pt` - Last checkpoint
- Training plots and metrics in the same directory

### Validate Model

To test your trained model:

```bash
python train_yolo_model.py \
    --data path/to/your_dataset \
    --val-only runs/detect/your_experiment_name/weights/best.pt
```

## Step 3: Update Your Code

After training, update your code to use the new model:

### 1. Update `detection.py`

Replace the model path and update class names:

```python
# In BallDetector.__init__()
self.model = YOLO("runs/detect/your_experiment_name/weights/best.pt")  # Update path
self.class_names = ["white", "red", "half", "blue"]  # Add your new class
```

### 2. Update `detect_all_balls()` Method

Add handling for your new ball type:

```python
def detect_all_balls(self, ...):
    # ... existing code ...
    
    white_balls = []
    red_balls = []
    half_balls = []
    blue_balls = []  # Add new list
    
    # ... detection code ...
    
    # Add handling for new ball type
    elif ball_type == "blue":
        blue_balls.append((int(x_center), int(y_center), radius))
    
    # Update return statement
    return white_balls, red_balls, half_balls, blue_balls
```

### 3. Update Code That Uses Ball Detection

You'll need to update:
- `tracking.py`: Update `update_tracking()` to handle the new ball type
- `scoring.py`: Add scoring logic for the new ball type if needed
- `stats_calculator.py`: Update statistics tracking

### 4. Copy Model to Data Directory

Once you're satisfied with the model:

```bash
cp runs/detect/your_experiment_name/weights/best.pt data/whiffle_new_best.pt
```

Or update the path in `detection.py` to point directly to the trained model.

## Tips for Better Results

1. **Data Quality > Quantity**: 200 well-labeled images beat 1000 poorly labeled ones
2. **Balanced Dataset**: Try to have similar numbers of examples for each class
3. **Augmentation**: The training script includes augmentation, but you can adjust it
4. **Start Small**: Begin with a smaller model (`yolov8n.pt`) for faster iteration
5. **Monitor Training**: Watch the validation metrics to avoid overfitting
6. **Test on Real Data**: Always test on actual gameplay footage, not just validation set

## Troubleshooting

### Low Detection Accuracy
- Collect more diverse training data
- Check label quality
- Increase training epochs
- Try a larger model (`yolov8s.pt` or `yolov8m.pt`)

### Model Not Detecting New Ball Type
- Ensure you included the new class in `--classes` argument
- Verify labels are correct (class ID matches position in class list)
- Check that you have enough examples of the new ball type

### Out of Memory Errors
- Reduce `--batch` size
- Reduce `--imgsz` (try 416 or 512)
- Use a smaller model (`yolov8n.pt`)

## Example: Adding a Blue Ball Type

1. **Collect 200+ images** with blue balls on your playfield
2. **Label them** using LabelImg (class: `blue`, class_id: 3)
3. **Train:**
   ```bash
   python train_yolo_model.py --data my_dataset --classes white red half blue --epochs 100
   ```
4. **Update `detection.py`:**
   - Change model path to `runs/detect/ball_detection/weights/best.pt`
   - Update `self.class_names = ["white", "red", "half", "blue"]`
   - Add `blue_balls` list and handling in `detect_all_balls()`
5. **Test and iterate!**

## Resources

- [Ultralytics YOLOv8 Docs](https://docs.ultralytics.com/)
- [LabelImg GitHub](https://github.com/HumanSignal/labelImg)
- [Roboflow](https://roboflow.com) - Online labeling tool

