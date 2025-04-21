from ultralytics import YOLO

# Load a pretrained YOLOv8 model
model = YOLO('yolov8n.pt')  # Use 'yolov8n.pt' for a lightweight model

# Train the model with data augmentation enabled
model.train(
    data='F:/Whiffle/9.6 (pickupsticks)/data.yaml',
    epochs=100,  # Increased from 50 to 100 for better training with augmentation
    imgsz=640,
    batch=16,
    device='gpu',  # Using CPU as per your setup
    patience=50,
    name='whiffle_exp',
    # Data augmentation parameters
    hsv_h=0.015,  # Hue augmentation (default: 0.015)
    hsv_s=0.7,    # Saturation augmentation (default: 0.7)
    hsv_v=0.4,    # Value/Brightness augmentation (default: 0.4)
    degrees=10.0, # Random rotation up to ±10 degrees
    translate=0.1, # Random translation up to ±10% of image size
    scale=0.5,    # Random scaling from 0.5x to 1.5x
    shear=2.0,    # Random shear up to ±2 degrees
    perspective=0.0001, # Slight perspective transformation
    flipud=0.5,   # 50% chance of flipping upside down
    fliplr=0.5,   # 50% chance of flipping left to right
    mosaic=1.0,   # Always apply mosaic augmentation
    mixup=0.0,    # Disable mixup (optional, can enable if needed)
    copy_paste=0.0, # Disable copy-paste (optional, can enable if needed)
    erasing=0.4,  # 40% chance of random erasing
)

# Evaluate the model on the validation set
model.val()