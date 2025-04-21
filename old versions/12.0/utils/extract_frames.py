import cv2
import os
import tkinter as tk
from tkinter import filedialog, messagebox
import threading

class VideoFrameExtractorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Frame Extractor")
        self.root.geometry("400x300")

        # Variables
        self.video_path = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.frame_interval = tk.IntVar(value=10)
        self.is_processing = False

        # GUI Elements
        tk.Label(root, text="Video File:").pack(pady=5)
        tk.Entry(root, textvariable=self.video_path, width=40).pack()
        tk.Button(root, text="Browse", command=self.select_video).pack()

        tk.Label(root, text="Output Directory:").pack(pady=5)
        tk.Entry(root, textvariable=self.output_dir, width=40).pack()
        tk.Button(root, text="Browse", command=self.select_output_dir).pack()

        tk.Label(root, text="Frame Interval:").pack(pady=5)
        tk.Entry(root, textvariable=self.frame_interval, width=10).pack()

        self.status = tk.Label(root, text="Ready")
        self.status.pack(pady=10)

        self.extract_btn = tk.Button(root, text="Extract Frames", command=self.start_extraction)
        self.extract_btn.pack(pady=10)

    def select_video(self):
        path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.avi *.mov")])
        if path:
            self.video_path.set(path)

    def select_output_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.output_dir.set(path)

    def extract_frames(self):
        video_path = self.video_path.get()
        output_dir = self.output_dir.get()
        frame_interval = self.frame_interval.get()

        # Validation
        if not video_path or not output_dir:
            messagebox.showerror("Error", "Please select both video file and output directory")
            self.update_status("Ready")
            return

        if frame_interval <= 0:
            messagebox.showerror("Error", "Frame interval must be positive")
            self.update_status("Ready")
            return

        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Open the video file
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            messagebox.showerror("Error", f"Could not open video file {video_path}")
            self.update_status("Ready")
            return

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.update_status(f"Extracting {total_frames} total frames...")

        frame_count = 0
        saved_count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % frame_interval == 0:
                frame_filename = os.path.join(output_dir, f"frame_{saved_count:04d}.jpg")
                cv2.imwrite(frame_filename, frame)
                saved_count += 1
                self.update_status(f"Saved {saved_count} frames...")

            frame_count += 1
            self.root.update()

        cap.release()
        self.update_status(f"Done! Extracted {saved_count} frames")
        messagebox.showinfo("Success", f"Extracted {saved_count} frames to {output_dir}")
        self.is_processing = False
        self.extract_btn.config(state="normal")

    def update_status(self, message):
        self.status.config(text=message)

    def start_extraction(self):
        if not self.is_processing:
            self.is_processing = True
            self.extract_btn.config(state="disabled")
            threading.Thread(target=self.extract_frames, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoFrameExtractorGUI(root)
    root.mainloop()