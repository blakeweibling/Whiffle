# train_ball_detector.py
import pickle
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as transforms
import numpy as np
from sklearn.model_selection import train_test_split
from models import BallClassifier  # Import BallClassifier from models.py

class BallDataset(Dataset):
    """Custom dataset for loading ball image patches and their labels."""
    def __init__(self, patches, labels, transform=None):
        self.patches = patches
        self.labels = labels
        self.transform = transform
        self.label_map = {"red": 0, "white": 1, "half": 2, "background": 3}

    def __len__(self):
        return len(self.patches)

    def __getitem__(self, idx):
        patch = self.patches[idx]
        label = self.label_map[self.labels[idx]]
        patch = patch.transpose((2, 0, 1))  # HWC to CHW
        patch = torch.tensor(patch, dtype=torch.float32) / 255.0  # Normalize to [0, 1]
        if self.transform:
            patch = self.transform(patch)
        return patch, label

def load_data(filename="labeled_data.pkl"):
    """Load labeled data from a pickle file."""
    try:
        with open(filename, "rb") as f:
            data = pickle.load(f)
        patches = [patch for patch, _ in data]
        labels = [label for _, label in data]
        return np.array(patches), labels
    except Exception as e:
        raise RuntimeError(f"Error loading data from {filename}: {e}")

def train_model():
    """Train the BallClassifier model on labeled data."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # Load data
    patches, labels = load_data()
    X_train, X_test, y_train, y_test = train_test_split(patches, labels, test_size=0.2, random_state=42)

    # Data augmentation
    transform = transforms.Compose([
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(10),
    ])

    train_dataset = BallDataset(X_train, y_train, transform=transform)
    test_dataset = BallDataset(X_test, y_test)
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=32)

    # Initialize model, loss, and optimizer
    model = BallClassifier().to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    # Training loop
    num_epochs = 50
    for epoch in range(num_epochs):
        model.train()
        running_loss = 0.0
        for inputs, targets in train_loader:
            inputs, targets = inputs.to(device), targets.to(device)
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            running_loss += loss.item()
        print(f"Epoch {epoch+1}/{num_epochs}, Loss: {running_loss/len(train_loader):.4f}")

        # Validation
        model.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for inputs, targets in test_loader:
                inputs, targets = inputs.to(device), targets.to(device)
                outputs = model(inputs)
                _, predicted = torch.max(outputs, 1)
                total += targets.size(0)
                correct += (predicted == targets).sum().item()
        accuracy = correct / total
        print(f"Validation Accuracy: {accuracy:.4f}")

    # Save the model
    try:
        torch.save(model.state_dict(), "ball_detector_cnn.pth")
        print("Model saved as ball_detector_cnn.pth")
    except Exception as e:
        print(f"Error saving model: {e}")

if __name__ == "__main__":
    try:
        train_model()
    except Exception as e:
        print(f"Error during training: {e}")