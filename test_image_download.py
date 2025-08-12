#!/usr/bin/env python3
"""
Test script to manually download sample Amazon review images
"""

import os
import requests
from scraper import download_image

def test_image_download():
    """Test downloading some sample Amazon review images"""
    
    # Sample Amazon review image URLs (these are common patterns)
    test_urls = [
        "https://images-na.ssl-images-amazon.com/images/I/31WdMz5JJtL._SY88.jpg",
        "https://m.media-amazon.com/images/I/71aswuSrDrL._SY88.jpg",
        "https://images-na.ssl-images-amazon.com/images/I/71zbpRsiV6L._SY88.jpg",
        "https://images-na.ssl-images-amazon.com/images/I/71AfFnUhLyL._SY88.jpg",
        "https://images-na.ssl-images-amazon.com/images/I/71b34UiUEUL._SY88.jpg"
    ]
    
    # Create test folder
    test_folder = "test_images"
    os.makedirs(test_folder, exist_ok=True)
    
    print("Testing image download function...")
    print("=" * 50)
    
    for i, url in enumerate(test_urls):
        filename = f"test_image_{i}.jpg"
        print(f"\nTesting URL {i+1}: {url}")
        print(f"Filename: {filename}")
        
        result = download_image(url, test_folder, filename)
        
        if result:
            print(f"✅ SUCCESS: Downloaded to {result}")
            # Check file size
            file_size = os.path.getsize(result)
            print(f"   File size: {file_size} bytes")
        else:
            print(f"❌ FAILED: Could not download {filename}")
    
    print("\n" + "=" * 50)
    print("Test completed!")
    
    # List all downloaded files
    if os.path.exists(test_folder):
        files = os.listdir(test_folder)
        print(f"\nFiles in {test_folder}:")
        for f in files:
            path = os.path.join(test_folder, f)
            size = os.path.getsize(path)
            print(f"  {f}: {size} bytes")

if __name__ == "__main__":
    test_image_download() 