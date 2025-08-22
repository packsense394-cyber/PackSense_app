#!/usr/bin/env python3

import os
import sys
from PIL import Image, ImageDraw, ImageFont
from collections import defaultdict
import math
import numpy as np

# Add the current directory to the path so we can import from scraper
sys.path.append('.')

from scraper import generate_defect_overlay, build_defect_coords_map

def test_defect_overlay():
    """Test the defect overlay generation functionality"""
    
    # Test data
    product_folder = "Tide_Liquid_Laundry_Detergent,_Original,_64_loads,_84_fl_oz,_HE_Compatible_(Packaging_May_Vary)_2025-08-20"
    folder = os.path.join("static", product_folder)
    product_image_path = os.path.join(folder, "product.jpg")
    
    # Sample defect pairs
    defect_pairs = [
        ("bottle", "leak"),
        ("cap", "loose"),
        ("package", "damage"),
        ("container", "mess")
    ]
    
    print(f"Testing defect overlay generation...")
    print(f"Product image path: {product_image_path}")
    print(f"Defect pairs: {defect_pairs}")
    
    if not os.path.exists(product_image_path):
        print(f"❌ Product image not found: {product_image_path}")
        return False
    
    try:
        # Build coordinates map for defect locations
        print("Building defect coordinates map...")
        coords_map = build_defect_coords_map(product_image_path, defect_pairs)
        print(f"Coordinates map: {coords_map}")
        
        # Generate the defect overlay
        overlay_path = os.path.join(folder, "defects_overlay.png")
        print(f"Generating defect overlay at: {overlay_path}")
        generate_defect_overlay(product_image_path, defect_pairs, coords_map, overlay_path)
        
        if os.path.exists(overlay_path):
            print(f"✅ Defect overlay generated successfully: {overlay_path}")
            return True
        else:
            print(f"❌ Defect overlay file not created: {overlay_path}")
            return False
            
    except Exception as e:
        print(f"❌ Error generating defect overlay: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_defect_overlay()
    if success:
        print("\n🎉 Defect overlay generation test passed!")
    else:
        print("\n💥 Defect overlay generation test failed!")
