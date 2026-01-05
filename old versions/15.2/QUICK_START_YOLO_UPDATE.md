# Quick Start: Updating YOLO Model for New Ball Type

This is a condensed guide. For detailed instructions, see `YOLO_TRAINING_GUIDE.md` and `EXAMPLE_ADDING_NEW_BALL_TYPE.md`.

## Overview

Your current model detects: `white`, `red`, `half` balls
You want to add: A new ball type (e.g., `blue`) on a different playfield

## Three Main Steps

### 1. Prepare Dataset & Train Model

```bash
# Install labeling tool (optional but recommended)
pip install labelimg

# Label your images using LabelImg or Roboflow
# Create dataset structure:
#   dataset/
#   ├── images/train/, images/val/
#   └── labels/train/, labels/val/

# Train the model
python train_yolo_model.py \
    --data path/to/your_dataset \
    --classes white red half blue \
    --epochs 100 \
    --name new_ball_type

# Your trained model will be at:
# runs/detect/new_ball_type/weights/best.pt
```

### 2. Update Code Files

**Files to modify:**
- `detection.py` - Add new ball type handling
- `tracking.py` - Add new ball type to tracking
- `game_loop.py` - Update function calls

**See `EXAMPLE_ADDING_NEW_BALL_TYPE.md` for exact code changes.**

### 3. Test & Deploy

```bash
# Copy your trained model to data directory
cp runs/detect/new_ball_type/weights/best.pt data/whiffle_new_best.pt

# Or update the path in detection.py to point to your model
```

## Key Points

1. **Dataset Quality**: 200+ well-labeled images per class is a good start
2. **Class Order Matters**: The order in `--classes` must match your label class IDs
3. **Fine-tuning**: Use `--model data/whiffle_new_best.pt` to fine-tune existing model
4. **Testing**: Always test on real gameplay footage, not just validation set

## Common Issues

- **Model not detecting new type**: Check class order matches labels
- **Low accuracy**: Need more diverse training data
- **Out of memory**: Reduce `--batch` size or `--imgsz`

## Need Help?

- Full training guide: `YOLO_TRAINING_GUIDE.md`
- Code change examples: `EXAMPLE_ADDING_NEW_BALL_TYPE.md`
- Training script: `train_yolo_model.py`

