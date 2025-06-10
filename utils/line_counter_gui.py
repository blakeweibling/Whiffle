import tkinter as tk
from tkinter import filedialog, messagebox
import os

# Global variable to store per-file line counts for details view
file_line_counts = []

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
    global file_line_counts
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
    file_line_counts = []  # Reset for each run

    try:
        for root_dir, dirs, files in os.walk(folder_path):
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root_dir, file)
                    py_files_found.append(file_path)
                    line_count = count_lines_in_file(file_path)
                    total_lines += line_count
                    file_count += 1
                    file_line_counts.append((file_path, line_count))

        if file_count > 0:
            result_label.config(text=f"Total lines in {file_count} .py files: {total_lines}")
            show_details_button.config(state=tk.NORMAL)
        else:
            result_label.config(text="No .py files found in the selected folder.")
            show_details_button.config(state=tk.DISABLED)

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {e}")
        result_label.config(text="Error occurred during counting.")
        selected_folder_label.config(text="Selected Folder: ")
        show_details_button.config(state=tk.DISABLED)

def show_more_details():
    if show_details_button['text'] == "Show More Details":
        file_details_text.config(state=tk.NORMAL)
        file_details_text.delete(1.0, tk.END)
        if not file_line_counts:
            file_details_text.insert(tk.END, "No details to show. Please count lines first.\n")
            file_details_text.config(state=tk.DISABLED)
            return
        # Sort by line count descending
        sorted_files = sorted(file_line_counts, key=lambda x: x[1], reverse=True)
        file_details_text.insert(tk.END, f"{'Lines':>8} | File\n")
        file_details_text.insert(tk.END, f"{'-'*8}-+-{'-'*60}\n")
        for file_path, line_count in sorted_files:
            display_path = file_path
            file_details_text.insert(tk.END, f"{line_count:8} | {display_path}\n")
        file_details_text.config(state=tk.DISABLED)
        show_details_button.config(text="Show Less Details")
        root.geometry("900x600")  # Grow taller
    else:
        file_details_text.config(state=tk.NORMAL)
        file_details_text.delete(1.0, tk.END)
        file_details_text.config(state=tk.DISABLED)
        show_details_button.config(text="Show More Details")
        root.geometry("900x300")  # Shrink back

# --- GUI Setup ---
root = tk.Tk()
root.title("Python Line Counter")
root.geometry("900x300") # Set a wider initial size

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

# Add the Show More Details button, initially disabled, directly below the result_label
show_details_button = tk.Button(main_frame, text="Show More Details", command=show_more_details, state=tk.DISABLED)
show_details_button.pack(pady=5)

# Add a frame to hold the text widget and its scrollbar
file_details_frame = tk.Frame(main_frame)
file_details_frame.pack(pady=5, fill=tk.BOTH, expand=True)

# Add the Text widget for details (no fixed height)
file_details_text = tk.Text(file_details_frame, wrap=tk.NONE, font=("Consolas", 11), state=tk.DISABLED)
file_details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Add a vertical scrollbar and link it to the text widget
file_details_scrollbar = tk.Scrollbar(file_details_frame, orient=tk.VERTICAL, command=file_details_text.yview)
file_details_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
file_details_text.config(yscrollcommand=file_details_scrollbar.set)

# Run the GUI event loop
root.mainloop()