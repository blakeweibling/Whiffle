from ultralytics import YOLO

# Load the model
model = YOLO('whiffle_new_best.pt')  # Fine-tune your existing model

# Train the model on your new dataset
model.train(
    data='dataset/data.yaml',  # Path to your data.yaml file
    epochs=50,
    imgsz=736,  # Match the height of your game resolution (1280x720), rounded to multiple of 32
    batch=4,  # Reduced for CPU training
    device='gpu',
    patience=20,
    name='whiffle_new_data',
    workers=4,  # Reduced for CPU
    optimizer='AdamW',
    lr0=0.001,
    augment=True,
    rect=True,  # Handle rectangular images (1280x720) without distortion
    save=True,
    save_period=10,  # Save checkpoint every 10 epochs
    plots=True  # Generate training plots
)

# Evaluate the model on the validation set
model.val()

# Save the trained model
model.save('whiffle_new_best.pt')