import os
from PIL import Image
import glob

def remove_iccp_profile(image_path):
    """Remove ICCP profile from a PNG image."""
    try:
        # Open the image
        img = Image.open(image_path)
        
        # Convert to RGB/RGBA to remove ICCP profile
        if img.mode in ('RGBA', 'LA'):
            background = Image.new('RGBA', img.size, (255, 255, 255, 0))
            background.paste(img, mask=img.split()[-1])
            img = background
        elif img.mode == 'P':
            img = img.convert('RGBA')
        else:
            img = img.convert('RGB')
        
        # Save without ICCP profile
        img.save(image_path, 'PNG', optimize=True)
        print(f"Fixed {image_path}")
    except Exception as e:
        print(f"Error processing {image_path}: {e}")

def main():
    # Get all PNG files in the assets directory
    png_files = glob.glob('assets/*.png')
    
    print(f"Found {len(png_files)} PNG files to process")
    
    # Process each PNG file
    for png_file in png_files:
        remove_iccp_profile(png_file)
    
    print("Finished processing all PNG files")

if __name__ == "__main__":
    main() 