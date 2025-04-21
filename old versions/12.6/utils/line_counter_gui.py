import tkinter as tk
from tkinter import filedialog, messagebox
import os

def count_lines_in_file(filepath):
    """Counts the lines in a single file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return len(f.readlines())
    except Exception as e:
        print(f"Error reading file {filepath}: {e}")
        return 0

def select_folder_and_count():
    """Opens a folder dialog, then counts lines in .py files within it."""
    folder_path = filedialog.askdirectory()
    if not folder_path:
        # User cancelled the dialog
        return

    selected_folder_label.config(text=f"Selected Folder: {folder_path}")
    result_label.config(text="Counting lines...")
    # Force GUI update to show "Counting..." message immediately
    root.update_idletasks()

    total_lines = 0
    file_count = 0
    py_files_found = []

    try:
        for root_dir, dirs, files in os.walk(folder_path):
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root_dir, file)
                    py_files_found.append(file_path)
                    line_count = count_lines_in_file(file_path)
                    total_lines += line_count
                    file_count += 1

        if file_count > 0:
            result_label.config(text=f"Total lines in {file_count} .py files: {total_lines}")
        else:
            result_label.config(text="No .py files found in the selected folder.")

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {e}")
        result_label.config(text="Error occurred during counting.")
        selected_folder_label.config(text="Selected Folder: ")


# --- GUI Setup ---
root = tk.Tk()
root.title("Python Line Counter")
root.geometry("500x200") # Set a reasonable initial size

# Frame for better organization
main_frame = tk.Frame(root, padx=10, pady=10)
main_frame.pack(expand=True, fill=tk.BOTH)

# Button to select folder
select_button = tk.Button(main_frame, text="Select Folder", command=select_folder_and_count)
select_button.pack(pady=10)

# Label to display the selected folder path
selected_folder_label = tk.Label(main_frame, text="Selected Folder: ", wraplength=480, justify=tk.LEFT)
selected_folder_label.pack(pady=5)

# Label to display the result
result_label = tk.Label(main_frame, text="Result will be shown here", font=("Arial", 12))
result_label.pack(pady=10)

# Run the GUI event loop
root.mainloop()