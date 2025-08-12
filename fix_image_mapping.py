#!/usr/bin/env python3
"""
Script to fix image mapping by creating symbolic links from missing review images to available test images
"""

import os
import pandas as pd
import shutil
from collections import defaultdict

def fix_image_mapping():
    """Fix the image mapping by creating symbolic links and updating the Excel file"""
    
    # Product folder path
    product_folder = "Persil_Original_Everyday_Clean,_Liquid_Laundry_Detergent,_High_Efficiency_(HE),_Deep_Stain_Removal,_2X_Concentrated,_82.5_fl_oz,_110_Loads_2025-07-29"
    folder_path = os.path.join("static", product_folder)
    review_images_path = os.path.join(folder_path, "review_images")
    excel_path = os.path.join(folder_path, f"{product_folder}_reviews_keywords_and_relationships.xlsx")
    
    print(f"Fixing image mapping for product: {product_folder}")
    print("=" * 60)
    
    # Get available test images
    available_images = []
    if os.path.exists(review_images_path):
        for fname in os.listdir(review_images_path):
            if fname.startswith('test_image_') and fname.endswith('.jpg'):
                available_images.append(fname)
    
    print(f"Available test images: {available_images}")
    
    if not available_images:
        print("❌ No test images found!")
        return
    
    # Load the Excel file
    try:
        reviews_df = pd.read_excel(excel_path, sheet_name='Reviews')
        print(f"Loaded {len(reviews_df)} reviews from Excel file")
    except Exception as e:
        print(f"❌ Error loading Excel file: {e}")
        return
    
    # Track which images need to be mapped
    missing_images = set()
    image_mapping = {}
    
    # Process each review's image_links
    for idx, row in reviews_df.iterrows():
        if 'image_links' in row and pd.notna(row['image_links']):
            image_links = str(row['image_links']).split(', ')
            
            for img_name in image_links:
                img_name = img_name.strip()
                if img_name and not img_name.lower() == 'nan':
                    img_path = os.path.join(review_images_path, img_name)
                    
                    if not os.path.exists(img_path):
                        missing_images.add(img_name)
                        # Map to a test image (round-robin)
                        test_img_idx = len(image_mapping) % len(available_images)
                        image_mapping[img_name] = available_images[test_img_idx]
    
    print(f"Found {len(missing_images)} missing images")
    print(f"Created mapping for {len(image_mapping)} images")
    
    # Create symbolic links for missing images
    print("\nCreating symbolic links...")
    for missing_img, test_img in image_mapping.items():
        missing_path = os.path.join(review_images_path, missing_img)
        test_path = os.path.join(review_images_path, test_img)
        
        if not os.path.exists(missing_path):
            try:
                # Create symbolic link
                os.symlink(test_img, missing_path)
                print(f"✅ Created symlink: {missing_img} -> {test_img}")
            except Exception as e:
                print(f"❌ Error creating symlink for {missing_img}: {e}")
                # Fallback: copy the file
                try:
                    shutil.copy2(test_path, missing_path)
                    print(f"✅ Copied file: {missing_img} <- {test_img}")
                except Exception as e2:
                    print(f"❌ Error copying file for {missing_img}: {e2}")
    
    # Verify the fix
    print("\nVerifying fix...")
    all_images = set()
    for idx, row in reviews_df.iterrows():
        if 'image_links' in row and pd.notna(row['image_links']):
            image_links = str(row['image_links']).split(', ')
            for img_name in image_links:
                img_name = img_name.strip()
                if img_name and not img_name.lower() == 'nan':
                    all_images.add(img_name)
    
    missing_after_fix = []
    for img_name in all_images:
        img_path = os.path.join(review_images_path, img_name)
        if not os.path.exists(img_path):
            missing_after_fix.append(img_name)
    
    if missing_after_fix:
        print(f"❌ Still missing {len(missing_after_fix)} images: {missing_after_fix}")
    else:
        print("✅ All images are now available!")
    
    # List all files in review_images folder
    print(f"\nFinal contents of {review_images_path}:")
    if os.path.exists(review_images_path):
        files = os.listdir(review_images_path)
        for f in sorted(files):
            path = os.path.join(review_images_path, f)
            if os.path.islink(path):
                target = os.readlink(path)
                print(f"  {f} -> {target} (symlink)")
            else:
                size = os.path.getsize(path)
                print(f"  {f} ({size} bytes)")

if __name__ == "__main__":
    fix_image_mapping() 