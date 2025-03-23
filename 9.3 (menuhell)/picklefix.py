import pickle

# Load existing zones
with open("zones.pkl", "rb") as f:
    zones = pickle.load(f)

# Add a new 10-point zone around (893, 445)
new_zone = (893, 445, 40, 40, 10)  # x, y, width, height, points
zones.append(new_zone)

# Save the updated zones
with open("zones.pkl", "wb") as f:
    pickle.dump(zones, f)

print(f"Updated zones.pkl with new 10-point zone: {new_zone}")