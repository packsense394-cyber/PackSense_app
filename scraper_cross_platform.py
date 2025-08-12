#!/usr/bin/env python3
"""
Cross-platform scraper module for PackSense
Compatible with Windows, macOS, and mobile devices
"""

import os
import re
import time
import requests
import numpy as np
import pandas as pd
import urllib.parse
import platform
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import math

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys

from collections import Counter, defaultdict

# Import required functions from nlp_utils
from nlp_utils import determine_category
from config import components_list, conditions_list
from nltk.stem import WordNetLemmatizer

#############################################
# Cross-platform compatibility functions
#############################################

def get_chrome_driver_path():
    """Get Chrome driver path based on platform"""
    system = platform.system().lower()
    
    if system == "windows":
        # Windows paths
        possible_paths = [
            "chromedriver.exe",
            "C:\\chromedriver\\chromedriver.exe",
            os.path.join(os.getcwd(), "chromedriver.exe"),
            os.path.join(os.path.expanduser("~"), "chromedriver.exe")
        ]
    elif system == "darwin":  # macOS
        # macOS paths
        possible_paths = [
            "chromedriver",
            "/usr/local/bin/chromedriver",
            "/opt/homebrew/bin/chromedriver",
            os.path.join(os.getcwd(), "chromedriver"),
            os.path.join(os.path.expanduser("~"), "chromedriver")
        ]
    else:  # Linux
        # Linux paths
        possible_paths = [
            "chromedriver",
            "/usr/bin/chromedriver",
            "/usr/local/bin/chromedriver",
            os.path.join(os.getcwd(), "chromedriver"),
            os.path.join(os.path.expanduser("~"), "chromedriver")
        ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    return None

def create_chrome_options_cross_platform(use_headless=True):
    """Create Chrome options compatible with all platforms"""
    options = Options()
    
    if use_headless:
        options.add_argument("--headless")
    
    # Cross-platform options
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Mobile user agent for better compatibility
    mobile_user_agent = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/14.1.2 Mobile/15E148 Safari/604.1"
    )
    options.add_argument(f"user-agent={mobile_user_agent}")
    
    # Additional mobile-friendly options
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-features=VizDisplayCompositor")
    
    return options

def create_webdriver_cross_platform(use_headless=True):
    """Create webdriver compatible with all platforms"""
    try:
        options = create_chrome_options_cross_platform(use_headless)
        driver_path = get_chrome_driver_path()
        
        if driver_path:
            service = Service(executable_path=driver_path)
            driver = webdriver.Chrome(service=service, options=options)
        else:
            # Try without specifying path (let Selenium find it)
            driver = webdriver.Chrome(options=options)
        
        # Set window size for mobile compatibility
        driver.set_window_size(375, 812)  # iPhone X dimensions
        
        return driver
    except Exception as e:
        print(f"Error creating webdriver: {e}")
        # Fallback to basic options
        options = Options()
        if use_headless:
            options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        return webdriver.Chrome(options=options)

#############################################
# Core scraping functions (cross-platform compatible)
#############################################

def click_next_if_available(driver):
    """Click next page button if available - cross-platform compatible"""
    try:
        # Try multiple selectors for better compatibility
        next_selectors = [
            "//ul[contains(@class,'a-pagination')]/li[contains(@class,'a-last')]",
            "//a[contains(@class, 'a-link-normal') and contains(text(), 'Next')]",
            "//span[contains(@class, 's-pagination-next')]",
            "//a[contains(@aria-label, 'Next')]"
        ]
        
        for selector in next_selectors:
            try:
                li = driver.find_element(By.XPATH, selector)
                if "a-disabled" in li.get_attribute("class"):
                    return False
                a = li.find_element(By.TAG_NAME, "a")
                driver.execute_script("arguments[0].click();", a)
                return True
            except NoSuchElementException:
                continue
                
        return False
    except Exception as e:
        print(f"Error clicking next: {e}")
        return False

def amazon_sign_in(driver, email, password, signin_url="https://www.amazon.com/ap/signin"):
    """Sign in to Amazon - cross-platform compatible"""
    try:
        driver.get(signin_url)
        time.sleep(3)
        
        # Wait for email field and enter email
        email_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ap_email"))
        )
        email_field.clear()
        email_field.send_keys(email)
        
        # Click continue
        continue_button = driver.find_element(By.ID, "continue")
        continue_button.click()
        time.sleep(2)
        
        # Wait for password field and enter password
        password_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ap_password"))
        )
        password_field.clear()
        password_field.send_keys(password)
        
        # Click sign in
        signin_button = driver.find_element(By.ID, "signInSubmit")
        signin_button.click()
        time.sleep(5)
        
        # Check if sign in was successful
        if "signin" not in driver.current_url.lower():
            print("Successfully signed in to Amazon")
            return True
        else:
            print("Sign in may have failed")
            return False
            
    except Exception as e:
        print(f"Error during sign in: {e}")
        return False

def ensure_signed_in(driver, email, password, current_url):
    """Ensure user is signed in - cross-platform compatible"""
    try:
        # Check if we're on a sign-in page
        if "signin" in driver.current_url.lower() or "login" in driver.current_url.lower():
            print("Detected sign-in page, attempting to sign in...")
            return amazon_sign_in(driver, email, password)
        
        # Check if we're signed in by looking for account elements
        try:
            account_elements = driver.find_elements(By.XPATH, "//span[contains(@id, 'nav-link-accountList')]")
            if account_elements:
                print("Already signed in to Amazon")
                return True
        except:
            pass
        
        # If we're not signed in, try to sign in
        return amazon_sign_in(driver, email, password)
        
    except Exception as e:
        print(f"Error ensuring sign in: {e}")
        return False

def get_product_name(driver, review_url):
    """Get product name - cross-platform compatible"""
    try:
        # Extract ASIN from URL
        asin_match = re.search(r'/(?:dp|product-reviews)/([A-Z0-9]{10})', review_url)
        if not asin_match:
            return "Unknown_Product"
        
        asin = asin_match.group(1)
        
        # Try to get product name from the page
        try:
            product_title = driver.find_element(By.XPATH, "//h1[contains(@class, 'product-title')]")
            return sanitize_filename(product_title.text.strip())
        except:
            pass
        
        # Fallback to ASIN-based name
        return f"Product_{asin}"
        
    except Exception as e:
        print(f"Error getting product name: {e}")
        return "Unknown_Product"

def download_image(url, filepath):
    """Download image - cross-platform compatible"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        return True
    except Exception as e:
        print(f"Error downloading image {url}: {e}")
        return False

def extract_reviews_from_page(driver, img_folder, seen_src=None):
    """Extract reviews from current page - cross-platform compatible"""
    if seen_src is None:
        seen_src = set()
    
    reviews = []
    
    try:
        # Wait for reviews to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(@data-hook, 'review')]"))
        )
        
        # Find all review containers
        review_containers = driver.find_elements(By.XPATH, "//div[contains(@data-hook, 'review')]")
        
        for container in review_containers:
            try:
                # Extract review text
                try:
                    review_text_elem = container.find_element(By.XPATH, ".//span[contains(@data-hook, 'review-body')]")
                    review_text = review_text_elem.text.strip()
                except:
                    review_text = ""
                
                # Extract rating
                try:
                    rating_elem = container.find_element(By.XPATH, ".//i[contains(@class, 'a-star')]")
                    rating_text = rating_elem.get_attribute("class")
                    rating = re.search(r'a-star-(\d+)', rating_text)
                    rating = int(rating.group(1)) if rating else 0
                except:
                    rating = 0
                
                # Extract title
                try:
                    title_elem = container.find_element(By.XPATH, ".//a[contains(@data-hook, 'review-title')]")
                    title = title_elem.text.strip()
                except:
                    title = ""
                
                # Extract date
                try:
                    date_elem = container.find_element(By.XPATH, ".//span[contains(@data-hook, 'review-date')]")
                    date = date_elem.text.strip()
                except:
                    date = ""
                
                # Extract images
                images = []
                try:
                    img_elements = container.find_elements(By.XPATH, ".//img[contains(@data-hook, 'review-image')]")
                    for img_elem in img_elements:
                        img_src = img_elem.get_attribute("src")
                        if img_src and img_src not in seen_src:
                            seen_src.add(img_src)
                            
                            # Download image
                            img_filename = f"review_img_{len(seen_src)}.jpg"
                            img_path = os.path.join(img_folder, img_filename)
                            
                            if download_image(img_src, img_path):
                                images.append(img_filename)
                except:
                    pass
                
                # Create review dict
                review = {
                    "review_text": review_text,
                    "rating": rating,
                    "title": title,
                    "date": date,
                    "images": images
                }
                
                if review_text:  # Only add if there's actual review text
                    reviews.append(review)
                    
            except Exception as e:
                print(f"Error extracting individual review: {e}")
                continue
        
        return reviews, seen_src
        
    except Exception as e:
        print(f"Error extracting reviews from page: {e}")
        return [], seen_src

def scrape_all_amazon_reviews(review_url, email, password, review_type="all", use_headless=True):
    """Scrape all Amazon reviews - cross-platform compatible"""
    driver = None
    try:
        # Create cross-platform webdriver
        driver = create_webdriver_cross_platform(use_headless)
        
        # Navigate to review page
        driver.get(review_url)
        time.sleep(5)
        
        # Ensure signed in
        if not ensure_signed_in(driver, email, password, review_url):
            print("Failed to sign in to Amazon")
            return None, []
        
        # Get product name
        product_name = get_product_name(driver, review_url)
        product_folder = f"{product_name}_{datetime.now().strftime('%Y-%m-%d')}"
        
        # Create folders
        os.makedirs("static", exist_ok=True)
        os.makedirs(os.path.join("static", product_folder), exist_ok=True)
        img_folder = os.path.join("static", product_folder, "review_images")
        os.makedirs(img_folder, exist_ok=True)
        
        # Scrape reviews
        all_reviews = []
        seen_src = set()
        page_num = 1
        
        while True:
            print(f"Scraping page {page_num}...")
            
            # Extract reviews from current page
            page_reviews, seen_src = extract_reviews_from_page(driver, img_folder, seen_src)
            
            if not page_reviews:
                print("No more reviews found")
                break
            
            all_reviews.extend(page_reviews)
            print(f"Found {len(page_reviews)} reviews on page {page_num}")
            
            # Try to go to next page
            if not click_next_if_available(driver):
                print("No more pages available")
                break
            
            time.sleep(2)
            page_num += 1
            
            # Limit to prevent infinite loops
            if page_num > 50:
                print("Reached maximum page limit")
                break
        
        print(f"Total reviews scraped: {len(all_reviews)}")
        
        # Save reviews to Excel
        if all_reviews:
            df = pd.DataFrame(all_reviews)
            excel_path = os.path.join("static", product_folder, f"{product_folder}_reviews_keywords_and_relationships.xlsx")
            
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Reviews', index=False)
                
                # Add empty sheets for compatibility
                pd.DataFrame().to_excel(writer, sheet_name='All_Keywords', index=False)
                pd.DataFrame().to_excel(writer, sheet_name='Association_Rules', index=False)
        
        return product_folder, all_reviews
        
    except Exception as e:
        print(f"Error scraping reviews: {e}")
        return None, []
    finally:
        if driver:
            driver.quit()

def scrape_recursive_packaging_reviews(review_url, email, password, use_headless=True):
    """Scrape packaging-related reviews recursively - cross-platform compatible"""
    driver = None
    try:
        # Create cross-platform webdriver
        driver = create_webdriver_cross_platform(use_headless)
        
        # Navigate to review page
        driver.get(review_url)
        time.sleep(5)
        
        # Ensure signed in
        if not ensure_signed_in(driver, email, password, review_url):
            print("Failed to sign in to Amazon")
            return None
        
        # Get product name
        product_name = get_product_name(driver, review_url)
        product_folder = f"{product_name}_{datetime.now().strftime('%Y-%m-%d')}"
        
        # Create folders
        os.makedirs("static", exist_ok=True)
        os.makedirs(os.path.join("static", product_folder), exist_ok=True)
        img_folder = os.path.join("static", product_folder, "review_images")
        os.makedirs(img_folder, exist_ok=True)
        
        # Initial review scraping
        print("Scraping initial reviews...")
        initial_reviews = []
        seen_src = set()
        page_num = 1
        
        while page_num <= 5:  # Limit initial scraping
            print(f"Scraping initial page {page_num}...")
            
            page_reviews, seen_src = extract_reviews_from_page(driver, img_folder, seen_src)
            
            if not page_reviews:
                break
            
            initial_reviews.extend(page_reviews)
            
            if not click_next_if_available(driver):
                break
            
            time.sleep(2)
            page_num += 1
        
        print(f"Initial reviews scraped: {len(initial_reviews)}")
        
        # Extract packaging keywords from initial reviews
        all_text = " ".join([r.get("review_text", "") for r in initial_reviews])
        
        # Simple packaging keyword extraction
        packaging_keywords = [
            "packaging", "package", "box", "bottle", "container", "seal", "cap", "lid",
            "broken", "damaged", "leak", "spill", "crushed", "dented", "torn", "ripped",
            "defective", "mold", "expired", "loose", "tight", "secure", "protective"
        ]
        
        found_keywords = []
        for keyword in packaging_keywords:
            if keyword.lower() in all_text.lower():
                found_keywords.append(keyword)
        
        print(f"Found packaging keywords: {found_keywords}")
        
        # Search for reviews with packaging keywords
        packaging_reviews = []
        
        for keyword in found_keywords[:5]:  # Limit to top 5 keywords
            print(f"Searching for reviews with keyword: {keyword}")
            
            # Navigate back to review page
            driver.get(review_url)
            time.sleep(3)
            
            # Try to find search box
            try:
                search_selectors = [
                    "//input[@placeholder='Search reviews']",
                    "//input[@placeholder='Search customer reviews']",
                    "//input[@aria-label='Search reviews']",
                    "//input[@type='text'][not(contains(@id, 'twotabsearch'))]"
                ]
                
                search_box = None
                for selector in search_selectors:
                    try:
                        search_box = driver.find_element(By.XPATH, selector)
                        break
                    except:
                        continue
                
                if search_box:
                    search_box.clear()
                    search_box.send_keys(keyword)
                    search_box.send_keys(Keys.RETURN)
                    time.sleep(3)
                    
                    # Extract reviews from search results
                    keyword_reviews, _ = extract_reviews_from_page(driver, img_folder, seen_src)
                    packaging_reviews.extend(keyword_reviews)
                    
            except Exception as e:
                print(f"Error searching for keyword {keyword}: {e}")
                continue
        
        # Combine all reviews
        all_reviews = initial_reviews + packaging_reviews
        
        # Remove duplicates based on review text
        seen_texts = set()
        unique_reviews = []
        for review in all_reviews:
            text = review.get("review_text", "").strip()
            if text and text not in seen_texts:
                seen_texts.add(text)
                unique_reviews.append(review)
        
        print(f"Total unique reviews: {len(unique_reviews)}")
        
        # Save results
        if unique_reviews:
            df = pd.DataFrame(unique_reviews)
            excel_path = os.path.join("static", product_folder, f"{product_folder}_reviews_keywords_and_relationships.xlsx")
            
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Reviews', index=False)
                pd.DataFrame().to_excel(writer, sheet_name='All_Keywords', index=False)
                pd.DataFrame().to_excel(writer, sheet_name='Association_Rules', index=False)
        
        return {
            'product_folder': product_folder,
            'all_reviews': unique_reviews,
            'initial_reviews': {'reviews': initial_reviews},
            'packaging_reviews': {'reviews': packaging_reviews},
            'total_reviews_extracted': len(unique_reviews),
            'packaging_related_reviews': len(packaging_reviews),
            'packaging_percentage': len(packaging_reviews) / len(unique_reviews) * 100 if unique_reviews else 0,
            'packaging_terms_searched': found_keywords
        }
        
    except Exception as e:
        print(f"Error in recursive packaging review scraping: {e}")
        return None
    finally:
        if driver:
            driver.quit()

def sanitize_filename(filename):
    """Sanitize filename for cross-platform compatibility"""
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Limit length
    if len(filename) > 200:
        filename = filename[:200]
    
    return filename

# Additional utility functions for compatibility
def get_product_main_image_url(driver, review_url):
    """Get product main image URL - cross-platform compatible"""
    try:
        # Extract ASIN and navigate to product page
        asin_match = re.search(r'/(?:dp|product-reviews)/([A-Z0-9]{10})', review_url)
        if not asin_match:
            return None
        
        asin = asin_match.group(1)
        product_url = f"https://www.amazon.com/dp/{asin}"
        
        driver.get(product_url)
        time.sleep(3)
        
        # Try to find main product image
        img_selectors = [
            "//img[@id='landingImage']",
            "//img[contains(@class, 'product-image')]",
            "//img[contains(@alt, 'product')]"
        ]
        
        for selector in img_selectors:
            try:
                img_elem = driver.find_element(By.XPATH, selector)
                return img_elem.get_attribute("src")
            except:
                continue
        
        return None
        
    except Exception as e:
        print(f"Error getting product image: {e}")
        return None

def generate_defect_overlay(product_folder):
    """Generate defect overlay - cross-platform compatible"""
    try:
        # This is a placeholder - implement actual defect overlay generation
        # For now, just create a simple placeholder image
        img = Image.new('RGBA', (400, 400), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        
        # Add some placeholder text
        try:
            # Try to use a default font
            font = ImageFont.load_default()
        except:
            font = None
        
        draw.text((50, 50), "Defect Overlay", fill=(255, 0, 0, 255), font=font)
        
        # Save the image
        overlay_path = os.path.join("static", product_folder, "defects_overlay.png")
        img.save(overlay_path)
        
        return overlay_path
        
    except Exception as e:
        print(f"Error generating defect overlay: {e}")
        return None

def build_defect_coords_map(reviews):
    """Build defect coordinates map - cross-platform compatible"""
    # Placeholder implementation
    return {}

def handle_captcha(driver):
    """Handle CAPTCHA - cross-platform compatible"""
    try:
        # Check for CAPTCHA
        captcha_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'captcha') or contains(text(), 'robot')]")
        
        if captcha_elements:
            print("CAPTCHA detected! Please solve it manually.")
            input("Press Enter after solving the CAPTCHA...")
            return True
        
        return False
        
    except Exception as e:
        print(f"Error handling CAPTCHA: {e}")
        return False

# Additional functions for compatibility with original scraper
def scrape_reviews_for_keywords(driver, review_url, email, password, product_folder, review_type="all", top_n=5):
    """Compatibility function - redirects to cross-platform version"""
    return scrape_all_amazon_reviews(review_url, email, password, review_type, use_headless=False)

def get_product_name_simple(driver):
    """Simple product name extraction"""
    try:
        title_elem = driver.find_element(By.XPATH, "//h1")
        return sanitize_filename(title_elem.text.strip())
    except:
        return "Unknown_Product"
