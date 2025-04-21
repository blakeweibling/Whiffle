import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox


def coco_to_yolo(coco_json_path, output_dir):
    """
    Convert COCO annotations to YOLO format for the Whiffle project.
    """
    try:
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Load the COCO JSON file
        with open(coco_json_path, "r") as f:
            coco_data = json.load(f)

        # Create a mapping from image ID to image info
        image_id_to_info = {img["id"]: img for img in coco_data["images"]}

        # Map COCO category IDs to YOLO class IDs (0-based)
        category_id_to_yolo_id = {
            cat["id"]: idx for idx, cat in enumerate(coco_data["categories"])
        }

        # Process each annotation
        annotations_by_image = {}
        for ann in coco_data["annotations"]:
            image_id = ann["image_id"]
            if image_id not in annotations_by_image:
                annotations_by_image[image_id] = []
            annotations_by_image[image_id].append(ann)

        # Convert annotations for each image
        for image_id, annotations in annotations_by_image.items():
            image_info = image_id_to_info[image_id]
            image_width = image_info["width"]
            image_height = image_info["height"]
            image_filename = image_info["file_name"]

            # Create a .txt file for this image
            txt_filename = os.path.splitext(image_filename)[0] + ".txt"
            txt_path = os.path.join(output_dir, txt_filename)

            with open(txt_path, "w") as f:
                for ann in annotations:
                    coco_category_id = ann["category_id"]
                    class_id = category_id_to_yolo_id[coco_category_id]
                    bbox = ann["bbox"]
                    x_min, y_min, width, height = bbox

                    # Convert to YOLO format
                    x_center = (x_min + width / 2) / image_width
                    y_center = (y_min + height / 2) / image_height
                    width_norm = width / image_width
                    height_norm = height / image_height

                    f.write(
                        f"{class_id} {x_center:.6f} {y_center:.6f} {width_norm:.6f} {height_norm:.6f}\n"
                    )

        return (
            True,
            f"Conversion completed successfully!\nOutput saved to: {output_dir}",
        )
    except Exception as e:
        return False, f"Error during conversion: {str(e)}"


class CocoToYoloGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("COCO to YOLO Converter")
        self.root.geometry("400x300")

        # Variables to store file paths
        self.coco_path = tk.StringVar()
        self.output_dir = tk.StringVar()

        # GUI Elements
        tk.Label(root, text="COCO to YOLO Converter", font=("Arial", 14)).pack(pady=10)

        # COCO JSON selection
        tk.Label(root, text="COCO JSON File:").pack()
        tk.Entry(root, textvariable=self.coco_path, width=40).pack()
        tk.Button(root, text="Browse", command=self.browse_coco).pack(pady=5)

        # Output directory selection
        tk.Label(root, text="Output Directory:").pack()
        tk.Entry(root, textvariable=self.output_dir, width=40).pack()
        tk.Button(root, text="Browse", command=self.browse_output).pack(pady=5)

        # Convert button
        tk.Button(
            root, text="Convert", command=self.convert, bg="green", fg="white"
        ).pack(pady=20)

    def browse_coco(self):
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            self.coco_path.set(filename)

    def browse_output(self):
        directory = filedialog.askdirectory()
        if directory:
            self.output_dir.set(directory)

    def convert(self):
        coco_path = self.coco_path.get()
        output_dir = self.output_dir.get()

        if not coco_path or not output_dir:
            messagebox.showerror(
                "Error", "Please select both input file and output directory"
            )
            return

        success, message = coco_to_yolo(coco_path, output_dir)
        if success:
            messagebox.showinfo("Success", message)
        else:
            messagebox.showerror("Error", message)


if __name__ == "__main__":
    root = tk.Tk()
    app = CocoToYoloGUI(root)
    root.mainloop()
