import os

label_dir = "F:/Whiffle/11.9/dataset/labels/val"
for file in os.listdir(label_dir):
    if file.endswith(".txt"):
        path = os.path.join(label_dir, file)
        with open(path, "r") as f:
            lines = set(f.readlines())  # Remove duplicates
        with open(path, "w") as f:
            f.writelines(lines)