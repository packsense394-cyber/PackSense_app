import os
import re
import time
import zipfile
import requests
import numpy as np
import pandas as pd
import urllib.parse
from datetime import datetime

from flask import Flask, request, render_template, url_for, send_file, jsonify, redirect
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys

from sklearn.feature_extraction.text import TfidfVectorizer
from mlxtend.frequent_patterns import fpgrowth, association_rules

from apscheduler.schedulers.background import BackgroundScheduler
from nltk.sentiment import SentimentIntensityAnalyzer
import atexit

from collections import Counter, defaultdict
import json
import math
from PIL import Image, ImageDraw, ImageFont
from typing import List

# Import our modular functions
from nlp_utils import (
    analyze_sentiment, extract_packaging_keywords, build_component_condition_cooccurrence,
    update_packaging_library, filter_packaging_keywords, map_keyword_to_images,
    build_keyword_sentence_map, build_cooccurrence_data, determine_category,
    get_related_words, summarize_text, analyze_recursive_packaging_reviews,
    get_packaging_related_reviews, get_reviews_by_sentiment, get_packaging_reviews_by_sentiment,
    classify_reviews_as_packaging, get_packaging_classification_summary
)
from scraper import (
    amazon_sign_in, ensure_signed_in, get_product_name, download_image,
    extract_reviews_from_page, scrape_all_amazon_reviews, scrape_reviews_for_keywords,
    get_product_main_image_url, generate_defect_overlay, build_defect_coords_map,
    handle_captcha, sanitize_filename, click_next_if_available, scrape_recursive_packaging_reviews
)
from config import components_list, conditions_list

#############################################
# NLTK Imports and Resource Check
#############################################
import nltk
from nltk.corpus import wordnet as wn
from nltk.stem import WordNetLemmatizer

try:
    nltk.data.find('corpora/wordnet')
except LookupError:
    nltk.download('wordnet')
try:
    nltk.data.find('corpora/omw-1.4')
except LookupError:
    nltk.download('omw-1.4')
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon')
    
sia = SentimentIntensityAnalyzer()

#############################################
# Co-occurrence & TF-IDF Analysis
#############################################
def analyze_reviews_with_tfidf(reviews, threshold=0.05, min_support=0.05):
    vectorizer = TfidfVectorizer(stop_words='english')
    tfidf_matrix = vectorizer.fit_transform(reviews)
    feature_names = vectorizer.get_feature_names_out()
    # top words from first review
    if tfidf_matrix.shape[0]>0:
        scores = tfidf_matrix[0].toarray().flatten()
        idxs = np.argsort(scores)[::-1][:5]
        top_words = [(feature_names[i],scores[i]) for i in idxs]
    else:
        top_words=[]
    # fpgrowth
    transactions = [[1 if s>threshold else 0 for s in row] for row in tfidf_matrix.toarray()]
    df_trans = pd.DataFrame(transactions,columns=feature_names).astype(bool)
    fi = fpgrowth(df_trans, min_support=min_support, use_colnames=True)
    fi['itemsets']=fi['itemsets'].apply(lambda x:list(x))
    if fi.empty:
        rules=pd.DataFrame()
    else:
        rules = association_rules(fi,metric="confidence",min_threshold=0.05)
        rules['antecedents']=rules['antecedents'].apply(lambda x:list(x))
        rules['consequents']=rules['consequents'].apply(lambda x:list(x))
    return top_words, df_trans, fi, rules

#############################################
# Flask App
#############################################
app = Flask(__name__, static_folder="static")
os.makedirs("templates", exist_ok=True)
os.makedirs("static", exist_ok=True)

@app.route("/")
def intro():
    """Introduction page"""
    return render_template("intro.html")

def newest_product_folder(prefix="Tide_Ultra_Oxi_Boost", base="static"):
    """Find the newest product folder matching the prefix"""
    import glob
    candidates = [d for d in glob.glob(os.path.join(base, f"{prefix}*")) if os.path.isdir(d)]
    if not candidates:
        return None
    return os.path.basename(max(candidates, key=os.path.getmtime))

@app.route("/demo")
def demo():
    """Demo mode - shows pre-scraped data with full PackSense dashboard"""
    try:
        # Dynamically find the newest Tide Ultra Oxi Boost folder
        demo_folder = newest_product_folder() or "Tide_Ultra_Oxi_Boost_Liquid_Laundry_Detergent,_84_fl_oz,_59_Loads,_Advanced_Stain_Remover,_Laundry_Detergent_Liquid_with_Extra_Oxi_Power_2025-09-02"
        
        # Check if demo data exists
        demo_path = os.path.join("static", demo_folder)
        if not os.path.exists(demo_path):
            return "Demo data not found. Please ensure demo data is available.", 404
        
        # Load the recursive analysis data
        recursive_analysis_path = os.path.join(demo_path, "recursive_analysis.json")
        if not os.path.exists(recursive_analysis_path):
            return "Demo analysis data not found.", 404
        
        with open(recursive_analysis_path, 'r', encoding='utf-8') as f:
            recursive_data = json.load(f)
        
        # Process the demo data to match the expected template format
        # Try to get all reviews first, fallback to initial_reviews
        reviews = recursive_data.get('all_reviews', [])
        if not reviews:
            reviews = recursive_data.get('initial_reviews', {}).get('reviews', [])
        total_reviews_count = recursive_data.get('total_reviews_extracted', len(reviews))
        
        # Clean and convert review data to proper types
        cleaned_reviews = []
        for review in reviews:
            if isinstance(review, dict):
                cleaned_review = {}
                for key, value in review.items():
                    if key == 'rating':
                        # Convert "5 out of 5" to 5.0
                        if isinstance(value, str) and 'out of' in value:
                            try:
                                cleaned_review[key] = float(value.split(' out of')[0])
                            except:
                                cleaned_review[key] = 5.0
                        else:
                            cleaned_review[key] = float(value) if isinstance(value, (int, float)) else 5.0
                    elif key == 'verified':
                        cleaned_review[key] = bool(value)
                    elif key == 'is_packaging_related':
                        cleaned_review[key] = bool(value)
                    else:
                        cleaned_review[key] = str(value) if value is not None else ""
                cleaned_reviews.append(cleaned_review)
        
        # Load and clean packaging frequency data from JSON
        def to_num(x):
            try:
                return float(str(x).replace(',', '').strip())
            except Exception:
                return 0.0

        # Generate packaging_freq from actual data structure (packaging-only subset)
        def _truthy(x):
            if isinstance(x, bool): 
                return x
            s = str(x or "").strip().lower()
            return s in {"true", "1", "yes", "y"}

        # 1) Use the packaging flag in reviews to compute the KPI (don't infer)
        packaging_reviews = [r for r in cleaned_reviews if _truthy(r.get("is_packaging_related"))]

        # 2) Prefer precomputed packaging_freq from JSON; otherwise derive from keyword_sentence_map
        raw_pf = (recursive_data or {}).get("packaging_freq")
        ksm = (recursive_data or {}).get("keyword_sentence_map")

        if isinstance(raw_pf, dict) and raw_pf:
            packaging_freq = {str(k): to_num(v) for k, v in raw_pf.items()}
        elif isinstance(raw_pf, list) and raw_pf:
            packaging_freq = {}
            for it in raw_pf:
                if isinstance(it, dict):
                    key = str(it.get("keyword") or it.get("term") or it.get("key") or "").strip()
                    val = to_num(it.get("count") or it.get("value") or it.get("freq") or 0)
                    if key: 
                        packaging_freq[key] = packaging_freq.get(key, 0) + val
        elif isinstance(ksm, dict) and ksm:
            packaging_freq = {str(k): len(v or []) for k, v in ksm.items()}
        else:
            # Generate from search_term counts in packaging-related reviews only
            from collections import Counter
            search_terms = Counter()
            
            # Count search_term occurrences in packaging-related reviews only
            for review in packaging_reviews:
                search_term = review.get('search_term', '').strip()
                if search_term:
                    search_terms[search_term] += 1
            
            packaging_freq = dict(search_terms)
        
        # Generate sample component frequency data
        sample_component_freq = {
            'bottle': 35, 'cap': 25, 'label': 20, 'seal': 15, 'handle': 10
        }
        
        # Generate sample condition frequency data
        sample_condition_freq = {
            'good': 180, 'excellent': 120, 'poor': 15, 'damaged': 8, 'broken': 5
        }
        
        # Generate sample enhanced metrics
        sample_enhanced_metrics = {
            'packaging_satisfaction_score': 7.2,
            'defect_rate': 0.15,
            'quality_score': 8.1,
            'customer_satisfaction': 7.8
        }
        
        # Generate sample top keywords
        sample_top_keywords = [
            {'word': 'bottle', 'count': 45, 'sentiment': 'neutral'},
            {'word': 'container', 'count': 32, 'sentiment': 'positive'},
            {'word': 'package', 'count': 28, 'sentiment': 'neutral'},
            {'word': 'box', 'count': 25, 'sentiment': 'positive'},
            {'word': 'cap', 'count': 22, 'sentiment': 'neutral'}
        ]
        
        # Generate sample keyword frequencies (same as packaging_freq for demo)
        sample_keyword_frequencies = packaging_freq
        
        # Generate packaging_terms list for dropdowns
        packaging_terms = sorted(packaging_freq.keys()) if packaging_freq else []
        
        # Build co-occurrence graph with canonical schema
        def build_cooc_graph(recursive_data, packaging_terms=None, min_pair_count=2, top_n_terms=50):
            """
            Canonical schema:
            {
              "nodes": [{"id": "bottle", "label": "bottle", "count": 42}],
              "links": [{"source": "bottle", "target": "leak", "weight": 4}]
            }
            weights are ints 1..5 scaled from raw pair counts
            """
            from collections import defaultdict, Counter
            import itertools, re
            
            def _tok(s):
                return re.findall(r"[A-Za-z][A-Za-z\-]+", (s or "").lower())
            
            # 0) If JSON already provides graph in correct-ish shape, normalize and return.
            raw = (recursive_data or {}).get("cooccurrence_graph")
            if isinstance(raw, dict) and isinstance(raw.get("nodes"), list) and isinstance(raw.get("links"), list):
                nodes = []
                seen = set()
                for n in raw["nodes"]:
                    nid = str(n.get("id") or n.get("name") or n.get("label") or "").strip()
                    if nid and nid not in seen:
                        nodes.append({"id": nid, "label": n.get("label") or nid, "count": int(n.get("count") or n.get("value") or 1)})
                        seen.add(nid)
                links = []
                for e in raw["links"]:
                    s = str(e.get("source") if not isinstance(e.get("source"), dict) else e["source"].get("id")).strip()
                    t = str(e.get("target") if not isinstance(e.get("target"), dict) else e["target"].get("id")).strip()
                    w = e.get("weight") or e.get("value") or 1
                    if s and t and s != t:
                        links.append({"source": s, "target": t, "weight": int(w)})
                if nodes and links:
                    return {"nodes": nodes, "links": links}

            # 1) Build from packaging reviews / keyword maps
            reviews = (recursive_data or {}).get("reviews", [])
            packaging_reviews = [r for r in reviews if _truthy(r.get("is_packaging_related"))]

            # Allowed terms (from packaging_freq) if provided
            if packaging_terms is None:
                pf = (recursive_data or {}).get("packaging_freq") or {}
                if isinstance(pf, dict): packaging_terms = {str(k).lower() for k in pf.keys()}
                else: packaging_terms = set()

            # If keyword_sentence_map exists, use it to seed term counts
            ksm = (recursive_data or {}).get("keyword_sentence_map") or {}
            term_counts = Counter({str(k).lower(): len(v or []) for k, v in (ksm.items() if isinstance(ksm, dict) else [])})

            # Fallback: count terms directly from packaging reviews
            for r in packaging_reviews:
                words = set(_tok(r.get("review_text")))
                for w in words:
                    if not packaging_terms or w in packaging_terms:
                        term_counts[w] += 1

            # Keep top N frequent terms (like local)
            top_terms = set([t for t, _ in term_counts.most_common(top_n_terms)])

            # Build pair counts
            pair_counts = Counter()
            for r in packaging_reviews:
                words = set(w for w in _tok(r.get("review_text")) if w in top_terms)
                for a, b in itertools.combinations(sorted(words), 2):
                    pair_counts[(a, b)] += 1

            # Threshold
            pair_counts = {k: v for k, v in pair_counts.items() if v >= min_pair_count}

            # Scale weights to 1..5
            if pair_counts:
                vals = list(pair_counts.values())
                vmin, vmax = min(vals), max(vals)
                def scale(v):
                    if vmax == vmin: return 3
                    return max(1, min(5, int(round(1 + 4 * (v - vmin) / (vmax - vmin)))))
            else:
                scale = lambda v: 1

            nodes = [{"id": t, "label": t, "count": int(term_counts[t])} for t in sorted(top_terms)]
            links = [{"source": a, "target": b, "weight": scale(c)} for (a, b), c in pair_counts.items()]

            return {"nodes": nodes, "links": links}
        
        # Build co-occurrence graph
        cooc_graph = build_cooc_graph(recursive_data, packaging_terms=set([t.lower() for t in packaging_terms]),
                                      min_pair_count=2, top_n_terms=50)
        
        # Generate sample co-occurrence data with proper structure
        sample_cooccurrence_data = {
            'nodes': [
                {'id': 'bottle', 'group': 1, 'size': 45, 'name': 'bottle'},
                {'id': 'container', 'group': 1, 'size': 32, 'name': 'container'},
                {'id': 'package', 'group': 1, 'size': 28, 'name': 'package'},
                {'id': 'box', 'group': 1, 'size': 25, 'name': 'box'},
                {'id': 'cap', 'group': 1, 'size': 22, 'name': 'cap'},
                {'id': 'lid', 'group': 1, 'size': 18, 'name': 'lid'},
                {'id': 'plastic', 'group': 1, 'size': 15, 'name': 'plastic'},
                {'id': 'seal', 'group': 1, 'size': 12, 'name': 'seal'}
            ],
            'links': [
                {'source': 'bottle', 'target': 'container', 'weight': 15, 'value': 15},
                {'source': 'package', 'target': 'box', 'weight': 12, 'value': 12},
                {'source': 'bottle', 'target': 'cap', 'weight': 18, 'value': 18},
                {'source': 'cap', 'target': 'lid', 'weight': 10, 'value': 10},
                {'source': 'container', 'target': 'plastic', 'weight': 8, 'value': 8},
                {'source': 'bottle', 'target': 'seal', 'weight': 6, 'value': 6}
            ]
        }
        
        # Generate sample keyword image map
        sample_keyword_image_map = {
            'bottle': ['bottle_image1.jpg', 'bottle_image2.jpg'],
            'container': ['container_image1.jpg'],
            'package': ['package_image1.jpg', 'package_image2.jpg']
        }
        
        # Generate sample defect pairs
        sample_defect_pairs = [
            {'defect': 'leak', 'component': 'bottle', 'severity': 'high'},
            {'defect': 'crack', 'component': 'cap', 'severity': 'medium'},
            {'defect': 'broken', 'component': 'seal', 'severity': 'high'},
            {'defect': 'spill', 'component': 'container', 'severity': 'low'}
        ]
        
        # Generate image URLs for defect modal
        product_image_rel = f'{demo_folder}/product.jpg'
        defects_overlay_rel = f'{demo_folder}/defects_overlay.png'
        
        product_image_url = url_for('static', filename=product_image_rel) if os.path.exists(os.path.join('static', product_image_rel)) else None
        defect_overlay_url = url_for('static', filename=defects_overlay_rel) if os.path.exists(os.path.join('static', defects_overlay_rel)) else None
        
        # Helper functions for robust data processing
        def _norm_sent(x):
            return str(x or "").strip().lower()
        
        def _as_bool(x):
            if isinstance(x, bool): 
                return x
            s = _norm_sent(x)
            return s in {"true", "1", "yes", "y"}
        
        # Compute KPI counts from FULL review data (no slicing)
        reviews_full = cleaned_reviews  # FULL LIST – no slicing here
        
        # Debug: Print review counts to understand the data
        print(f"Demo Debug - Total reviews loaded: {len(reviews_full)}")
        print(f"Demo Debug - Total reviews extracted: {total_reviews_count}")
        print(f"Demo Debug - Packaging reviews count: {len(packaging_reviews)}")
        
        def _norm(s): 
            return str(s or "").strip().lower()
        
        pos = sum(1 for r in reviews_full if _norm(r.get("sentiment", "")).startswith("pos"))
        neu = sum(1 for r in reviews_full if _norm(r.get("sentiment", "")).startswith("neu"))
        neg = sum(1 for r in reviews_full if _norm(r.get("sentiment", "")).startswith("neg"))
        pack = len(packaging_reviews)  # Use actual packaging reviews count
        
        # Debug: Print sentiment counts
        print(f"Demo Debug - Sentiment counts: pos={pos}, neu={neu}, neg={neg}, pack={pack}")
        
        # Defects: use sample defect pairs for now
        defects = len(sample_defect_pairs) if sample_defect_pairs else 0
        
        # Create KPI object for template
        kpi = {
            "total": len(reviews_full),
            "positive": pos,
            "neutral": neu,
            "negative": neg,
            "packaging_related": pack,
            "packaging_pct": round((pack / len(reviews_full) * 100), 1) if reviews_full else 0.0,
            "defects": defects,
        }
        
        # Create properly formatted data for the template with all required fields
        demo_data = {
            'product_name': 'Tide Ultra Oxi Boost Liquid Laundry Detergent, 84 fl oz, 59 Loads, Advanced Stain Remover, Laundry Detergent Liquid with Extra Oxi Power',
            'product_description_url': '/demo',
            'total_reviews': int(total_reviews_count),
            'packaging_review_count': int(recursive_data.get('packaging_related_reviews', 0)),
            'packaging_percentage': float(recursive_data.get('packaging_percentage', 0.0)),
            'sentiment_distribution': {
                'positive': pos,
                'negative': neg,
                'neutral': neu
            },
            'reviews': reviews_full,  # Use full reviews for rendering
            'is_demo': True,
            'product_image_url': product_image_url,
            'defect_overlay_url': defect_overlay_url,
            'kpi': kpi,  # Add KPI object for template
            
            # Add all the required template variables with safe defaults
            'review_filters': {
                'all': len(reviews_full),
                'packaging': pack,
                'positive': pos,
                'negative': neg,
                'neutral': neu
            },
            'packaging_freq': packaging_freq,
            'packaging_terms': packaging_terms,
            'cooc_graph': cooc_graph,
            'component_freq': sample_component_freq,
            'condition_freq': sample_condition_freq,
            'keyword_sentence_map': {},
            'defect_coords_map': {},
            'enhanced_metrics': sample_enhanced_metrics,
            'top_keywords': sample_top_keywords,
            'review_timeline': [],
            'defect_summary': {'total_defects': 15, 'critical_defects': 3, 'minor_defects': 12},
            
            # Add the missing variables that the template expects
            'keyword_frequencies': sample_keyword_frequencies,
            'cooccurrence_data': sample_cooccurrence_data,
            'keyword_image_map': sample_keyword_image_map,
            'defect_pairs': sample_defect_pairs
        }
        
        # Render using the demo-specific template with KPI fixes
        return render_template('results_enhanced_demo.html', **demo_data)
        
    except Exception as e:
        print(f"Error loading demo data: {e}")
        # Return a simple demo page if everything fails
        return f"""
        <html>
        <head><title>PackSense Demo</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px; background: #000; color: #fff;">
            <h1>🎯 PackSense Demo Mode</h1>
            <p>Demo mode is working! This shows that PackSense is successfully deployed.</p>
            <p>Error details: {str(e)}</p>
            <a href="/" style="color: #fff; text-decoration: underline;">← Back to Home</a>
        </body>
        </html>
        """

@app.route("/demo-product")
def demo_product():
    """Demo product page for the Tide Ultra Oxi Boost"""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Tide Ultra Oxi Boost - PackSense Demo</title>
        <style>
            body { font-family: Arial, sans-serif; background: #000; color: #fff; margin: 0; padding: 20px; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { text-align: center; margin-bottom: 30px; }
            .product-card { background: #222; padding: 30px; border-radius: 15px; margin-bottom: 30px; }
            .product-image { width: 200px; height: 200px; background: #333; border-radius: 10px; margin: 0 auto 20px; display: flex; align-items: center; justify-content: center; }
            .back-btn { display: inline-block; background: #333; color: #fff; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📦 Tide Ultra Oxi Boost Liquid Laundry Detergent</h1>
                <p>PackSense Demo Product Page</p>
            </div>
            
            <div class="product-card">
                <div class="product-image">
                    <span style="font-size: 3em;">🧴</span>
                </div>
                <h2>Tide Ultra Oxi Boost Liquid Laundry Detergent</h2>
                <p><strong>Size:</strong> 84 fl oz (59 Loads)</p>
                <p><strong>Features:</strong> Advanced Stain Remover, Laundry Detergent Liquid with Extra Oxi Power</p>
                <p><strong>Compatibility:</strong> HE Compatible</p>
                <p><strong>Packaging:</strong> Liquid detergent in secure bottle with easy-pour spout</p>
                
                <h3>Key Benefits:</h3>
                <ul>
                    <li>Advanced stain removal with Oxi power</li>
                    <li>Works in all water temperatures</li>
                    <li>HE washer compatible</li>
                    <li>Fresh, clean scent</li>
                    <li>Concentrated formula - less waste</li>
                </ul>
                
                <h3>Packaging Analysis:</h3>
                <p>Based on customer reviews analyzed by PackSense:</p>
                <ul>
                    <li><strong>68.9%</strong> of reviews mention packaging</li>
                    <li><strong>222</strong> packaging-related reviews out of 322 total</li>
                    <li>Most common packaging keywords: bottle, container, package, box, cap</li>
                    <li>Packaging satisfaction score: 7.2/10</li>
                </ul>
                
                <div style="text-align: center;">
                    <a href="/demo" class="back-btn">← Back to Analysis</a>
                    <a href="/" class="back-btn" style="margin-left: 10px;">← Back to Home</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

@app.route("/analyze", methods=["GET", "POST"])
def index():
    """Main analysis route - now uses Recursive Review Extraction Strategy integrated into existing flow"""
    if request.method == "POST":
        review_url = request.form.get("review_url", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        review_type = request.form.get("review_type", "all").strip()
        use_headless = request.form.get("use_headless", "false") == "true"

        if not review_url or not email or not password:
            return "Missing required fields", 400

        try:
            # Use new recursive scraping function with integrated logic
            print("Starting Recursive Review Extraction Strategy...")
            reviews_data = scrape_recursive_packaging_reviews(
                review_url=review_url,
                email=email,
                password=password,
                use_headless=use_headless
            )
            
            if not reviews_data:
                return "Failed to extract reviews. Please check your credentials and URL.", 400

            # Perform NLP-based analysis
            print("Performing NLP-based analysis...")
            analysis_results = analyze_recursive_packaging_reviews(reviews_data)
            
            # Save analysis results
            product_folder = reviews_data['product_folder']
            analysis_file = os.path.join("static", product_folder, "recursive_analysis.json")
            os.makedirs(os.path.dirname(analysis_file), exist_ok=True)
            
            with open(analysis_file, 'w') as f:
                json.dump(analysis_results, f, indent=2, default=str)
            
            print(f"Recursive analysis completed. Results saved to {analysis_file}")
            
            # Redirect to the product overview page first, then user can navigate to analysis
            return redirect(f"/product_overview/{product_folder}")
            
        except Exception as e:
            print(f"Error in recursive analysis: {e}")
            return f"Analysis failed: {str(e)}", 500

    # GET request - show form
    return render_template("index.html")

@app.route("/analysis/<product_folder>")
def analysis(product_folder):
    """Detailed analysis page with all the review data and features - now supports enhanced recursive data"""
    # Load data from the product folder
    folder = os.path.join("static", product_folder)
    
    # Check if enhanced recursive analysis data exists
    recursive_analysis_file = os.path.join(folder, "recursive_analysis.json")
    if os.path.exists(recursive_analysis_file):
        print("Loading enhanced recursive analysis data...")
        import json as json_module
        with open(recursive_analysis_file, 'r') as f:
            recursive_data = json_module.load(f)
        
        # Use enhanced data
        all_reviews = recursive_data.get('all_reviews', [])
        initial_reviews = recursive_data.get('initial_reviews', {}).get('reviews', [])
        packaging_reviews = recursive_data.get('packaging_reviews', {}).get('reviews', [])
        
        # Enhanced metrics
        total_reviews = recursive_data.get('total_reviews_extracted', 0)
        packaging_related = recursive_data.get('packaging_related_reviews', 0)
        packaging_percentage = recursive_data.get('packaging_percentage', 0)
        
        # Enhanced sentiment breakdown
        sentiment_breakdown = recursive_data.get('sentiment_breakdown', {})
        positive_count = sentiment_breakdown.get('positive', 0)
        negative_count = sentiment_breakdown.get('negative', 0)
        neutral_count = sentiment_breakdown.get('neutral', 0)
        
        # Enhanced packaging terms
        packaging_terms_searched = recursive_data.get('packaging_terms_searched', [])
        
        # Use ALL reviews for comprehensive classification
        reviews = all_reviews
        
        # Process review images to ensure they have proper URLs
        for review in reviews:
            if 'review_images' in review and review['review_images']:
                processed_images = []
                for img in review['review_images']:
                    if isinstance(img, str):
                        # If it's already a URL, keep it
                        if img.startswith('http'):
                            processed_images.append(img)
                        else:
                            # If it's a filename, convert to URL
                            processed_images.append(url_for('static', filename=f"{product_folder}/review_images/{img}"))
                    else:
                        processed_images.append(str(img))
                review['review_images'] = processed_images
        
        print(f"Enhanced data loaded: {total_reviews} total reviews, {packaging_related} packaging-related")
        
    else:
        # Fallback to original logic
        print("Loading original analysis data...")
        excel_path = os.path.join(folder, f"{product_folder}_reviews_keywords_and_relationships.xlsx")
        if os.path.exists(excel_path):
            reviews_df = pd.read_excel(excel_path, sheet_name='Reviews')
            reviews = reviews_df.to_dict('records')
        else:
            reviews = []
        
        # Calculate metrics
        total_reviews = len(reviews)
        positive_count = sum(1 for r in reviews if analyze_sentiment(str(r.get("review_text", ""))) == "positive")
        negative_count = sum(1 for r in reviews if analyze_sentiment(str(r.get("review_text", ""))) == "negative")
        neutral_count = total_reviews - positive_count - negative_count
        
        # Process review images to ensure they have proper URLs
        for review in reviews:
            if 'review_images' in review and review['review_images']:
                processed_images = []
                for img in review['review_images']:
                    if isinstance(img, str):
                        # If it's already a URL, keep it
                        if img.startswith('http'):
                            processed_images.append(img)
                        else:
                            # If it's a filename, convert to URL
                            processed_images.append(url_for('static', filename=f"{product_folder}/review_images/{img}"))
                    else:
                        processed_images.append(str(img))
                review['review_images'] = processed_images
        
        # Default values for enhanced features
        packaging_related = 0
        packaging_percentage = 0
        packaging_terms_searched = []
    
    # Load other data
    base_image_url = url_for('static', filename=f"{product_folder}/product.jpg")
    excel_url = url_for('static', filename=f"{product_folder}/{product_folder}_reviews_keywords_and_relationships.xlsx")
    lib_url = url_for('static', filename="packaging_library.xlsx")
    
    # Load image files
    img_folder = os.path.join(folder, "review_images")
    image_files = []
    unique_images = set()  # Track unique image files
    
    if os.path.exists(img_folder):
        for fname in os.listdir(img_folder):
            if fname.lower().endswith(('.jpg', '.png', '.gif')):
                # Get the real file path (resolve symbolic links)
                real_path = os.path.realpath(os.path.join(img_folder, fname))
                # Use the real filename as the key for deduplication
                real_filename = os.path.basename(real_path)
                
                # Only add if we haven't seen this real file before
                if real_filename not in unique_images:
                    unique_images.add(real_filename)
                    image_files.append(fname)
    
    # Load packaging data (enhanced if available)
    if os.path.exists(recursive_analysis_file):
        # Use enhanced packaging terms
        packaging_keywords = packaging_terms_searched
        packaging_keywords_flat = packaging_terms_searched
        dropdown_data_flat = packaging_terms_searched + ['packaging', 'broken', 'leak', 'damaged', 'defective']
        
        # For enhanced data, we need to build the packaging frequency manually
        packaging_freq = {}
        for kw in packaging_keywords_flat:
            count = sum(1 for r in reviews if kw.lower() in str(r.get("review_text", "")).lower())
            if count > 0:
                packaging_freq[kw] = count
    else:
        # Original packaging data loading logic
        try:
            import ast
            excel_path = os.path.join(folder, f"{product_folder}_reviews_keywords_and_relationships.xlsx")
            fi_df = pd.read_excel(excel_path, sheet_name='All_Keywords')
            if 'itemsets' in fi_df.columns:
                # Handle string representations of lists from Excel
                packaging_keywords_raw = fi_df['itemsets'].tolist()
                packaging_keywords = []
                for item in packaging_keywords_raw:
                    if isinstance(item, str):
                        try:
                            # Use ast.literal_eval to safely parse the string representation
                            parsed_item = ast.literal_eval(item)
                            if isinstance(parsed_item, list):
                                for kw in parsed_item:
                                    if isinstance(kw, str) and len(kw) > 1:
                                        packaging_keywords.append(kw)
                        except (ValueError, SyntaxError):
                            # Fallback to manual parsing if ast.literal_eval fails
                            item = item.strip('"').strip("'").strip('[]')
                            if item:
                                items = [kw.strip().strip("'\"") for kw in item.split(',') if kw.strip()]
                                for kw in items:
                                    if len(kw) > 1 and kw.replace(' ', '').isalnum():
                                        packaging_keywords.append(kw)
                    elif isinstance(item, list):
                        for kw in item:
                            if isinstance(kw, str) and len(kw) > 1:
                                packaging_keywords.append(kw)
            else:
                packaging_keywords = []
        except:
            packaging_keywords = []
        
        # Convert to flat lists
        flat_pkg = packaging_keywords
        packaging_keywords_flat = flat_pkg
        dropdown_data_flat = sorted(set(['packaging', 'broken', 'leak', 'damaged', 'defective'] + flat_pkg))
        
        # Build packaging frequency
        packaging_freq = {}
        for kw in packaging_keywords_flat:
            count = sum(1 for r in reviews if kw.lower() in str(r.get("review_text", "")).lower())
            if count > 0:
                packaging_freq[kw] = count
    
    # Build keyword maps - will be updated after co-occurrence data is built for enhanced analysis
    if os.path.exists(recursive_analysis_file):
        # For enhanced data, we'll build keyword maps after co-occurrence data
        unique_keys = set(packaging_keywords_flat)  # Temporary, will be updated
        kw_img = {}
        kw_img_trans = {}
        kw_sent = {}
    else:
        unique_keys = set(packaging_keywords_flat)
        print(f"Building keyword maps for {len(unique_keys)} unique keys: {list(unique_keys)[:10]}")
        
        kw_img = map_keyword_to_images(reviews, unique_keys)
        print(f"Raw keyword image map has {len(kw_img)} keywords")
        if kw_img:
            print(f"Sample raw keyword image map: {list(kw_img.items())[:3]}")
        
        # Fix image paths to ensure they exist
        kw_img_trans = {}
        for kw, imgs in kw_img.items():
            valid_images = []
            for img_filename in imgs:
                if img_filename.strip():
                    # Check if the image file actually exists
                    img_path = os.path.join(folder, "review_images", img_filename.strip())
                    if os.path.exists(img_path):
                        valid_images.append(
                            url_for('static', filename=f"{product_folder}/review_images/{img_filename.strip()}")
                        )
            if valid_images:
                kw_img_trans[kw] = valid_images
        
        print(f"Built keyword image map with {len(kw_img_trans)} keywords")
        if kw_img_trans:
            print(f"Sample keyword image map keys: {list(kw_img_trans.keys())[:5]}")
            for key in list(kw_img_trans.keys())[:3]:
                print(f"  {key}: {len(kw_img_trans[key])} images")
        else:
            print("No keyword image map data found")
        
        # Build keyword sentence map
        kw_sent = build_keyword_sentence_map(reviews, unique_keys)
        print(f"Built keyword sentence map with {len(kw_sent)} keywords")
        if kw_sent:
            print(f"Sample keyword sentence map keys: {list(kw_sent.keys())[:5]}")
            for key in list(kw_sent.keys())[:3]:
                print(f"  {key}: {len(kw_sent[key])} sentences")
        else:
            print("No keyword sentence map data found")
    
    # Load cooccurrence data
    if os.path.exists(recursive_analysis_file):
        # For enhanced data, build cooccurrence from actual words found in reviews
        print("Building co-occurrence data from words found in reviews...")
        cooccurrence_data = {}
        
        # Extract all packaging-related words from reviews
        from collections import Counter
        import re
        
        # Define packaging-related keywords to look for
        packaging_keywords_to_find = [
            'bottle', 'package', 'packaging', 'container', 'box', 'bag', 'can', 'jar', 'tube', 'pouch',
            'leak', 'leaking', 'leaked', 'broken', 'break', 'broke', 'damage', 'damaged', 'crack', 'cracked',
            'seal', 'sealed', 'cap', 'lid', 'top', 'cover', 'plastic', 'glass', 'metal', 'paper', 'cardboard',
            'label', 'labeled', 'wrapped', 'wrap', 'protective', 'protection', 'secure', 'secured',
            'spill', 'spilled', 'mess', 'dirty', 'clean', 'hygienic', 'safe', 'unsafe', 'dangerous',
            'tin', 'aluminum', 'steel', 'foil', 'bubble', 'cushion', 'padding', 'tape', 'adhesive',
            'transparent', 'clear', 'opaque', 'color', 'colored', 'design', 'shape', 'size', 'large', 'small'
        ]
        
        # Find all packaging words that actually appear in reviews
        found_packaging_words = set()
        word_frequency = Counter()
        
        for review in reviews:
            review_text = str(review.get("review_text", "")).lower()
            # Find all packaging keywords in this review
            for keyword in packaging_keywords_to_find:
                if keyword in review_text:
                    found_packaging_words.add(keyword)
                    word_frequency[keyword] += 1
        
        # Only include words that appear at least 2 times
        frequent_packaging_words = [word for word, count in word_frequency.items() if count >= 2]
        
        print(f"Found {len(found_packaging_words)} packaging words in reviews")
        print(f"Words appearing 2+ times: {frequent_packaging_words}")
        
        # Build co-occurrence matrix from actual words found in reviews
        if frequent_packaging_words:
            print(f"Building co-occurrence matrix for {len(frequent_packaging_words)} frequently occurring terms")
            
            for i, term1 in enumerate(frequent_packaging_words):
                for j, term2 in enumerate(frequent_packaging_words):
                    if i != j:
                        # Count co-occurrences in reviews
                        cooccurrence_count = 0
                        for review in reviews:
                            review_text = str(review.get("review_text", "")).lower()
                            if term1 in review_text and term2 in review_text:
                                cooccurrence_count += 1
                        
                        if cooccurrence_count > 0:
                            if term1 not in cooccurrence_data:
                                cooccurrence_data[term1] = {}
                            cooccurrence_data[term1][term2] = cooccurrence_count
            
            print(f"Built co-occurrence data with {len(cooccurrence_data)} terms")
            if cooccurrence_data:
                print("Sample co-occurrence relationships:")
                for term1, connections in list(cooccurrence_data.items())[:3]:
                    for term2, count in list(connections.items())[:3]:
                        print(f"  {term1} ↔ {term2}: {count} times")
        else:
            print("No frequently occurring packaging words found")
            cooccurrence_data = {}
        
        # Update unique_keys to match the words actually found in co-occurrence network
        if cooccurrence_data:
            unique_keys = set(cooccurrence_data.keys())
            print(f"Updated unique_keys to match co-occurrence network: {list(unique_keys)[:10]}")
            
            # Rebuild keyword maps with the correct keys
            kw_img = map_keyword_to_images(reviews, unique_keys)
            kw_sent = build_keyword_sentence_map(reviews, unique_keys)
            
            # Fix image paths to ensure they exist
            kw_img_trans = {}
            for kw, imgs in kw_img.items():
                valid_images = []
                for img_filename in imgs:
                    if img_filename.strip():
                        # Check if the image file actually exists
                        img_path = os.path.join(folder, "review_images", img_filename.strip())
                        if os.path.exists(img_path):
                            valid_images.append(
                                url_for('static', filename=f"{product_folder}/review_images/{img_filename.strip()}")
                            )
                if valid_images:
                    kw_img_trans[kw] = valid_images
            
            print(f"Rebuilt keyword maps with {len(kw_img_trans)} image keywords and {len(kw_sent)} sentence keywords")
        else:
            print("No co-occurrence data found, using original unique_keys")
    else:
        try:
            excel_path = os.path.join(folder, f"{product_folder}_reviews_keywords_and_relationships.xlsx")
            rules_df = pd.read_excel(excel_path, sheet_name='Association_Rules')
            cooccurrence_data = build_cooccurrence_data(fi_df) if not fi_df.empty else {}
        except:
            cooccurrence_data = {}
    
    # Build defect analysis
    if os.path.exists(recursive_analysis_file):
        # For enhanced data, build defect pairs from packaging terms
        print("Building defect analysis for enhanced data...")
        defect_pairs = []
        
        # Create a more flexible matching system
        for term in packaging_terms_searched:
            term_lower = term.lower()
            
            # Check if this term is a condition
            is_condition = any(cond.lower() in term_lower or term_lower in cond.lower() 
                             for cond in conditions_list)
            
            if is_condition:
                # This is a condition term, find component terms it co-occurs with
                for review in reviews:
                    review_text = str(review.get("review_text", "")).lower()
                    if term_lower in review_text:
                        for comp in components_list:
                            comp_lower = comp.lower()
                            if comp_lower in review_text:
                                defect_pairs.append((comp, term))
        
        defect_pairs = list(set(defect_pairs))  # Remove duplicates
        print(f"Found {len(defect_pairs)} defect pairs")
        
        # If no defect pairs found with the above logic, try a more general approach
        if not defect_pairs:
            print("No defect pairs found with strict matching, trying general approach...")
            for review in reviews:
                review_text = str(review.get("review_text", "")).lower()
                review_components = [comp for comp in components_list if comp.lower() in review_text]
                review_conditions = [cond for cond in conditions_list if cond.lower() in review_text]
                
                for comp in review_components:
                    for cond in review_conditions:
                        defect_pairs.append((comp, cond))
            
            defect_pairs = list(set(defect_pairs))  # Remove duplicates
            print(f"Found {len(defect_pairs)} defect pairs with general approach")
    else:
        # Original defect analysis logic
        try:
            comp = pd.DataFrame([{"Keyword": w, "Category": "component"} for w in components_list])
            cond = pd.DataFrame([{"Keyword": w, "Category": "condition"} for w in conditions_list])
            packaging_library_terms = pd.concat([comp, cond]).dropna().astype(str).tolist()
        except:
            packaging_library_terms = []
        
        df_co = build_component_condition_cooccurrence(reviews, pd.concat([comp, cond], ignore_index=True))
        defect_pairs = [
            (comp, cond)
            for cond in df_co.index
            for comp in df_co.columns
            if df_co.loc[cond, comp] > 0
        ]
    
    # Generate defect overlay image if we have defect pairs and a product image
    defect_image_url = url_for('static', filename=f"{product_folder}/defects_overlay.png")
    product_image_path = os.path.join(folder, "product.jpg")
    
    if defect_pairs and os.path.exists(product_image_path):
        print(f"Generating defect overlay for {len(defect_pairs)} defect pairs...")
        try:
            # Build coordinates map for defect locations
            coords_map = build_defect_coords_map(product_image_path, defect_pairs)
            
            # Generate the defect overlay
            overlay_path = os.path.join(folder, "defects_overlay.png")
            generate_defect_overlay(product_image_path, defect_pairs, coords_map, overlay_path)
            
            print(f"Defect overlay generated successfully: {overlay_path}")
        except Exception as e:
            print(f"Error generating defect overlay: {e}")
            # Fallback to default defect image URL
            defect_image_url = url_for('static', filename=f"{product_folder}/defects_overlay.png")
    else:
        print("No defect pairs found or product image missing, skipping defect overlay generation")
        defect_image_url = url_for('static', filename=f"{product_folder}/defects_overlay.png")
    
    # Enhanced metrics for template
    enhanced_metrics = {
        'total_reviews': total_reviews,
        'packaging_related': packaging_related,
        'packaging_percentage': packaging_percentage,
        'positive_count': positive_count,
        'negative_count': negative_count,
        'neutral_count': neutral_count,
        'has_enhanced_data': os.path.exists(recursive_analysis_file)
    }
    
    # Build product description URL - point to our own product overview page
    product_description_url = f"/product_overview/{product_folder}"
    
    # Apply comprehensive packaging classification algorithm to ALL reviews
    print("Applying comprehensive packaging classification algorithm...")
    all_reviews = classify_reviews_as_packaging(reviews, components_list, conditions_list)
    
    # Get classification summary for all reviews
    classification_summary = get_packaging_classification_summary(all_reviews)
    print(f"Classification Summary: {classification_summary}")
    
    # Update the reviews variable to use the classified reviews
    reviews = all_reviews
    
    # Add sentiment analysis to each review and ensure rating is an integer
    for review in reviews:
        review['sentiment'] = analyze_sentiment(str(review.get("review_text", "")))
        
        # Ensure rating is properly processed
        if 'rating' in review and review['rating'] is not None:
            try:
                if isinstance(review['rating'], str):
                    # Try to extract numeric rating from string
                    import re
                    rating_match = re.search(r'(\d+(?:\.\d+)?)', str(review['rating']))
                    if rating_match:
                        rating_value = float(rating_match.group(1))
                        # Ensure rating is between 0 and 5
                        if 0 <= rating_value <= 5:
                            review['rating'] = rating_value
                        else:
                            review['rating'] = None
                    else:
                        review['rating'] = None
                elif isinstance(review['rating'], (int, float)):
                    # Ensure rating is between 0 and 5
                    if 0 <= review['rating'] <= 5:
                        review['rating'] = float(review['rating'])
                    else:
                        review['rating'] = None
                else:
                    review['rating'] = None
            except (ValueError, TypeError):
                review['rating'] = None
        else:
            review['rating'] = None
    
    # Prepare review filtering data for sidebar using classification summary
    review_filters = {
        'all_reviews': classification_summary['total_reviews'],
        'packaging_reviews': classification_summary['packaging_reviews'],
        'positive_reviews': len([r for r in reviews if r.get('sentiment') == "positive"]),
        'neutral_reviews': len([r for r in reviews if r.get('sentiment') == "neutral"]),
        'negative_reviews': len([r for r in reviews if r.get('sentiment') == "negative"])
    }
    
    # Update enhanced metrics with comprehensive classification results
    enhanced_metrics['total_reviews'] = classification_summary['total_reviews']
    enhanced_metrics['packaging_related'] = classification_summary['packaging_reviews']
    enhanced_metrics['packaging_percentage'] = classification_summary['packaging_percentage']
    enhanced_metrics['classification_confidence'] = classification_summary['avg_packaging_confidence']
    enhanced_metrics['high_confidence_packaging'] = classification_summary['high_confidence_packaging']
    
    # Update main template variables to match classification results
    total_reviews = classification_summary['total_reviews']
    packaging_related = classification_summary['packaging_reviews']
    packaging_percentage = classification_summary['packaging_percentage']
    
    # Recalculate sentiment counts from classified reviews
    positive_count = len([r for r in reviews if r.get('sentiment') == "positive"])
    negative_count = len([r for r in reviews if r.get('sentiment') == "negative"])
    neutral_count = len([r for r in reviews if r.get('sentiment') == "neutral"])
    
    print(f"Comprehensive packaging classification: {classification_summary['packaging_reviews']} packaging-related out of {len(reviews)} total reviews")
    print(f"Average confidence: {classification_summary['avg_packaging_confidence']:.2f}")
    print(f"High confidence packaging reviews: {classification_summary['high_confidence_packaging']}")
    
    # Debug: Print what's being passed to template
    print(f"DEBUG: Passing to template - keyword_sentence_map keys: {list(kw_sent.keys()) if kw_sent else 'None'}")
    print(f"DEBUG: Passing to template - keyword_image_map keys: {list(kw_img_trans.keys()) if kw_img_trans else 'None'}")
    print(f"DEBUG: Passing to template - cooccurrence_data keys: {list(cooccurrence_data.keys()) if cooccurrence_data else 'None'}")
    
    # Clean the data to avoid JSON parsing errors
    def clean_for_json(obj):
        if isinstance(obj, dict):
            return {k: clean_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [clean_for_json(item) for item in obj]
        elif isinstance(obj, str):
            # Remove or replace problematic characters that break JSON
            cleaned = obj
            # Replace control characters
            for char in ['\n', '\r', '\t', '\b', '\f']:
                cleaned = cleaned.replace(char, ' ')
            # Replace quotes that could break JSON
            cleaned = cleaned.replace('"', "'").replace('\\', '/')
            # Remove any other control characters
            cleaned = ''.join(char for char in cleaned if ord(char) >= 32 or char in ['\t', '\n', '\r'])
            return cleaned
        else:
            return obj
    
    # Clean the data to ensure JSON compatibility
    def clean_text_for_json(text):
        if not isinstance(text, str):
            return str(text)
        # Remove or replace problematic characters
        cleaned = text
        # Replace control characters with spaces
        for char in ['\n', '\r', '\t', '\b', '\f']:
            cleaned = cleaned.replace(char, ' ')
        # Replace quotes that could break JSON
        cleaned = cleaned.replace('"', "'").replace('\\', '/')
        # Remove any other control characters
        cleaned = ''.join(char for char in cleaned if ord(char) >= 32 or char in ['\t', '\n', '\r'])
        # Remove multiple spaces
        cleaned = ' '.join(cleaned.split())
        return cleaned
    
    def clean_data_for_json(obj):
        if isinstance(obj, dict):
            return {k: clean_data_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [clean_data_for_json(item) for item in obj]
        elif isinstance(obj, str):
            return clean_text_for_json(obj)
        else:
            return obj
    
    # Clean the data
    cleaned_reviews = clean_data_for_json(reviews)
    cleaned_kw_sent = clean_data_for_json(kw_sent)
    cleaned_kw_img = clean_data_for_json(kw_img_trans)
    
    print(f"DEBUG: Using original data - kw_sent keys: {list(kw_sent.keys()) if kw_sent else 'None'}")
    
    # Test JSON serialization
    try:
        test_json = json.dumps(kw_sent)
        print(f"DEBUG: JSON validation passed - length: {len(test_json)}")
    except Exception as e:
        print(f"DEBUG: JSON validation failed: {e}")
        # If JSON fails, create a simplified version
        simplified_kw_sent = {}
        for key, value in kw_sent.items():
            try:
                # Only keep simple string values
                if isinstance(value, list):
                    simplified_values = []
                    for item in value:
                        if isinstance(item, dict) and 'sentence' in item:
                            simplified_values.append(item['sentence'][:200])  # Truncate long sentences
                        elif isinstance(item, str):
                            simplified_values.append(item[:200])
                    simplified_kw_sent[key] = simplified_values
            except:
                continue
        cleaned_kw_sent = simplified_kw_sent
        print(f"DEBUG: Using simplified data - keys: {list(simplified_kw_sent.keys())}")
    
    # Calculate keyword frequencies for word cloud
    keyword_frequencies = {}
    if reviews:
        from collections import Counter
        import re
        
        # Combine all review text
        all_text = ' '.join([str(review.get('review_text', '')) for review in reviews])
        
        # Extract packaging-related keywords and count their occurrences
        packaging_terms = components_list + conditions_list
        
        for term in packaging_terms:
            # Use case-insensitive regex to find all occurrences
            pattern = r'\b' + re.escape(term.lower()) + r'\b'
            count = len(re.findall(pattern, all_text.lower()))
            if count > 0:
                keyword_frequencies[term] = count
        
        # Sort by frequency (highest first)
        keyword_frequencies = dict(sorted(keyword_frequencies.items(), key=lambda x: x[1], reverse=True))
    

    
    return render_template(
        "results_enhanced.html",
        product_name=product_folder.replace('_', ' ').replace('-', ' '),
        packaging_keywords=packaging_keywords_flat,
        packaging_dropdown_data=dropdown_data_flat,
        image_files=image_files,
        reviews=cleaned_reviews,
        excel_file=excel_url,
        cooccurrence_data=cooccurrence_data,
        keyword_image_map=cleaned_kw_img,
        product_folder=product_folder,
        packaging_library_url=lib_url,
        keyword_sentence_map=cleaned_kw_sent,
        defect_image_url=defect_image_url,
        defect_pairs=defect_pairs,
        total_reviews=total_reviews,
        positive_count=positive_count,
        neutral_count=neutral_count,
        negative_count=negative_count,
        base_image_url=base_image_url,
        packaging_freq=packaging_freq,
        enhanced_metrics=enhanced_metrics,  # Pass enhanced metrics to template
        product_description_url=product_description_url,  # Product description URL
        review_filters=review_filters,  # Review filtering data for sidebar
        keyword_frequencies=keyword_frequencies,  # Keyword frequencies for word cloud
    )

@app.route("/product_overview/<product_folder>")
def product_overview(product_folder):
    """Product overview page showing product details and summary"""
    # Load data from the product folder
    folder = os.path.join("static", product_folder)
    
    # Check if enhanced recursive analysis data exists
    recursive_analysis_file = os.path.join(folder, "recursive_analysis.json")
    if os.path.exists(recursive_analysis_file):
        with open(recursive_analysis_file, 'r') as f:
            recursive_data = json.load(f)
        
        # Use enhanced data
        all_reviews = recursive_data.get('all_reviews', [])
        total_reviews = recursive_data.get('total_reviews_extracted', 0)
        packaging_related = recursive_data.get('packaging_related_reviews', 0)
        packaging_percentage = recursive_data.get('packaging_percentage', 0)
        
        # Enhanced sentiment breakdown
        sentiment_breakdown = recursive_data.get('sentiment_breakdown', {})
        positive_count = sentiment_breakdown.get('positive', 0)
        negative_count = sentiment_breakdown.get('negative', 0)
        neutral_count = sentiment_breakdown.get('neutral', 0)
    else:
        # Fallback to original logic
        excel_path = os.path.join(folder, f"{product_folder}_reviews_keywords_and_relationships.xlsx")
        if os.path.exists(excel_path):
            reviews_df = pd.read_excel(excel_path, sheet_name='Reviews')
            all_reviews = reviews_df.to_dict('records')
        else:
            all_reviews = []
        
        # Calculate metrics
        total_reviews = len(all_reviews)
        positive_count = sum(1 for r in all_reviews if analyze_sentiment(str(r.get("review_text", ""))) == "positive")
        negative_count = sum(1 for r in all_reviews if analyze_sentiment(str(r.get("review_text", ""))) == "negative")
        neutral_count = total_reviews - positive_count - negative_count
        
        # Default values for enhanced features
        packaging_related = 0
        packaging_percentage = 0
    
    # Apply the same comprehensive classification algorithm as the analysis page
    # to ensure metrics consistency between overview and analysis pages
    if all_reviews:
        print("Applying comprehensive packaging classification for product overview...")
        classified_reviews = classify_reviews_as_packaging(all_reviews, components_list, conditions_list)
        classification_summary = get_packaging_classification_summary(classified_reviews)
        
        # Preserve the original total_reviews from enhanced data, don't overwrite it
        # total_reviews = classification_summary['total_reviews']  # REMOVED - this was overwriting the correct value
        packaging_related = classification_summary['packaging_reviews']
        packaging_percentage = classification_summary['packaging_percentage']
        
        # Recalculate sentiment counts from classified reviews
        positive_count = len([r for r in classified_reviews if r.get('sentiment') == "positive"])
        negative_count = len([r for r in classified_reviews if r.get('sentiment') == "negative"])
        neutral_count = len([r for r in classified_reviews if r.get('sentiment') == "neutral"])
        
        print(f"Product overview metrics updated: {packaging_related} packaging-related out of {total_reviews} total reviews")
    
    # Load product image
    product_image_url = url_for('static', filename=f"{product_folder}/product.jpg")
    

    
    # Load sample reviews (first 5)
    sample_reviews = all_reviews[:5] if all_reviews else []
    
    return render_template(
        "product_overview.html",
        product_name=product_folder.replace('_', ' ').replace('-', ' '),
        product_folder=product_folder,
        total_reviews=total_reviews,
        packaging_related=packaging_related,
        packaging_percentage=packaging_percentage,
        positive_count=positive_count,
        negative_count=negative_count,
        neutral_count=neutral_count,
        product_image_url=product_image_url,
        sample_reviews=sample_reviews,
        analysis_url=f"/analysis/{product_folder}"
    )

@app.route("/enhanced_analyze", methods=["GET", "POST"])
def enhanced_analyze():
    """Enhanced analysis route for PackSense agenda with comprehensive packaging review analysis"""
    if request.method == "POST":
        review_url = request.form.get("review_url", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        initial_count = int(request.form.get("initial_count", "100"))
        use_headless = request.form.get("use_headless", "false") == "true"

        if not review_url or not email or not password:
            return "Missing required fields", 400

        # Validate initial count
        if initial_count < 10 or initial_count > 500:
            initial_count = 100

        try:
            # Use enhanced scraping function
            print("Starting enhanced packaging review analysis...")
            reviews_data = scrape_enhanced_packaging_reviews(
                review_url=review_url,
                email=email,
                password=password,
                initial_count=initial_count,
                use_headless=use_headless
            )
            
            if not reviews_data:
                return "Failed to extract reviews. Please check your credentials and URL.", 400

            # Perform comprehensive analysis
            print("Performing comprehensive analysis...")
            analysis_results = analyze_packaging_reviews_comprehensive(reviews_data)
            
            # Save analysis results
            product_folder = reviews_data['product_folder']
            analysis_file = os.path.join("static", product_folder, "enhanced_analysis.json")
            os.makedirs(os.path.dirname(analysis_file), exist_ok=True)
            
            with open(analysis_file, 'w') as f:
                json.dump(analysis_results, f, indent=2, default=str)
            
            print(f"Enhanced analysis completed. Results saved to {analysis_file}")
            
            # Redirect to enhanced results page
            return redirect(f"/enhanced_results/{product_folder}")
            
        except Exception as e:
            print(f"Error in enhanced analysis: {e}")
            return f"Analysis failed: {str(e)}", 500

    # GET request - show form
    return render_template("enhanced_analyze.html")

@app.route("/enhanced_results/<product_folder>")
def enhanced_results(product_folder):
    """Enhanced results page with sidebar and comprehensive analysis"""
    try:
        # Load analysis results
        analysis_file = os.path.join("static", product_folder, "enhanced_analysis.json")
        if not os.path.exists(analysis_file):
            return "Analysis results not found", 404
            
        with open(analysis_file, 'r') as f:
            analysis_results = json.load(f)
        
        return render_template("enhanced_results.html", 
                             analysis_results=analysis_results,
                             product_folder=product_folder)
                             
    except Exception as e:
        print(f"Error loading enhanced results: {e}")
        return f"Error loading results: {str(e)}", 500

@app.route("/api/filter_reviews/<product_folder>")
def api_filter_reviews(product_folder):
    """API endpoint for filtering reviews by sentiment and keyword"""
    try:
        sentiment = request.args.get('sentiment', 'all')
        keyword = request.args.get('keyword', '')
        review_type = request.args.get('type', 'packaging')  # 'initial' or 'packaging'
        
        # Load analysis results
        analysis_file = os.path.join("static", product_folder, "enhanced_analysis.json")
        if not os.path.exists(analysis_file):
            return jsonify({'error': 'Analysis results not found'}), 404
            
        with open(analysis_file, 'r') as f:
            analysis_results = json.load(f)
        
        # Get reviews based on type
        if review_type == 'initial':
            reviews = analysis_results['initial_reviews']['reviews']
        else:
            reviews = analysis_results['packaging_reviews']['reviews']
        
        # Apply filters
        if sentiment != 'all':
            reviews = filter_reviews_by_sentiment(reviews, sentiment)
        
        if keyword:
            reviews = filter_reviews_by_keyword(reviews, keyword)
        
        # Limit results for performance
        reviews = reviews[:50]  # Limit to 50 reviews for display
        
        return jsonify({
            'reviews': reviews,
            'count': len(reviews),
            'filters': {
                'sentiment': sentiment,
                'keyword': keyword,
                'type': review_type
            }
        })
        
    except Exception as e:
        print(f"Error filtering reviews: {e}")
        return jsonify({'error': str(e)}), 500

@app.route("/download_images/<product_folder>")
def download_images(product_folder):
    img_dir = os.path.join("static", product_folder, "review_images")
    if not os.path.exists(img_dir): 
        return "No images", 404
    zip_name = f"{product_folder}_images.zip"
    zip_path = os.path.join("static", product_folder, zip_name)
    with zipfile.ZipFile(zip_path, 'w') as z:
        for root, _, files in os.walk(img_dir):
            for f in files:
                z.write(os.path.join(root, f), arcname=f)
    return send_file(zip_path, as_attachment=True)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_msg = data.get("message", "").strip()
    reviews = data.get("reviews", [])
    all_text = " ".join(str(r.get("review_text", "")) for r in reviews)
    lm = user_msg.lower()
    reply = None

    # 1) Greeting
    if lm in ("hi", "hello"):
        reply = (
            "Hi! I'm your PackSense review assistant. 👋\n"
            "You can ask me to:\n"
            "- Summarize reviews\n"
            "- Summarize this review: <your text>\n"
            "- Extract packaging keywords\n"
            "- Extract packaging keywords from this review: <your text>\n"
            "- Sentiment summary\n"
            "- Common packaging issues\n"
            "- Show reviews about <keyword>\n"
            "- Show sentiment chart\n"
            "- Show wordcloud\n"
            "- Help"
        )

    # 2) Summarize a single review
    elif lm.startswith("summarize this review:"):
        text = user_msg[len("summarize this review:"):].strip()
        summary = summarize_text(text)
        sentiment = analyze_sentiment(text)
        pk = extract_packaging_keywords(text)
        reply = (
            f"**Summary:** {summary}\n"
            f"**Sentiment:** {sentiment}\n"
        )

    # 3) Summarize all reviews
    elif "summarize reviews" in lm:
        summary = summarize_text(all_text)
        sentiment = analyze_sentiment(all_text)
        pk = extract_packaging_keywords(all_text)
        reply = (
            f"**Summary (all reviews):** {summary}\n"
            f"**Sentiment:** {sentiment}\n"
            f"**Packaging keywords:** {', '.join(pk) or 'None'}"
        )

    # 4) Sentiment summary
    elif "sentiment summary" in lm:
        # count positives, negatives, neutrals
        counts = {"positive": 0, "negative": 0, "neutral": 0}
        for r in reviews:
            s = analyze_sentiment(str(r.get("review_text", "")))
            counts[s] += 1
        reply = (
            f"Sentiment breakdown:\n"
            f"Positive: {counts['positive']}\n"
            f"Neutral:  {counts['neutral']}\n"
            f"Negative: {counts['negative']}"
        )

    # 5) Common packaging issues
    elif "common packaging issues" in lm:
        pk_all = extract_packaging_keywords(all_text)
        freq = {}
        for k in pk_all:
            freq[k] = freq.get(k, 0) + 1
        if freq:
            sorted_issues = sorted(freq.items(), key=lambda x: x[1], reverse=True)
            ranks = ", ".join(f"{k}: {v}" for k, v in sorted_issues)
            reply = f"Most common packaging issues: {ranks}"
        else:
            reply = "No packaging keywords found in the reviews."

    # 6) show reviews about <keyword>
    elif lm.startswith("show reviews about "):
        kw = lm.replace("show reviews about ", "").strip()
        matching = [
            str(r.get("review_text", "")).strip()
            for r in reviews
            if kw in str(r.get("review_text", "")).lower()
        ]
        if matching:
            lines = [f"{i+1}) {text}" for i, text in enumerate(matching)]
            reply = f'Reviews mentioning "{kw}":\n' + "\n".join(lines)
        else:
            reply = f'No reviews found mentioning "{kw}".'

    # 7) extract packaging keywords from this review
    elif lm.startswith("extract packaging keywords from this review:"):
        text = user_msg[len("extract packaging keywords from this review:"):].strip()
        pk = extract_packaging_keywords(text)
        reply = f"**Packaging keywords:** {', '.join(pk) or 'None'}"

    # 8) extract packaging keywords from all reviews
    elif "extract packaging keywords" in lm:
        pk = extract_packaging_keywords(all_text)
        reply = f"**Packaging keywords (all reviews):** {', '.join(pk) or 'None'}"

    # 9) help menu
    elif lm == "help":
        reply = (
            "Here are the commands I understand:\n"
            "- Summarize reviews\n"
            "- Summarize this review: <your text>\n"
            "- Extract packaging keywords\n"
            "- Extract packaging keywords from this review: <your text>\n"
            "- Sentiment summary\n"
            "- Common packaging issues\n"
            "- Show reviews about <keyword>\n"
            "- Show sentiment chart\n"
            "- Show wordcloud\n"
            "- Help"
        )

    # 10) Show sentiment bar chart
    elif lm == "show sentiment chart":
        # count positives, negatives, neutrals
        counts = {"positive": 0, "negative": 0, "neutral": 0}
        for r in reviews:
            s = analyze_sentiment(str(r.get("review_text", "")))
            counts[s] += 1
        return jsonify(
            reply="__chart__",
            chart_type="sentiment_bar",
            chart_data=counts
        )

    # 11) Show word‑cloud of packaging issues
    elif lm == "show wordcloud":
        pk = extract_packaging_keywords(all_text)
        from collections import Counter
        wc = Counter(pk)
        return jsonify(
            reply="__chart__",
            chart_type="wordcloud",
            chart_data=wc
        )    

    # fallback
    else:
        reply = (
            "Sorry, I didn't get that. Type `help` to see what I can do."
        )

    return jsonify(reply=reply)

def scheduled_scrape():
    # example scheduled job, adjust as needed
    review_url = "https://www.amazon.com/product-reviews/B085V5PPP8/"
    email = "you@example.com"
    password = "password"
    name, revs = scrape_all_amazon_reviews(review_url, email, password, review_type="all", use_headless=True)
    print(f"Scheduled scrape found {len(revs)} reviews for {name}" if revs else "No new reviews")

scheduler = BackgroundScheduler()
scheduler.add_job(scheduled_scrape, 'cron', hour=10, minute=0)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

@app.route('/neo4j_cooccurrence/<product_folder>')
def neo4j_cooccurrence(product_folder):
    """Get Neo4j-based co-occurrence data for a product"""
    try:
        from neo4j_utils import get_neo4j_network_data
        
        # Try to get data from Neo4j
        network_data = get_neo4j_network_data()
        
        if network_data:
            return jsonify(network_data)
        else:
            # Fallback to regular co-occurrence data
            folder = os.path.join("static", product_folder)
            recursive_analysis_file = os.path.join(folder, "recursive_analysis.json")
            
            if os.path.exists(recursive_analysis_file):
                with open(recursive_analysis_file, 'r') as f:
                    recursive_data = json.load(f)
                
                packaging_reviews_data = recursive_data.get('packaging_reviews', {})
                if isinstance(packaging_reviews_data, dict):
                    reviews = packaging_reviews_data.get('reviews', [])
                else:
                    reviews = []
                    
                packaging_keywords_flat = recursive_data.get('packaging_terms_searched', [])
                
                # Build co-occurrence data
                cooccurrence_data = {}
                for i, term1 in enumerate(packaging_keywords_flat):
                    for j, term2 in enumerate(packaging_keywords_flat):
                        if i != j:
                            cooccurrence_count = 0
                            for review in reviews:
                                review_text = str(review.get("review_text", "")).lower()
                                if term1.lower() in review_text and term2.lower() in review_text:
                                    cooccurrence_count += 1
                            
                            if cooccurrence_count > 0:
                                if term1 not in cooccurrence_data:
                                    cooccurrence_data[term1] = {}
                                cooccurrence_data[term1][term2] = cooccurrence_count
                
                # Convert to network format
                nodes = [{'id': term, 'name': term} for term in cooccurrence_data.keys()]
                relationships = []
                for term1, connections in cooccurrence_data.items():
                    for term2, weight in connections.items():
                        relationships.append({
                            'source': term1,
                            'target': term2,
                            'weight': weight
                        })
                
                return jsonify({
                    'nodes': nodes,
                    'relationships': relationships
                })
            else:
                return jsonify({'error': 'No data found'})
                
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/neo4j_term_details/<term_name>')
def neo4j_term_details(term_name):
    """Get detailed information about a term from Neo4j"""
    try:
        from neo4j_utils import Neo4jCooccurrenceGraph
        
        graph = Neo4jCooccurrenceGraph()
        details = graph.get_term_details(term_name)
        graph.close()
        
        if details:
            return jsonify(details)
        else:
            return jsonify({'error': 'Term not found'})
            
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == "__main__":
    import sys
    port = 5010
    if len(sys.argv) > 1 and sys.argv[1].startswith('--port'):
        try:
            port = int(sys.argv[1].split('=')[1])
        except (IndexError, ValueError):
            print("Invalid port format. Using default port 5010")
    elif len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("Invalid port number. Using default port 5010")
    
    print(f"Starting PackSense server on port {port}")
    app.run(debug=True, port=port, use_reloader=False) 