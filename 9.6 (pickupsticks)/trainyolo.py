from ultralytics import YOLO

# Load a pretrained YOLOv8 model
model = YOLO('yolov8n.pt')  # Use 'yolov8n.pt' for a lightweight model

# Train the model
model.train(
    data='F:/Whiffle/9.6 (pickupsticks)/data.yaml',
    epochs=100,
    imgsz=640,
    batch=16,
    device='cpu',  # Changed from '0' to 'cpu'
    patience=50,
    name='whiffle_exp'
)

# Evaluate the model on the validation set
model.val()