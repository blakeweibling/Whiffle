import os
import json

def split_labels(input_dir, output_dir, state_output_file):
    """
    Split YOLO label files with 6 columns into 5-column files for training and save state info separately.

    Args:
        input_dir (str): Directory containing the original label files (6 columns).
        output_dir (str): Directory to save the new label files (5 columns).
        state_output_file (str): File to save the state information as JSON.
    """
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Dictionary to store state information
    state_info = {}

    # Process each label file in the input directory
    for filename in os.listdir(input_dir):
        if not filename.endswith('.txt'):
            continue

        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, filename)

        # Read the original label file
        with open(input_path, 'r') as f:
            lines = f.readlines()

        # Process each line and extract the first 5 columns
        new_lines = []
        states = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) != 6:
                print(f"Warning: Skipping invalid line in {filename}: {line}")
                continue

            # Extract the first 5 columns (class_id, x_center, y_center, width, height)
            new_line = ' '.join(parts[:5]) + '\n'
            new_lines.append(new_line)

            # Extract the state (6th column)
            state = int(parts[5])
            states.append(state)

        # Write the new label file with 5 columns
        with open(output_path, 'w') as f:
            f.writelines(new_lines)

        # Store the state information
        state_info[os.path.splitext(filename)[0]] = states

        print(f"Processed {filename}")

    # Save the state information to a JSON file
    with open(state_output_file, 'w') as f:
        json.dump(state_info, f, indent=4)

    print(f"Saved state information to {state_output_file}")

# Run the script for both training and validation sets
split_labels('dataset/labels/train', 'dataset/labels/train_yolo', 'dataset/states_train.json')
split_labels('dataset/labels/val', 'dataset/labels/val_yolo', 'dataset/states_val.json')