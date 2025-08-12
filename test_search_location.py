#!/usr/bin/env python3
"""
Test script to verify search location targeting
"""

import os
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
import time

def test_search_location():
    """Test to verify we're targeting the reviews search bar, not main search"""
    
    print("Testing search location targeting...")
    print("=" * 60)
    
    # Setup Chrome driver
    options = Options()
    # options.add_argument("--headless")  # Comment out headless for debugging
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/112.0.0.0 Safari/537.36"
    )
    
    driver = webdriver.Chrome(options=options)
    
    try:
        # Test with a sample Amazon product review page
        test_url = "https://www.amazon.com/product-reviews/B08N5WRWNW"
        print(f"Testing with URL: {test_url}")
        
        driver.get(test_url)
        time.sleep(5)
        
        print(f"Page title: {driver.title}")
        print(f"Current URL: {driver.current_url}")
        
        # Check if we're on the right page
        if "robot" in driver.page_source.lower() or "captcha" in driver.page_source.lower():
            print("⚠️  CAPTCHA or robot detection detected!")
            return
        
        print(f"Page source length: {len(driver.page_source)}")
        print(f"Contains 'review': {'Yes' if 'review' in driver.page_source.lower() else 'No'}")
        print(f"Contains 'search': {'Yes' if 'search' in driver.page_source.lower() else 'No'}")
        
        print("\n1. Checking for main search bar...")
        main_search_selectors = [
            "//input[@id='twotabsearchtextbox']",
            "//input[@name='field-keywords']",
            "//input[contains(@id, 'search')]"
        ]
        
        main_search_found = False
        for selector in main_search_selectors:
            try:
                main_search = driver.find_element(By.XPATH, selector)
                print(f"   Found main search with: {selector}")
                main_search_found = True
                break
            except NoSuchElementException:
                continue
        
        print("\n2. Checking for reviews search bar...")
        
        # First, let's see what elements are available
        print("   Available input elements:")
        all_inputs = driver.find_elements(By.XPATH, "//input[@type='text']")
        for i, inp in enumerate(all_inputs[:10]):  # Show first 10
            inp_id = inp.get_attribute("id") or "no-id"
            inp_name = inp.get_attribute("name") or "no-name"
            inp_placeholder = inp.get_attribute("placeholder") or "no-placeholder"
            inp_class = inp.get_attribute("class") or "no-class"
            print(f"     Input {i+1}: ID='{inp_id}', Name='{inp_name}', Placeholder='{inp_placeholder}', Class='{inp_class}'")
        
        print("\n   Available div elements with 'review' in class:")
        review_divs = driver.find_elements(By.XPATH, "//div[contains(@class, 'review')]")
        for i, div in enumerate(review_divs[:5]):  # Show first 5
            div_class = div.get_attribute("class") or "no-class"
            div_id = div.get_attribute("id") or "no-id"
            print(f"     Div {i+1}: ID='{div_id}', Class='{div_class}'")
        
        print("\n   Available elements with 'data-hook' attribute:")
        data_hook_elements = driver.find_elements(By.XPATH, "//*[@data-hook]")
        for i, elem in enumerate(data_hook_elements[:10]):  # Show first 10
            hook_value = elem.get_attribute("data-hook") or "no-hook"
            elem_tag = elem.tag_name
            print(f"     {elem_tag} {i+1}: data-hook='{hook_value}'")
        
        reviews_search_selectors = [
            "//input[@placeholder='Search reviews']",
            "//input[@placeholder='Search customer reviews']",
            "//input[@aria-label='Search reviews']",
            "//input[@aria-label='Search customer reviews']",
            "//input[@id='search-reviews']",
            "//input[@name='search-reviews']",
            "//div[contains(@class, 'reviews')]//input[@type='text']",
            "//div[contains(@class, 'review')]//input[@type='text']",
            "//section[contains(@class, 'reviews')]//input[@type='text']",
            "//div[@data-hook='reviews-medley']//input[@type='text']",
            "//div[contains(@class, 'filter')]//input[@type='text']",
            "//div[contains(@class, 'search')]//input[@type='text']",
            "//input[contains(@placeholder, 'review')]",
            "//input[contains(@placeholder, 'customer')]",
            "//input[@type='text'][not(contains(@id, 'twotabsearch'))][not(contains(@name, 'search'))]"
        ]
        
        reviews_search_found = False
        for selector in reviews_search_selectors:
            try:
                reviews_search = driver.find_element(By.XPATH, selector)
                print(f"   Found reviews search with: {selector}")
                
                # Check if it's not the main search
                search_id = reviews_search.get_attribute("id") or ""
                search_class = reviews_search.get_attribute("class") or ""
                
                if "twotabsearch" in search_id or "main-search" in search_class:
                    print(f"   ⚠️  WARNING: This appears to be the main search bar!")
                    print(f"      ID: {search_id}")
                    print(f"      Class: {search_class}")
                else:
                    print(f"   ✅ This appears to be the reviews search bar!")
                    print(f"      ID: {search_id}")
                    print(f"      Class: {search_class}")
                    reviews_search_found = True
                    break
                    
            except NoSuchElementException:
                continue
        
        print("\n3. Testing search functionality...")
        if reviews_search_found:
            try:
                print("   Attempting to search for 'packaging'...")
                reviews_search.clear()
                reviews_search.send_keys("packaging")
                reviews_search.send_keys(Keys.RETURN)
                time.sleep(3)
                
                # Check if search results are visible
                current_url = driver.current_url
                print(f"   Current URL after search: {current_url}")
                
                if "packaging" in current_url.lower():
                    print("   ✅ Search appears to have worked!")
                else:
                    print("   ⚠️  Search may not have worked as expected")
                    
            except Exception as e:
                print(f"   ❌ Error during search test: {e}")
        else:
            print("   ❌ No reviews search bar found")
        
        print("\n" + "=" * 60)
        print("TEST RESULTS:")
        print(f"Main search bar found: {'Yes' if main_search_found else 'No'}")
        print(f"Reviews search bar found: {'Yes' if reviews_search_found else 'No'}")
        
        if reviews_search_found:
            print("✅ Reviews search targeting appears to be working correctly!")
        else:
            print("❌ Reviews search targeting needs improvement")
            
    except Exception as e:
        print(f"Error during test: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    test_search_location() 