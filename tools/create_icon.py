"""Create a trading app icon with an upward green arrow."""
from PIL import Image, ImageDraw
import sys
from pathlib import Path

def create_icon_sizes():
    """Create icon in multiple sizes for .ico file."""
    sizes = [16, 32, 48, 256]
    images = []
    
    for size in sizes:
        # Create transparent image
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Green color for upward trend (same as alert icon)
        green = (0, 150, 0, 255)
        
        # Calculate triangle points
        # For upward triangle pointing up
        margin = max(2, size // 8)
        center_x = size // 2
        
        points = [
            (center_x, margin),  # Top point
            (margin, size - margin),  # Bottom left
            (size - margin, size - margin),  # Bottom right
        ]
        
        # Draw filled triangle
        draw.polygon(points, fill=green, outline=green)
        
        # Optionally add a subtle border
        if size >= 32:
            border_points = [
                (center_x - 1, margin),
                (margin, size - margin),
                (size - margin, size - margin),
            ]
            # Slightly darker border
            draw.polygon(border_points, fill=(0, 130, 0, 255))
            draw.polygon(points, fill=green)
        
        images.append(img)
    
    return images

def main():
    """Generate the icon file."""
    # Get the trading_app directory
    script_dir = Path(__file__).parent
    trading_app_dir = script_dir.parent / 'trading_app'
    
    # Create icon images
    images = create_icon_sizes()
    
    # Save as .ico file with multiple sizes
    ico_path = trading_app_dir / 'icon.ico'
    # Save all images as ICO - Pillow handles multiple sizes
    images[0].save(
        ico_path,
        format='ICO',
        sizes=[(img.width, img.height) for img in images],
        append_images=images[1:] if len(images) > 1 else []
    )
    
    # Also save as PNG (256x256) for reference
    png_path = trading_app_dir / 'icon.png'
    images[-1].save(png_path, format='PNG')
    
    print(f"Icon created: {ico_path}")
    print(f"PNG version created: {png_path}")
    print("\nIcon sizes included:")
    for img in images:
        print(f"  - {img.width}x{img.height}")

if __name__ == '__main__':
    try:
        main()
    except ImportError as e:
        print(f"Error: {e}")
        print("Make sure Pillow is installed: pip install Pillow")
        sys.exit(1)
    except Exception as e:
        print(f"Error creating icon: {e}")
        sys.exit(1)

