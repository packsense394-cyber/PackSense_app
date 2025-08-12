#!/usr/bin/env python3
"""
Debug script to test image extraction from Amazon reviews
"""

import os
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from scraper import amazon_sign_in, download_image

def debug_image_extraction():
    """Test image extraction from a sample Amazon review page"""
    
    # Test with a sample Amazon review URL
    review_url = "https://www.amazon.com/product-reviews/B085V5PPP8/"
    email = "your-email@example.com"  # Replace with your email
    password = "your-password"        # Replace with your password
    
    print("Debugging image extraction...")
    print("=" * 50)
    
    # Setup Chrome driver
    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/112.0.0.0 Safari/537.36"
    )
    
    driver = webdriver.Chrome(options=options)
    
    try:
        # Sign in to Amazon
        print("Signing in to Amazon...")
        if not amazon_sign_in(driver, email, password, review_url):
            print("Failed to sign in to Amazon")
            return
        
        print("Successfully signed in to Amazon")
        
        # Navigate to reviews page
        driver.get(review_url)
        print(f"Navigated to: {review_url}")
        
        # Wait for page to load
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "cm_cr-review_list"))
        )
        print("Reviews page loaded")
        
        # Scroll to load lazy-loaded content
        print("Scrolling to load all content...")
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            import time
            time.sleep(2)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        
        # Find review blocks
        review_blocks = driver.find_elements(By.XPATH, "//*[@data-hook='review']")
        print(f"Found {len(review_blocks)} review blocks")
        
        # Create test folder
        test_folder = "debug_images"
        os.makedirs(test_folder, exist_ok=True)
        
        # Test image extraction on first few reviews
        for i, block in enumerate(review_blocks[:3]):  # Test first 3 reviews
            print(f"\n--- Review {i+1} ---")
            
            # Try different image selectors
            selectors = [
                ".//img[contains(@class,'review-image')]",
                ".//img[contains(@data-hook,'review-image')]",
                ".//div[contains(@class,'review-image-tile-section')]//img",
                ".//img[contains(@src,'amazon.com')]",
                ".//img"
            ]
            
            for j, selector in enumerate(selectors):
                imgs = block.find_elements(By.XPATH, selector)
                print(f"Selector {j+1}: {selector} - Found {len(imgs)} images")
                
                for k, img in enumerate(imgs):
                    src = img.get_attribute("src")
                    data_src = img.get_attribute("data-src")
                    print(f"  Image {k+1}: src='{src}', data-src='{data_src}'")
                    
                    if src and src.startswith("http"):
                        # Try to download
                        filename = f"review_{i+1}_selector_{j+1}_img_{k+1}.jpg"
                        print(f"  Attempting to download: {filename}")
                        result = download_image(src, test_folder, filename)
                        if result:
                            print(f"  ✅ Successfully downloaded: {result}")
                        else:
                            print(f"  ❌ Failed to download: {filename}")
        
        print(f"\nDebug completed. Check the '{test_folder}' folder for downloaded images.")
        
    except Exception as e:
        print(f"Error during debug: {e}")
        import traceback
        traceback.print_exc()
    finally:
        driver.quit()

if __name__ == "__main__":
    debug_image_extraction() 