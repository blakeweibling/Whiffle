import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import pickle

# Load data
try:
    data = pd.read_csv("training_data.csv")
    print(data.head())
except FileNotFoundError:
    print("Error: training_data.csv not found. Please run the game to collect data first.")
    exit(1)

# Check if data is empty
if data.empty:
    print("Error: training_data.csv is empty. Please collect more data by playing the game.")
    exit(1)

# Prepare features and labels
le = LabelEncoder()
data["ball_type"] = le.fit_transform(data["ball_type"])  # Encode ball types (white=0, red=1, half=2)
X = data[["x", "y", "ball_type"]]
y = data["score"]

# Handle imbalanced data by oversampling non-zero scores
non_zero_data = data[data["score"] > 0]
zero_data = data[data["score"] == 0]
if len(non_zero_data) > 0 and len(zero_data) > 0:
    oversampled_non_zero = non_zero_data.sample(n=len(zero_data), replace=True, random_state=42)
    balanced_data = pd.concat([zero_data, oversampled_non_zero])
    X = balanced_data[["x", "y", "ball_type"]]
    y = balanced_data["score"]

# Split data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train Random Forest Regressor
model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Evaluate
score = model.score(X_test, y_test)
print(f"Model R^2 score: {score:.2f}")

# Save model and encoder
with open("score_model.pkl", "wb") as f:
    pickle.dump(model, f)
with open("ball_type_encoder.pkl", "wb") as f:
    pickle.dump(le, f)
print("Model and encoder saved as score_model.pkl and ball_type_encoder.pkl")