from ultralytics import YOLO

def main():
    # Load the model
    model = YOLO("whiffle_new_best.pt")

    # Train the model on your new dataset
    model.train(
        data="dataset/data.yaml",
        epochs=100,
        imgsz=736,
        batch=16,
        device=0,  # GPU
        patience=0,
        name="whiffle_new_data",
        workers=4,
        optimizer="AdamW",
        lr0=0.001,
        augment=True,
        rect=True,
        save=True,
        save_period=10,
        plots=True,
    )

    # Evaluate the model on the validation set
    model.val()

    # Save the trained model
    model.save("whiffle_new_best3.pt")

if __name__ == '__main__':
    main()