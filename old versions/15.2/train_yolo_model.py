# train_yolo_model.py
"""
Training script for YOLOv8 model to detect balls on a playfield.

This script trains a YOLOv8 model to detect different types of balls.
You can use it to:
1. Train a new model from scratch
2. Fine-tune an existing model for a new playfield/ball type

Usage:
    python train_yolo_model.py --data path/to/dataset --epochs 100 --imgsz 640

Dataset Structure:
    dataset/
    ├── images/
    │   ├── train/
    │   ├── val/
    │   └── test/ (optional)
    └── labels/
        ├── train/
        ├── val/
        └── test/ (optional)

Label Format (YOLO format):
    class_id center_x center_y width height
    (all values normalized 0-1)
"""

import argparse
import os
from pathlib import Path
from ultralytics import YOLO


def create_dataset_yaml(dataset_path: str, classes: list, output_path: str = "dataset.yaml"):
    """
    Create a YOLO dataset configuration file.
    
    Args:
        dataset_path: Path to the dataset root directory
        classes: List of class names
        output_path: Path to save the YAML file
    """
    dataset_path = Path(dataset_path).absolute()
    
    yaml_content = f"""# YOLO Dataset Configuration
# Path to dataset
path: {dataset_path}
train: images/train
val: images/val
test: images/test  # optional

# Classes
names:
"""
    for idx, class_name in enumerate(classes):
        yaml_content += f"  {idx}: {class_name}\n"
    
    with open(output_path, 'w') as f:
        f.write(yaml_content)
    
    print(f"Created dataset configuration: {output_path}")
    return output_path


def train_model(
    model_path: str = None,
    data_yaml: str = "dataset.yaml",
    epochs: int = 100,
    imgsz: int = 640,
    batch: int = 16,
    device: str = None,
    project: str = "runs/detect",
    name: str = "ball_detection",
    patience: int = 50,
    save_period: int = 10,
):
    """
    Train a YOLOv8 model.
    
    Args:
        model_path: Path to pretrained model (e.g., 'yolov8n.pt') or None to use default
        data_yaml: Path to dataset YAML configuration
        epochs: Number of training epochs
        imgsz: Image size for training
        batch: Batch size
        device: Device to use ('cpu', '0', '0,1', etc.) or None for auto
        project: Project directory name
        name: Experiment name
        patience: Early stopping patience
        save_period: Save checkpoint every N epochs
    """
    # Load model
    if model_path and os.path.exists(model_path):
        print(f"Loading pretrained model: {model_path}")
        model = YOLO(model_path)
    else:
        print("Loading YOLOv8n (nano) model from scratch")
        model = YOLO('yolov8n.pt')  # You can use 'yolov8s.pt', 'yolov8m.pt', etc.
    
    # Train the model
    results = model.train(
        data=data_yaml,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        project=project,
        name=name,
        patience=patience,
        save_period=save_period,
        # Additional training parameters
        optimizer='AdamW',  # or 'SGD'
        lr0=0.01,  # Initial learning rate
        lrf=0.01,  # Final learning rate (lr0 * lrf)
        momentum=0.937,
        weight_decay=0.0005,
        warmup_epochs=3.0,
        warmup_momentum=0.8,
        warmup_bias_lr=0.1,
        box=7.5,  # Box loss gain
        cls=0.5,  # Class loss gain
        dfl=1.5,  # DFL loss gain
        # Augmentation
        hsv_h=0.015,  # Image HSV-Hue augmentation
        hsv_s=0.7,  # Image HSV-Saturation augmentation
        hsv_v=0.4,  # Image HSV-Value augmentation
        degrees=0.0,  # Image rotation (+/- deg)
        translate=0.1,  # Image translation (+/- fraction)
        scale=0.5,  # Image scale (+/- gain)
        shear=0.0,  # Image shear (+/- deg)
        perspective=0.0,  # Image perspective (+/- fraction)
        flipud=0.0,  # Image flip up-down (probability)
        fliplr=0.5,  # Image flip left-right (probability)
        mosaic=1.0,  # Image mosaic (probability)
        mixup=0.0,  # Image mixup (probability)
        copy_paste=0.0,  # Segment copy-paste (probability)
    )
    
    print(f"\nTraining completed!")
    print(f"Best model saved at: {results.save_dir}/weights/best.pt")
    print(f"Last model saved at: {results.save_dir}/weights/last.pt")
    
    return results


def validate_model(model_path: str, data_yaml: str, imgsz: int = 640):
    """
    Validate a trained model.
    
    Args:
        model_path: Path to the trained model
        data_yaml: Path to dataset YAML configuration
        imgsz: Image size for validation
    """
    model = YOLO(model_path)
    results = model.val(data=data_yaml, imgsz=imgsz)
    print(f"\nValidation Results:")
    print(f"mAP50: {results.box.map50}")
    print(f"mAP50-95: {results.box.map}")
    return results


def main():
    parser = argparse.ArgumentParser(description="Train YOLOv8 model for ball detection")
    parser.add_argument(
        "--data",
        type=str,
        required=True,
        help="Path to dataset root directory (should contain images/ and labels/ folders)"
    )
    parser.add_argument(
        "--classes",
        type=str,
        nargs="+",
        default=["white", "red", "half"],
        help="List of class names (default: white red half)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Path to pretrained model (e.g., 'yolov8n.pt' or 'data/whiffle_new_best.pt' for fine-tuning)"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=100,
        help="Number of training epochs (default: 100)"
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="Image size for training (default: 640)"
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=16,
        help="Batch size (default: 16)"
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Device to use ('cpu', '0', '0,1', etc.) or None for auto"
    )
    parser.add_argument(
        "--name",
        type=str,
        default="ball_detection",
        help="Experiment name (default: ball_detection)"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run validation after training"
    )
    parser.add_argument(
        "--val-only",
        type=str,
        default=None,
        help="Only validate (provide path to model .pt file)"
    )
    
    args = parser.parse_args()
    
    # Create dataset YAML
    data_yaml = create_dataset_yaml(args.data, args.classes)
    
    if args.val_only:
        # Only validate
        validate_model(args.val_only, data_yaml, args.imgsz)
    else:
        # Train model
        results = train_model(
            model_path=args.model,
            data_yaml=data_yaml,
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            device=args.device,
            name=args.name,
        )
        
        # Validate if requested
        if args.validate:
            best_model = os.path.join(results.save_dir, "weights", "best.pt")
            validate_model(best_model, data_yaml, args.imgsz)


if __name__ == "__main__":
    main()

