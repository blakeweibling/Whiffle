import pickle

with open("labeled_data.pkl", "rb") as f:
    data = pickle.load(f)

label_counts = {"red": 0, "white": 0, "half": 0, "background": 0}
for _, label in data:
    label_counts[label] = label_counts.get(label, 0) + 1

print("Label counts:", label_counts)
print("Total samples:", len(data))