import os
import tkinter as tk
from tkinter import filedialog, messagebox


def convert_py_to_txt():
    # Get the source directory
    source_dir = filedialog.askdirectory(title="Select Directory Containing .py Files")
    if not source_dir:
        return

    # Get the destination directory
    dest_dir = filedialog.askdirectory(title="Select Directory to Save .txt Files")
    if not dest_dir:
        return

    try:
        # Count converted files
        converted_count = 0

        # Iterate through files in source directory
        for filename in os.listdir(source_dir):
            if filename.endswith(".py"):
                source_path = os.path.join(source_dir, filename)
                # Create new filename with .txt extension
                new_filename = os.path.splitext(filename)[0] + ".txt"
                dest_path = os.path.join(dest_dir, new_filename)

                # Read .py file and write to .txt file
                with open(source_path, "r", encoding="utf-8") as py_file:
                    content = py_file.read()

                with open(dest_path, "w", encoding="utf-8") as txt_file:
                    txt_file.write(content)

                converted_count += 1

        # Show success message
        messagebox.showinfo(
            "Success",
            f"Converted {converted_count} .py files to .txt files\n"
            f"Saved to: {dest_dir}",
        )

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {str(e)}")


# Create the main window
root = tk.Tk()
root.title("PY to TXT Converter")
root.geometry("300x150")

# Create and pack widgets
label = tk.Label(root, text="Convert .py files to .txt files", font=("Arial", 12))
label.pack(pady=20)

convert_button = tk.Button(
    root,
    text="Select Directory and Convert",
    command=convert_py_to_txt,
    font=("Arial", 10),
)
convert_button.pack(pady=10)

# Start the application
root.mainloop()
