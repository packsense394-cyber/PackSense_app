import os
import re
import time
import requests
import numpy as np
import pandas as pd
import urllib.parse
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import math

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
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

def click_next_if_available(driver):
    try:
        li = driver.find_element(
            By.XPATH,
            "//ul[contains(@class,'a-pagination')]/li[contains(@class,'a-last')]"
        )
        if "a-disabled" in li.get_attribute("class"):
            return False
        a = li.find_element(By.TAG_NAME, "a")
        driver.execute_script("arguments[0].click();", a)
        return True
    except NoSuchElementException:
        return False

def scrape_reviews_for_keywords(
    driver,
    review_url: str,
    email: str,
    password: str,
    product_folder: str,
    review_type: str = "all",
    top_n: int = 5
) -> list[dict]:
    """
    Assumes `driver` is already signed in on Amazon and still on the product page.
    1) Paginate all unfiltered reviews → collect into all_reviews
    2) From their text extract top_n "condition" keywords
    3) For each keyword: type it into the on‑page filter box → paginate & collect
    Returns the merged list of review‑dicts.
    """
    all_reviews = []
    seen_texts  = set()

    # — build & load base reviews URL —
    m    = re.search(r'/(?:dp|product-reviews)/([A-Z0-9]{10})', review_url)
    asin = m.group(1)
    fv   = {"all":"all_stars","positive":"positive","critical":"critical"}.get(review_type,"all_stars")
    base_url = (
        f"https://www.amazon.com/product-reviews/{asin}/"
        f"?reviewerType=all_reviews&filterByStar={fv}&pageNumber=1"
    )
    driver.get(base_url)
    time.sleep(5)
    ensure_signed_in(driver, email, password, base_url)

    img_folder = os.path.join("static", product_folder, "review_images")
    os.makedirs(img_folder, exist_ok=True)

    # — scrape ALL unfiltered pages —
    seen_src = set()
    while True:
        ensure_signed_in(driver, email, password, base_url)
        prs, seen_src = extract_reviews_from_page(driver, img_folder, seen_src = seen_src)
        if not prs:
            break
        all_reviews.extend(prs)

        # click Next if available
        if not click_next_if_available(driver):
            break
        time.sleep(2)

    # — pick top_n condition‑keywords from all text —
    blob   = " ".join(r["review_text"] for r in all_reviews).lower()
    tokens = re.findall(r"\w+", blob)
    conds  = [t for t in tokens if determine_category(t, components_list, conditions_list) == "condition"]
    lem    = WordNetLemmatizer()
    counts = Counter(lem.lemmatize(w) for w in conds)
    top_k  = [kw for kw,_ in counts.most_common(top_n)]

    # — for each keyword, re‑filter & collect those reviews —
    for kw in top_k:
        # type into filter box
        ensure_signed_in(driver, email, password, base_url)
        box = WebDriverWait(driver,10).until(
            EC.presence_of_element_located((By.XPATH, "//input[contains(@placeholder,'Search customer reviews')]"))
        )
        box.clear()
        box.send_keys(kw)
        box.send_keys(Keys.RETURN)
        time.sleep(5)

        sub_seen = set()
        while True:
            ensure_signed_in(driver, email, password, base_url)
            prs, sub_seen = extract_reviews_from_page(driver, img_folder, seen_src = sub_seen)
            if not prs:
                break
            for r in prs:
                txt = r["review_text"].strip()
                if txt and txt not in seen_texts:
                    seen_texts.add(txt)
                    all_reviews.append(r)

            if not click_next_if_available(driver):
                break
            time.sleep(2)

        # reset back to unfiltered page
        driver.get(base_url)
        time.sleep(5)
        ensure_signed_in(driver, email, password, base_url)

    return all_reviews

def build_full_component_map(image_path, hand_tuned, all_components):
    """
    Returns a coords map where:
     - any component in hand_tuned keeps its exact coords
     - every other component from all_components falls back to the image center
    """
    img = Image.open(image_path)
    w, h = img.size
    center = (w//2, h//2)

    full_map = {}
    for comp in all_components:
        full_map[comp] = hand_tuned.get(comp, center)
    return full_map

def get_product_main_image_url(driver):
    try:
        # primary selector
        img = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "landingImage"))
        )
        return img.get_attribute("src")
    except:
        # fallback to the img inside #imgTagWrapperId
        try:
            img = driver.find_element(By.CSS_SELECTOR, "#imgTagWrapperId img")
            return img.get_attribute("src")
        except:
            return None

def generate_defect_overlay(image_path, defect_pairs, coords_map, output_path):
    """
    Draw numbered X's at each defect location using an inverted
    color sampled from the product image underneath each mark.
    """
    img = Image.open(image_path).convert("RGBA")
    w, h = img.size

    base = img.copy()
    draw = ImageDraw.Draw(base)
    font = ImageFont.load_default()

    # group defect indices by component so we can stack them
    comp_to_idxs = defaultdict(list)
    for idx, (comp, cond) in enumerate(defect_pairs, start=1):
        comp_to_idxs[comp].append(idx)

    X_half = 12            # half‐width of the X
    line_w = 4             # stroke width
    v_step = X_half * 2 + 6  # vertical separation when stacking

    # for sampling the underlying pixel
    sample_rgb = img.convert("RGB")
    pix = sample_rgb.load()

    for comp, idxs in comp_to_idxs.items():
        tx_base, ty_base = coords_map.get(comp, (w//2, h//2))

        for stack_i, defect_idx in enumerate(idxs):
            # fan them out vertically
            ty = ty_base + (stack_i - (len(idxs)-1)/2) * v_step
            tx = tx_base

            # clamp inside image so X never bleeds off
            tx = max(X_half, min(tx, w - X_half))
            ty = max(X_half, min(ty, h - X_half))

            # sample & invert for high contrast
            try:
                r, g, b = pix[tx, ty]
            except:
                r, g, b = (255,255,255)
            color = (255 - r, 255 - g, 255 - b)

            # draw the X
            x0, y0 = tx - X_half, ty - X_half
            x1, y1 = tx + X_half, ty + X_half
            draw.line((x0, y0, x1, y1), fill=color, width=line_w)
            draw.line((x0, y1, x1, y0), fill=color, width=line_w)

            # now draw the number above the X, measured via textbbox
            txt = str(defect_idx)
            bbox = draw.textbbox((0,0), txt, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            num_x = tx - tw//2
            num_y = ty - X_half - th - 2
            draw.text((num_x, num_y), txt, fill=color, font=font)

    base.save(output_path)
   
def build_defect_coords_map(image_path, defect_pairs):
    """
    For each component in defect_pairs, march a ray inward
    to find the first non-white pixel and use that as (tx,ty).
    """
    img = Image.open(image_path).convert("RGBA")
    w, h = img.size
    pix = np.array(img)[..., :3]
    mask = ~np.all(pix > 245, axis=2)      # True where the product is
    center = (w//2, h//2)

    coords = {}
    n = len(defect_pairs)
    for idx, (comp, cond) in enumerate(defect_pairs, start=1):
        angle = 2 * math.pi * (idx - 1) / n
        dx, dy = math.cos(angle), math.sin(angle)

        tx = ty = None
        radius = max(w, h) * 0.5 + 20
        for r in range(int(radius), 0, -1):
            x = int(center[0] + dx * r)
            y = int(center[1] + dy * r)
            if 0 <= x < w and 0 <= y < h and mask[y, x]:
                tx, ty = x, y
                break

        # fallback to center if we never hit the mask
        if tx is None:
            tx, ty = center

        coords[comp] = (tx, ty)

    return coords

def amazon_sign_in(driver, email, password, return_url):
    encoded = urllib.parse.quote(return_url, safe='')
    sign_in_url = (
        "https://www.amazon.com/ap/signin?openid.pape.max_auth_age=3600&openid.return_to="
        f"{encoded}&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.assoc_handle=usflex&openid.mode=checkid_setup&language=en_US&"
        "openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0"
    )
    driver.get(sign_in_url)
    wait = WebDriverWait(driver, 30)

    # ——— Enter email ———
    try:
        email_field = wait.until(EC.element_to_be_clickable((By.ID, "ap_email")))
        driver.execute_script("arguments[0].scrollIntoView(true);", email_field)
        email_field.click()
        email_field.clear()
        email_field.send_keys(email)
    except TimeoutException:
        return False

    driver.find_element(By.ID, "continue").click()

    # ——— Enter password ———
    try:
        pwd_field = wait.until(EC.element_to_be_clickable((By.ID, "ap_password")))
        driver.execute_script("arguments[0].scrollIntoView(true);", pwd_field)
        pwd_field.click()
        pwd_field.clear()
        pwd_field.send_keys(password)
    except TimeoutException:
        return False

    driver.find_element(By.ID, "signInSubmit").click()
    time.sleep(5)

    # ─── guard against a None page_source ───
    page = driver.page_source or ""
    if "Type the characters you see" in page:
        handle_captcha(driver)

    return True

def ensure_signed_in(driver, email, password, return_url):
    """
    If we're ever bounced back to the Amazon login page
    (i.e. the email field is present), just re-run amazon_sign_in.
    """
    try:
        # "ap_email" only exists on the sign‑in page
        driver.find_element(By.ID, "ap_email")
        # re‑sign in and then reload the return_url
        amazon_sign_in(driver, email, password, return_url)
    except NoSuchElementException:
        # not on the sign‑in page → all good
        pass

def get_product_name(driver, asin):
    url = f"https://www.amazon.com/dp/{asin}"
    try:
        driver.get(url)
    except:
        return "Unknown_Product"
    wait = WebDriverWait(driver,20)
    try:
        return wait.until(EC.presence_of_element_located((By.ID,"productTitle"))).text.strip()
    except:
        return "Unknown_Product"

def download_image(image_url, folder, filename):
    try:
        print(f"Attempting to download: {image_url}")
        
        # Add headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.amazon.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'image',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'cross-site',
        }
        
        # Try different URL patterns for Amazon images
        urls_to_try = [image_url]
        
        # If it's an Amazon image URL, try different size variants
        if 'amazon.com' in image_url:
            # Try to get a larger version by modifying the URL
            if '_SY88' in image_url:
                urls_to_try.extend([
                    image_url.replace('_SY88', '_AC_SL1500'),
                    image_url.replace('_SY88', '_AC_SL1000'),
                    image_url.replace('_SY88', '_AC_UL1500')
                ])
            if '_AC_SL1500' in image_url:
                urls_to_try.extend([
                    image_url.replace('_AC_SL1500', '_AC_SL1000'),
                    image_url.replace('_AC_SL1500', '_AC_UL1500')
                ])
            if 'images-na.ssl-images-amazon.com' in image_url:
                urls_to_try.append(image_url.replace('images-na.ssl-images-amazon.com', 'm.media-amazon.com'))
            if 'm.media-amazon.com' in image_url:
                urls_to_try.append(image_url.replace('m.media-amazon.com', 'images-na.ssl-images-amazon.com'))
        
        for url in urls_to_try:
            try:
                print(f"Trying URL: {url}")
                resp = requests.get(url, headers=headers, stream=True, timeout=20)
                print(f"Response status for {url}: {resp.status_code}")
                
                if resp.status_code == 200:
                    # Check if the response is actually an image
                    content_type = resp.headers.get('content-type', '')
                    if not content_type.startswith('image/'):
                        print(f"Not an image: {content_type}")
                        continue
                    
                    os.makedirs(folder, exist_ok=True)
                    path = os.path.join(folder, filename)
                    
                    with open(path, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    # Verify the file was created and has content
                    if os.path.exists(path) and os.path.getsize(path) > 0:
                        print(f"Successfully downloaded: {path}")
                        return path
                    else:
                        print(f"File created but empty or missing: {path}")
                        if os.path.exists(path):
                            os.remove(path)
                elif resp.status_code == 403:
                    print(f"Access forbidden (403) for {url} - Amazon may be blocking")
                elif resp.status_code == 404:
                    print(f"Image not found (404) for {url}")
                else:
                    print(f"HTTP {resp.status_code} for {url}")
                    
            except requests.exceptions.Timeout:
                print(f"Timeout downloading from {url}")
                continue
            except requests.exceptions.ConnectionError:
                print(f"Connection error downloading from {url}")
                continue
            except Exception as e:
                print(f"Exception downloading from {url}: {e}")
                continue
        
        print(f"All download attempts failed for {filename}")
        return None
        
    except Exception as e:
        print(f"Exception in download_image: {e}")
        return None

def extract_reviews_from_page(driver, image_folder, review_offset=0, seen_src=None):
    """
    Scrolls the page, finds all reviews, extracts their text and metadata,
    downloads any new images (avoiding duplicates via seen_src), and returns
    a list of review dicts plus the updated seen_src set.
    """

    # Initialize seen_src on first call
    if seen_src is None:
        seen_src = set()

    # 1) Scroll to bottom to load lazy‐loaded reviews
    SCROLL_PAUSE_TIME = 2
    last_h = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE_TIME)
        new_h = driver.execute_script("return document.body.scrollHeight")
        if new_h == last_h:
            break
        last_h = new_h

    # 2) Wait for the reviews container
    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "cm_cr-review_list"))
        )
    except:
        return [], seen_src

    # 3) Locate all individual review blocks
    review_blocks = driver.find_elements(By.XPATH, "//*[@data-hook='review']")
    if not review_blocks:
        review_blocks = driver.find_elements(
            By.XPATH,
            "//div[@id='cm_cr-review_list']//div[contains(@class,'review')]"
        )
    if not review_blocks:
        return [], seen_src

    reviews_data = []
    for idx, block in enumerate(review_blocks):
        gi = review_offset + idx

        # extract title
        try:
            title = block.find_element(
                By.XPATH, ".//a[@data-hook='review-title']"
            ).text.strip()
        except:
            try:
                title = block.find_element(
                    By.XPATH, ".//span[@data-hook='review-title']"
                ).text.strip()
            except:
                title = ""

        # extract text
        try:
            text = block.find_element(
                By.XPATH, ".//span[@data-hook='review-body']"
            ).text.strip()
        except:
            text = ""

        # extract rating
        rating = ""
        try:
            star_cls = block.find_element(
                By.XPATH, ".//i[contains(@class,'a-icon-star')]"
            ).get_attribute("class")
            m = re.search(r'a-star-(\d+(?:-\d)?)', star_cls)
            if m:
                rating = f"{m.group(1).replace('-', '.')} out of 5"
        except:
            pass

        # extract reviewer name
        try:
            reviewer = block.find_element(
                By.XPATH, ".//span[@class='a-profile-name']"
            ).text.strip()
        except:
            reviewer = "anonymous"

        # extract date
        try:
            date = block.find_element(
                By.XPATH, ".//span[@data-hook='review-date']"
            ).text.strip()
        except:
            date = ""

        # extract "Verified Purchase" flag
        verified = False
        try:
            if block.find_elements(
                By.XPATH, ".//*[contains(text(),'Verified Purchase')]"
            ):
                verified = True
        except:
            pass

        # extract images, deduplicating by URL
        local_images = []

        # Wait for any lazy-loaded images to appear
        try:
            # Scroll the review block into view to trigger lazy loading
            driver.execute_script("arguments[0].scrollIntoView(true);", block)
            time.sleep(1)
            
            # Wait for any images to load
            WebDriverWait(driver, 5).until(
                lambda d: len(block.find_elements(By.TAG_NAME, "img")) > 0
            )
        except:
            pass

        # Try multiple selectors for finding review images
        imgs = []
        
        # Method 1: Look for images with review-image class or data-hook
        imgs = block.find_elements(
            By.XPATH,
            ".//img[contains(@class,'review-image') or contains(@data-hook,'review-image')]"
        )
        print(f"Found {len(imgs)} review images with specific selectors")
        
        # Method 2: Look for images in review-image-tile-section
        if not imgs:
            imgs = block.find_elements(
                By.XPATH,
                ".//div[contains(@class,'review-image-tile-section')]//img"
            )
            print(f"Found {len(imgs)} images in review-image-tile-section")
        
        # Method 3: Look for any img tags with src starting with http
        if not imgs:
            imgs = [
                img for img in block.find_elements(By.TAG_NAME, "img")
                if img.get_attribute("src") and img.get_attribute("src").startswith("http")
            ]
            print(f"Found {len(imgs)} total images with http URLs")

        # Method 4: Look for images in any div that might contain review images
        if not imgs:
            imgs = block.find_elements(
                By.XPATH,
                ".//div[contains(@class,'image') or contains(@class,'photo')]//img"
            )
            print(f"Found {len(imgs)} images in image/photo divs")
        
        # Method 5: Look for any img with amazon.com in src
        if not imgs:
            imgs = [
                img for img in block.find_elements(By.TAG_NAME, "img")
                if img.get_attribute("src") and "amazon.com" in img.get_attribute("src")
            ]
            print(f"Found {len(imgs)} images with amazon.com URLs")
        
        # Method 6: Look for images in any container that might have review images
        if not imgs:
            imgs = block.find_elements(
                By.XPATH,
                ".//div[contains(@class,'review') or contains(@class,'image') or contains(@class,'photo') or contains(@class,'media')]//img"
            )
            print(f"Found {len(imgs)} images in review/image/photo/media containers")
        
        # Method 7: Look for any img with data-src (lazy loading)
        if not imgs:
            imgs = [
                img for img in block.find_elements(By.TAG_NAME, "img")
                if img.get_attribute("data-src") and img.get_attribute("data-src").startswith("http")
            ]
            print(f"Found {len(imgs)} images with data-src (lazy loading)")
        
        # Method 8: Look for any img with srcset (responsive images)
        if not imgs:
            imgs = [
                img for img in block.find_elements(By.TAG_NAME, "img")
                if img.get_attribute("srcset") and "amazon.com" in img.get_attribute("srcset")
            ]
            print(f"Found {len(imgs)} images with srcset")
        
        # Method 9: Look for any img in the entire review block
        if not imgs:
            imgs = block.find_elements(By.TAG_NAME, "img")
            print(f"Found {len(imgs)} total img tags in review block")
        
        # Method 10: Look for background images in CSS
        if not imgs:
            try:
                elements_with_bg = block.find_elements(
                    By.XPATH,
                    ".//*[contains(@style,'background-image')]"
                )
                print(f"Found {len(elements_with_bg)} elements with background images")
                # Extract background image URLs
                for elem in elements_with_bg:
                    style = elem.get_attribute("style")
                    if style and "background-image" in style:
                        bg_match = re.search(r'url\(["\']?([^"\']+)["\']?\)', style)
                        if bg_match and "amazon.com" in bg_match.group(1):
                            print(f"Found background image: {bg_match.group(1)}")
                            # Create a fake img element for download
                            from selenium.webdriver.remote.webelement import WebElement
                            fake_img = WebElement(driver, "fake")
                            fake_img._parent = elem
                            fake_img.get_attribute = lambda attr: bg_match.group(1) if attr == "src" else None
                            imgs.append(fake_img)
            except Exception as e:
                print(f"Error checking background images: {e}")

        print(f"Total images found for review {gi}: {len(imgs)}")
        
        # Ensure image folder exists
        if not os.path.exists(image_folder):
            os.makedirs(image_folder, exist_ok=True)
            print(f"Created image folder: {image_folder}")
        
        for i, img_el in enumerate(imgs):
            src = img_el.get_attribute("src")
            if not src:
                # Try data-src for lazy loaded images
                src = img_el.get_attribute("data-src")
            if not src:
                # Try srcset for responsive images
                srcset = img_el.get_attribute("srcset")
                if srcset and "amazon.com" in srcset:
                    # Extract the first URL from srcset
                    srcset_match = re.search(r'([^\s,]+)', srcset)
                    if srcset_match:
                        src = srcset_match.group(1)
            
            print(f"Image {i}: {src}")
            if not src or src in seen_src:
                print(f"Skipping image {i}: no src or already seen")
                continue
            seen_src.add(src)

            safe = re.sub(r'[^a-zA-Z0-9_]', '', reviewer.replace(" ", "_"))
            fname = f"{safe}_review{gi}_{i}.jpg"
            print(f"Attempting to download as: {fname}")
            if download_image(src, image_folder, fname):
                local_images.append(fname)
                print(f"Successfully added {fname} to local_images")
            else:
                print(f"Failed to download {fname}")

        # Try to find "see all" links for more images
        try:
            see_all_links = block.find_elements(
                By.XPATH,
                ".//a[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'see all') or contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'view all')]"
            )
            
            for see_all in see_all_links:
                try:
                    print(f"Clicking 'see all' link for more images...")
                    driver.execute_script("arguments[0].click();", see_all)
                    
                    # Wait for modal to appear
                    modal = WebDriverWait(driver, 10).until(
                        EC.visibility_of_element_located(
                            (By.XPATH, "//div[contains(@class,'a-popover-inner') or contains(@class,'modal') or contains(@class,'overlay')]")
                        )
                    )
                    time.sleep(2)
                    
                    modal_imgs = modal.find_elements(By.XPATH, ".//img")
                    print(f"Found {len(modal_imgs)} additional images in modal")
                    
                    for j, mimg in enumerate(modal_imgs):
                        msrc = mimg.get_attribute("src")
                        if not msrc:
                            msrc = mimg.get_attribute("data-src")
                        if not msrc or msrc in seen_src:
                            continue
                        seen_src.add(msrc)

                        fname = f"{safe}_review{gi}_modal_{j}.jpg"
                        if download_image(msrc, image_folder, fname):
                            local_images.append(fname)
                            print(f"Successfully added modal image {fname}")

                    # Close the modal
                    try:
                        close_btn = driver.find_element(
                            By.XPATH, "//button[contains(@class,'a-button-close') or contains(@class,'close') or contains(@aria-label,'Close')]"
                        )
                        driver.execute_script("arguments[0].click();", close_btn)
                        time.sleep(1)
                    except:
                        # Try pressing Escape key
                        from selenium.webdriver.common.keys import Keys
                        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                        time.sleep(1)

                except Exception as e:
                    print(f"Error processing 'see all' link: {e}")
                    continue

        except Exception as e:
            print(f"Error looking for 'see all' links: {e}")
            pass

        # assemble the review dict
        reviews_data.append({
            "review_title": title,
            "review_text": text,
            "reviewer_name": reviewer,
            "review_date": date,
            "rating": rating,
            "verified": verified,
            "image_links": ", ".join(local_images)
        })

    return reviews_data, seen_src

def scrape_all_conditions_once(
    review_url: str,
    email: str,
    password: str,
    review_type: str,
    condition_keywords: list[str]
) -> list[dict]:
    """
    1) Launch Chrome once and sign in.
    2) Go to the "all reviews" page.
    3) For each kw in condition_keywords:
         • filter on the page
         • paginate & extract
         • dedupe + collect
    4) Quit & return the merged list.
    """
    opts = Options()
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(
      "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/112.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=opts)
    try:
        # 1) sign in once
        amazon_sign_in(driver, email, password, review_url)

        # 2) navigate to base "all reviews" page
        m   = re.search(r'/(?:dp|product-reviews)/([A-Z0-9]{10})', review_url)
        asin= m.group(1)
        fv  = {"all":"all_stars","positive":"positive","critical":"critical"}\
                 .get(review_type,"all_stars")
        base_url = (
          f"https://www.amazon.com/product-reviews/{asin}/"
          f"?reviewerType=all_reviews&filterByStar={fv}&pageNumber=1"
        )
        driver.get(base_url)
        time.sleep(5)

        ensure_signed_in(driver, email, password, review_url)
        time.sleep(2)

        # prepare your image folder once
        today     = datetime.now().strftime("%Y-%m-%d")
        folder    = os.path.join("static", f"{asin}_{today}")
        img_folder= os.path.join(folder, "review_images")
        os.makedirs(img_folder, exist_ok=True)

        all_reviews = []
        seen_texts  = set()

        # 3) for each condition keyword
        for kw in condition_keywords:
            # a) type into the "Search customer reviews" box
            box = WebDriverWait(driver,10).until(
                EC.presence_of_element_located(
                  (By.XPATH, "//input[contains(@placeholder,'Search customer reviews')]")
                )
            )
            box.clear()
            box.send_keys(kw)
            box.send_keys(Keys.RETURN)
            time.sleep(5)

            # b) paginate & extract
            seen_src = set()
            while True:
                prs, seen_src = extract_reviews_from_page(
                    driver,
                    img_folder,
                    review_offset=len(all_reviews),
                    seen_src=seen_src
                )
                if not prs:
                    break
                for r in prs:
                    txt = r["review_text"].strip()
                    if txt and txt not in seen_texts:
                        seen_texts.add(txt)
                        all_reviews.append(r)

                # click "Next"
                try:
                    nxt = driver.find_element(
                      By.XPATH,
                      "//ul[contains(@class,'a-pagination')]/li[contains(@class,'a-last')]/a"
                    )
                    driver.execute_script("arguments[0].click();", nxt)
                    time.sleep(5)
                except:
                    break

            # c) reset back to page 1
            driver.get(base_url)
            time.sleep(5)

            ensure_signed_in(driver, email, password, review_url)
            time.sleep(2)

        return all_reviews

    finally:
        driver.quit()

def scrape_all_amazon_reviews(review_url, email, password, review_type="all", use_headless=False, filter_keyword: str = None,):
    print(f"Starting scrape_all_amazon_reviews with URL: {review_url}")
    print(f"Review type: {review_type}")
    print(f"Use headless: {use_headless}")
    print(f"Filter keyword: {filter_keyword}")
    
    options = Options()
    if use_headless: options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/112.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=options)
    
    try:
        # 1) extract ASIN from whatever URL they gave us:
        m = re.search(r'/(?:dp|product-reviews)/([A-Z0-9]{10})', review_url)

        if not m:
            print("Could not extract ASIN from URL")
            driver.quit()
            return None, [], None, None
        asin = m.group(1)
        print(f"Extracted ASIN: {asin}")
        
        # 2) build the **product** page URL
        dp_url = f"https://www.amazon.com/dp/{asin}"
        print(f"Product page URL: {dp_url}")

        # 3) sign in *to* the product page so #landingImage is present
        print("Attempting to sign in to Amazon...")
        if not amazon_sign_in(driver, email, password, dp_url):
            print("Failed to sign in to Amazon")
            driver.quit()
            # need to return 4 values: product_name, reviews list, image_path, folder
            return None, [], None, None
        
        print("Successfully signed in to Amazon")
        
        # now we're logged in and on the product page:
        product_name = get_product_name(driver, asin)
        print(f"Product name: {product_name}")

        today = datetime.now().strftime("%Y-%m-%d")
        product_folder = f"{product_name.replace(' ', '_')}_{today}"
        folder = os.path.join("static", product_folder)
        os.makedirs(folder, exist_ok=True)
        print(f"Created product folder: {folder}")

        main_image_url = get_product_main_image_url(driver)
        product_image_path = None
        if main_image_url:
            print(f"Downloading main product image: {main_image_url}")
            product_image_path = download_image(main_image_url, folder, "product.jpg")
            if product_image_path:
                print(f"Successfully downloaded product image: {product_image_path}")
            else:
                print("Failed to download product image")
        else:
            print("No main product image URL found")

        img_folder = os.path.join(folder,"review_images")
        os.makedirs(img_folder,exist_ok=True)
        print(f"Created review images folder: {img_folder}")
        
        if review_type=="all": fv="all_stars"
        elif review_type=="positive": fv="positive"
        elif review_type=="critical": fv="critical"
        else: fv="all_stars"
        
        print(f"Review filter value: {fv}")
        
        # 4) navigate to the reviews page
        driver.get(review_url)
        print(f"Navigated to reviews page: {review_url}")
        
        # 5) apply review type filter if needed
        if review_type != "all":
            print(f"Applying {review_type} filter...")
            try:
                # Look for filter dropdown or buttons
                filter_selectors = [
                    "//select[@id='filter-dropdown']",
                    "//button[contains(text(),'Filter')]",
                    "//a[contains(text(),'Filter')]"
                ]
                
                for selector in filter_selectors:
                    try:
                        filter_element = driver.find_element(By.XPATH, selector)
                        if filter_element.tag_name == "select":
                            # It's a dropdown
                            from selenium.webdriver.support.ui import Select
                            select = Select(filter_element)
                            if review_type == "positive":
                                select.select_by_visible_text("4 stars & up")
                            elif review_type == "critical":
                                select.select_by_visible_text("1, 2, 3 stars")
                        else:
                            # It's a button/link, click it
                            filter_element.click()
                            time.sleep(2)
                            
                            # Look for the specific filter option
                            if review_type == "positive":
                                positive_filter = driver.find_element(By.XPATH, "//a[contains(text(),'4 stars') or contains(text(),'Positive')]")
                                positive_filter.click()
                            elif review_type == "critical":
                                critical_filter = driver.find_element(By.XPATH, "//a[contains(text(),'1 star') or contains(text(),'Critical')]")
                                critical_filter.click()
                        
                        time.sleep(3)
                        print(f"Applied {review_type} filter successfully")
                        break
                    except:
                        continue
                        
            except Exception as e:
                print(f"Error applying filter: {e}")

        # 6) extract reviews with images
        all_reviews = []
        seen_src = set()
        page_num = 1

        while True:
            print(f"Processing page {page_num}...")
            reviews_data, seen_src = extract_reviews_from_page(driver, img_folder, len(all_reviews), seen_src)
            
            if not reviews_data:
                print(f"No reviews found on page {page_num}")
                break

            all_reviews.extend(reviews_data)
            print(f"Extracted {len(reviews_data)} reviews from page {page_num}")
            print(f"Total reviews so far: {len(all_reviews)}")
            
            # Check if we should continue to next page
            if not click_next_if_available(driver):
                print("No more pages available")
                break

            page_num += 1
            time.sleep(2)
        
        print(f"Total reviews extracted: {len(all_reviews)}")
        print(f"Total unique images seen: {len(seen_src)}")
        
        # Check if any images were actually downloaded
        if os.path.exists(img_folder):
            downloaded_images = [f for f in os.listdir(img_folder) if f.endswith(('.jpg', '.jpeg', '.png'))]
            print(f"Images downloaded to {img_folder}: {len(downloaded_images)}")
            for img in downloaded_images:
                print(f"  - {img}")
        else:
            print(f"Image folder {img_folder} does not exist")
        
        return product_name, all_reviews, product_image_path, folder
        
    except Exception as e:
        print(f"Error in scrape_all_amazon_reviews: {e}")
        import traceback
        traceback.print_exc()
        return None, [], None, None
    finally:
        driver.quit()

def handle_captcha(driver):
    wait_time=60
    start=time.time()
    while "Type the characters you see" in driver.page_source:
        if time.time()-start>wait_time:
            driver.refresh()
            start=time.time()
        time.sleep(5)

def sanitize_filename(name):
    return re.sub(r'[^a-zA-Z0-9_]','',name.replace(" ","_")) 

def scrape_recursive_packaging_reviews(
    review_url: str,
    email: str,
    password: str,
    use_headless: bool = False
) -> dict:
    """
    New Review Extraction Strategy:
    1. Extract initial batch of 100 reviews (general extraction)
    2. Use predefined keyword sets to search in review search box
    3. Recursively extract all reviews associated with those keywords
    4. Return comprehensive data for NLP analysis
    """
    print("Starting Recursive Packaging Review Extraction Strategy...")
    
    options = Options()
    if use_headless: 
        options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/112.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=options)
    
    try:
        # Extract ASIN and setup
        m = re.search(r'/(?:dp|product-reviews)/([A-Z0-9]{10})', review_url)
        if not m:
            print("Could not extract ASIN from URL")
            driver.quit()
            return None
        
        asin = m.group(1)
        print(f"Extracted ASIN: {asin}")
        
        # Build product page URL and sign in ONCE
        dp_url = f"https://www.amazon.com/dp/{asin}"
        if not amazon_sign_in(driver, email, password, dp_url):
            print("Failed to sign in to Amazon")
            driver.quit()
            return None
        
        print("Successfully signed in to Amazon - will maintain session")
        
        # Get product info and create folders
        product_name = get_product_name(driver, asin)
        today = datetime.now().strftime("%Y-%m-%d")
        product_folder = f"{product_name.replace(' ', '_')}_{today}"
        folder = os.path.join("static", product_folder)
        os.makedirs(folder, exist_ok=True)
        
        # Download product image
        main_image_url = get_product_main_image_url(driver)
        product_image_path = None
        if main_image_url:
            product_image_path = download_image(main_image_url, folder, "product.jpg")
        
        img_folder = os.path.join(folder, "review_images")
        os.makedirs(img_folder, exist_ok=True)
        
        # Step 1: Extract initial batch of 100 reviews (general extraction)
        print("Step 1: Extracting initial batch of 100 reviews...")
        initial_reviews = []
        seen_src = set()
        
        # Navigate to reviews page
        base_url = f"https://www.amazon.com/product-reviews/{asin}/?reviewerType=all_reviews&filterByStar=all_stars&pageNumber=1"
        driver.get(base_url)
        time.sleep(3)
        
        # Extract initial 100 reviews (no need to re-authenticate)
        page_count = 0
        while len(initial_reviews) < 100:
            page_count += 1
            print(f"Extracting page {page_count}...")
            
            page_reviews, seen_src = extract_reviews_from_page(driver, img_folder, seen_src=seen_src)
            
            if not page_reviews:
                print("No more reviews found")
                break
                
            initial_reviews.extend(page_reviews)
            print(f"Total reviews collected: {len(initial_reviews)}")
            
            if len(initial_reviews) >= 100:
                initial_reviews = initial_reviews[:100]
                break
                
            if not click_next_if_available(driver):
                print("No more pages available")
                break
            time.sleep(2)
        
        print(f"Initial reviews extracted: {len(initial_reviews)}")
        
        # Step 2: Use predefined keyword sets to search in review search box
        print("Step 2: Searching for packaging-related terms...")
        print("Note: Reviews search functionality may require authentication on Amazon")
        packaging_reviews = []
        all_packaging_terms = components_list + conditions_list
        
        # Combine all review text for keyword analysis
        all_text = " ".join([r.get("review_text", "") for r in initial_reviews]).lower()
        
        # Find relevant packaging terms that appear in the reviews
        relevant_terms = []
        for term in all_packaging_terms:
            if term.lower() in all_text:
                relevant_terms.append(term)
        
        print(f"Found {len(relevant_terms)} relevant packaging terms: {relevant_terms[:10]}...")
        
        # Step 3: Recursively extract all reviews associated with those keywords
        print("Step 3: Recursively extracting reviews for each keyword...")
        seen_review_ids = set()
        
        for term in relevant_terms:
            print(f"Searching for term: {term}")
            
            try:
                # Navigate back to reviews page (maintain session)
                driver.get(base_url)
                time.sleep(3)
                
                # Find and use search box - specifically for reviews search
                search_box = None
                search_selectors = [
                    # Most specific selectors for reviews search
                    "//input[@placeholder='Search reviews']",
                    "//input[@placeholder='Search customer reviews']",
                    "//input[@aria-label='Search reviews']",
                    "//input[@aria-label='Search customer reviews']",
                    "//input[@id='search-reviews']",
                    "//input[@name='search-reviews']",
                    # Look for search box within reviews section
                    "//div[contains(@class, 'reviews')]//input[@type='text']",
                    "//div[contains(@class, 'review')]//input[@type='text']",
                    "//section[contains(@class, 'reviews')]//input[@type='text']",
                    "//div[@data-hook='reviews-medley']//input[@type='text']",
                    # Look for search box near review filters
                    "//div[contains(@class, 'filter')]//input[@type='text']",
                    "//div[contains(@class, 'search')]//input[@type='text']",
                    # More generic but still review-focused
                    "//input[contains(@placeholder, 'review')]",
                    "//input[contains(@placeholder, 'customer')]",
                    # Last resort - any text input but exclude main search
                    "//input[@type='text'][not(contains(@id, 'twotabsearch'))][not(contains(@name, 'search'))]"
                ]
                
                for selector in search_selectors:
                    try:
                        search_box = driver.find_element(By.XPATH, selector)
                        print(f"Found search box with selector: {selector}")
                        
                        # Additional verification - make sure it's not the main search
                        if "twotabsearch" in search_box.get_attribute("id") or "main-search" in search_box.get_attribute("class"):
                            print("Skipping main search bar, looking for reviews search...")
                            continue
                            
                        break
                    except NoSuchElementException:
                        continue
                
                if search_box:
                    print(f"Searching for term '{term}' in reviews search bar...")
                    search_box.clear()
                    search_box.send_keys(term)
                    search_box.send_keys(Keys.RETURN)
                    time.sleep(3)
                    
                    # Extract reviews for this term (recursively through all pages)
                    term_reviews = []
                    page_count = 0
                    
                    while True:
                        page_count += 1
                        print(f"  Extracting page {page_count} for term '{term}'...")
                        
                        page_reviews, _ = extract_reviews_from_page(driver, img_folder, seen_src=set())
                        
                        if not page_reviews:
                            break
                        
                        # Add term information and filter duplicates
                        for review in page_reviews:
                            review_id = review.get('review_id', review.get('review_text', ''))
                            if review_id not in seen_review_ids:
                                seen_review_ids.add(review_id)
                                review['search_term'] = term
                                review['is_packaging_related'] = True
                                term_reviews.append(review)
                        
                        # Try to go to next page
                        if not click_next_if_available(driver):
                            break
                        time.sleep(2)
                    
                    packaging_reviews.extend(term_reviews)
                    print(f"  Found {len(term_reviews)} unique reviews for term '{term}'")
                else:
                    print(f"Could not find reviews search box for term '{term}'")
                    print("Reviews search functionality may not be available or requires authentication")
                    print("Trying alternative approach...")
                    
                    # Alternative approach: Filter reviews from initial batch based on keyword presence
                    print(f"  Filtering initial reviews for term '{term}'...")
                    term_reviews = []
                    
                    for review in initial_reviews:
                        review_text = review.get("review_text", "").lower()
                        if term.lower() in review_text:
                            review_id = review.get('review_id', review.get('review_text', ''))
                            if review_id not in seen_review_ids:
                                seen_review_ids.add(review_id)
                                review_copy = review.copy()
                                review_copy['search_term'] = term
                                review_copy['is_packaging_related'] = True
                                term_reviews.append(review_copy)
                    
                    packaging_reviews.extend(term_reviews)
                    print(f"  Found {len(term_reviews)} reviews containing '{term}' from initial batch")
                        
            except Exception as e:
                print(f"Error searching for term '{term}': {e}")
                continue
        
        print(f"Total unique packaging-related reviews found: {len(packaging_reviews)}")
        
        # Prepare results
        results = {
            'product_name': product_name,
            'product_folder': product_folder,
            'product_image_path': product_image_path,
            'initial_reviews': initial_reviews,
            'packaging_reviews': packaging_reviews,
            'packaging_terms_searched': relevant_terms,
            'total_initial_reviews': len(initial_reviews),
            'total_packaging_reviews': len(packaging_reviews),
            'scraping_timestamp': datetime.now().isoformat()
        }
        
        print(f"Recursive packaging review extraction completed successfully!")
        print(f"Initial reviews: {len(initial_reviews)}")
        print(f"Packaging-related reviews: {len(packaging_reviews)}")
        
        return results
        
    except Exception as e:
        print(f"Error in recursive scraping: {e}")
        return None
    finally:
        driver.quit() 