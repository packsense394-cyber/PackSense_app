#!/usr/bin/env python3
"""
Simple test script to debug image extraction issues
"""

import os
import requests
from scraper import download_image

def test_amazon_image_download():
    """Test downloading Amazon review images with different URL patterns"""
    
    # Sample Amazon review image URLs (these are common patterns)
    test_urls = [
        "https://images-na.ssl-images-amazon.com/images/I/31WdMz5JJtL._SY88.jpg",
        "https://m.media-amazon.com/images/I/71aswuSrDrL._SY88.jpg",
        "https://images-na.ssl-images-amazon.com/images/I/71zbpRsiV6L._SY88.jpg",
        "https://images-na.ssl-images-amazon.com/images/I/71AfFnUhLyL._SY88.jpg",
        "https://images-na.ssl-images-amazon.com/images/I/71b34UiUEUL._SY88.jpg"
    ]
    
    # Create test folder
    test_folder = "test_extraction"
    os.makedirs(test_folder, exist_ok=True)
    
    print("Testing Amazon image download function...")
    print("=" * 60)
    
    success_count = 0
    total_count = len(test_urls)
    
    for i, url in enumerate(test_urls):
        filename = f"amazon_test_{i}.jpg"
        print(f"\nTest {i+1}/{total_count}: {url}")
        print(f"Filename: {filename}")
        
        result = download_image(url, test_folder, filename)
        
        if result:
            print(f"✅ SUCCESS: Downloaded to {result}")
            file_size = os.path.getsize(result)
            print(f"   File size: {file_size} bytes")
            success_count += 1
        else:
            print(f"❌ FAILED: Could not download {filename}")
    
    print("\n" + "=" * 60)
    print(f"Test Results: {success_count}/{total_count} images downloaded successfully")
    
    if success_count == 0:
        print("\n🔍 DIAGNOSIS:")
        print("No images were downloaded. Possible causes:")
        print("1. Amazon is blocking automated downloads")
        print("2. Network connectivity issues")
        print("3. Image URLs are no longer valid")
        print("4. Missing required headers or authentication")
        
        print("\n💡 SUGGESTIONS:")
        print("1. Check your internet connection")
        print("2. Try running the test again")
        print("3. Check if Amazon has changed their image URL patterns")
        print("4. Consider using a VPN if Amazon is blocking your IP")
    
    elif success_count < total_count:
        print(f"\n⚠️  PARTIAL SUCCESS: {total_count - success_count} images failed")
        print("Some images downloaded successfully, others failed.")
        print("This suggests intermittent issues or some URLs are invalid.")
    
    else:
        print("\n🎉 ALL TESTS PASSED!")
        print("Image download function is working correctly.")
    
    # List all downloaded files
    if os.path.exists(test_folder):
        files = os.listdir(test_folder)
        if files:
            print(f"\n📁 Files in {test_folder}:")
            for f in files:
                path = os.path.join(test_folder, f)
                size = os.path.getsize(path)
                print(f"  {f}: {size} bytes")
        else:
            print(f"\n📁 No files in {test_folder}")

if __name__ == "__main__":
    test_amazon_image_download() 