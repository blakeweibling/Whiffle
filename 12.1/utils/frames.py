import os


def rename_frames(directory):
    files = sorted([f for f in os.listdir(directory) if f.endswith(".jpg")])
    for i, filename in enumerate(files):
        new_name = f"frame_{i:04d}.jpg"
        os.rename(os.path.join(directory, filename), os.path.join(directory, new_name))
        print(f"Renamed {filename} to {new_name}")


# Example usage
rename_frames("dataset/images/train")
rename_frames("dataset/images/val")
