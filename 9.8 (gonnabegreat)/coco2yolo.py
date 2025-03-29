import json
import os
import argparse

def coco_to_yolo(coco_json_path, output_dir):
    """
    Convert COCO annotations to YOLO format for the Whiffle project.

    Args:
        coco_json_path (str): Path to the COCO JSON file.
        output_dir (str): Directory to save the YOLO .txt files.
    """
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Load the COCO JSON file
    with open(coco_json_path, 'r') as f:
        coco_data = json.load(f)

    # Create a mapping from image ID to image info
    image_id_to_info = {img['id']: img for img in coco_data['images']}

    # Map COCO category IDs to YOLO class IDs (0-based)
    # COCO: white=1, red=2, half=3
    # YOLO: white=0, red=1, half=2
    category_id_to_yolo_id = {cat['id']: idx for idx, cat in enumerate(coco_data['categories'])}
    print("Category ID mapping:", category_id_to_yolo_id)

    # Map state values to numerical IDs
    state_map = {'on_playfield': 0, 'in_hole': 1}

    # Process each annotation
    annotations_by_image = {}
    for ann in coco_data['annotations']:
        image_id = ann['image_id']
        if image_id not in annotations_by_image:
            annotations_by_image[image_id] = []
        annotations_by_image[image_id].append(ann)

    # Convert annotations for each image
    for image_id, annotations in annotations_by_image.items():
        image_info = image_id_to_info[image_id]
        image_width = image_info['width']
        image_height = image_info['height']
        image_filename = image_info['file_name']

        # Create a .txt file for this image
        txt_filename = os.path.splitext(image_filename)[0] + '.txt'
        txt_path = os.path.join(output_dir, txt_filename)

        with open(txt_path, 'w') as f:
            for ann in annotations:
                # Get YOLO class ID (adjust for 0-based indexing)
                coco_category_id = ann['category_id']
                class_id = category_id_to_yolo_id[coco_category_id]

                # Get bounding box in COCO format: [x_min, y_min, width, height]
                bbox = ann['bbox']
                x_min, y_min, width, height = bbox

                # Convert to YOLO format: [x_center, y_center, width, height] (normalized)
                x_center = (x_min + width / 2) / image_width
                y_center = (y_min + height / 2) / image_height
                width_norm = width / image_width
                height_norm = height / image_height

                # Get state attribute
                state = ann.get('attributes', {}).get('state', 'on_playfield')  # Default to 'on_playfield' if missing
                state_id = state_map[state]

                # Write to YOLO .txt file
                f.write(f"{class_id} {x_center:.6f} {y_center:.6f} {width_norm:.6f} {height_norm:.6f} {state_id}\n")

        print(f"Created {txt_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert COCO annotations to YOLO format.")
    parser.add_argument("coco_json_path", help="Path to the COCO JSON file")
    parser.add_argument("output_dir", help="Directory to save the YOLO .txt files")
    args = parser.parse_args()

    coco_to_yolo(args.coco_json_path, args.output_dir)