# YOLO Model Training Guide

This guide explains how to train and update your YOLO model for the Five Star playfield with silver and gold balls.

## Overview

Your current model (`data/whiffle_new_best_fivestar.pt`) detects 2 ball types:
- `silver`: Silver balls
- `gold`: Gold balls

To train or retrain the model for your playfield, you'll need to:
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

3. **For the Five Star playfield:**
   - Capture images from the actual playfield you'll be using
   - Include background variations
   - Capture edge cases (balls near boundaries, overlapping, etc.)

### Labeling Images

You need to label each image with bounding boxes in YOLO format.

#### Using CVAT.ai (Recommended)

CVAT.ai is a powerful web-based annotation tool that supports YOLO format export.

1. **Access CVAT.ai:**
   - Go to [cvat.ai](https://cvat.ai) or set up your own instance
   - Create an account or log in

2. **Create a New Project:**
   - Click "Create new project"
   - Name your project (e.g., "Five Star Balls")
   - Add labels: `silver` and `gold`
   - Save the project

3. **Create a New Task:**
   - Click "Create new task"
   - Name your task (e.g., "Training Set")
   - Upload your images (you can upload multiple images at once)
   - Select the project you created
   - Click "Submit"

4. **Label Images:**
   - Open the task and click "Job #X" to start labeling
   - Use the rectangle tool to draw bounding boxes around each ball
   - Assign the correct label (silver or gold) to each bounding box
   - Use keyboard shortcuts for faster labeling:
     - `N` - Next image
     - `P` - Previous image
     - `R` - Rectangle tool
   - Save your progress regularly

5. **Export Labels:**
   - Go to the task page
   - Click "Actions" → "Export dataset"
   - Choose "YOLO 1.1" format
   - Download the exported dataset
   - The exported folder will contain:
     - `obj_train_data/` - Your images
     - `obj_train_data/` - Your labels in YOLO format (`.txt` files)
   - Organize these into the train/val/test structure as needed

#### YOLO Label Format

Each image should have a corresponding `.txt` file with the same name.

Format: `class_id center_x center_y width height`

All values are normalized (0-1):
- `class_id`: Integer (0=silver, 1=gold)
- `center_x`: X coordinate of box center / image width
- `center_y`: Y coordinate of box center / image height
- `width`: Box width / image width
- `height`: Box height / image height

Example (`image001.txt`):
```
0 0.5 0.3 0.1 0.1
1 0.7 0.6 0.08 0.08
0 0.2 0.8 0.12 0.12
```

## Step 2: Train the Model

### Quick Start

1. **Prepare your dataset** following the structure above

2. **Run the training script:**
   ```bash
   python train_yolo_model.py --data path/to/your_dataset --classes silver gold --epochs 100
   ```

   Replace:
   - `path/to/your_dataset` with your dataset path
   - `--epochs 100` with desired number of epochs

### Training Options

#### Fine-tune Existing Model (Recommended for New Playfield)

If you want to adapt the existing model to a new playfield while keeping the same ball types:

```bash
python train_yolo_model.py \
    --data path/to/your_dataset \
    --model data/whiffle_new_best_fivestar.pt \
    --classes silver gold \
    --epochs 50 \
    --name new_playfield
```

#### Train New Model from Scratch

To train a completely new model:

```bash
python train_yolo_model.py \
    --data path/to/your_dataset \
    --classes silver gold \
    --epochs 100 \
    --name fivestar_training
```

#### Advanced Training Options

```bash
python train_yolo_model.py \
    --data path/to/your_dataset \
    --classes silver gold \
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

Replace the model path:

```python
# In BallDetector.__init__()
self.model = YOLO("runs/detect/your_experiment_name/weights/best.pt")  # Update path
self.class_names = ["silver", "gold"]
```

### 2. Copy Model to Data Directory

Once you're satisfied with the model:

```bash
cp runs/detect/your_experiment_name/weights/best.pt data/whiffle_new_best_fivestar.pt
```

Or update the path in `detection.py` to point directly to the trained model.

## Tips for Better Results

1. **Data Quality > Quantity**: 200 well-labeled images beat 1000 poorly labeled ones
2. **Balanced Dataset**: Try to have similar numbers of examples for each class (silver and gold)
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

### Model Not Detecting Ball Types Correctly
- Ensure you included both classes in `--classes` argument: `silver gold`
- Verify labels are correct (class ID 0=silver, 1=gold)
- Check that you have enough examples of each ball type
- Ensure class IDs in labels match the order in the class list

### Out of Memory Errors
- Reduce `--batch` size
- Reduce `--imgsz` (try 416 or 512)
- Use a smaller model (`yolov8n.pt`)

## Example: Training for Five Star Playfield

1. **Collect 200+ images** with silver and gold balls on your Five Star playfield
2. **Label them** using CVAT.ai:
   - Create a project with labels: `silver` and `gold`
   - Upload images and create bounding boxes
   - Export in YOLO 1.1 format
   - Class IDs will be: 0=silver, 1=gold (based on label order in CVAT)
3. **Train:**
   ```bash
   python train_yolo_model.py --data my_fivestar_dataset --classes silver gold --epochs 100 --name fivestar_model
   ```
4. **Update `detection.py`:**
   - Change model path to `data/whiffle_new_best_fivestar.pt` or point to `runs/detect/fivestar_model/weights/best.pt`
   - Ensure `self.class_names = ["silver", "gold"]`
5. **Test and iterate!**

## Resources

- [Ultralytics YOLOv8 Docs](https://docs.ultralytics.com/)
- [CVAT.ai](https://cvat.ai) - Web-based annotation tool
- [CVAT Documentation](https://docs.cvat.ai/) - Complete CVAT user guide
