#!/usr/bin/env python3

import os
import json
from app import app
from nlp_utils import build_keyword_sentence_map, map_keyword_to_images

def test_template_data():
    """Test the exact data structure being passed to the template"""
    
    # Use the same product folder as in the terminal output
    product_folder = "Persil_Intense_Fresh_Everyday_Clean,_Liquid_Laundry_Detergent,_High_Efficiency_(HE),_Deep_Stain_Removal,_2X_Concentrated,_82.5_fl_oz,_110_Loads_2025-08-16"
    
    with app.app_context():
        # Load the recursive analysis data
        folder = os.path.join("static", product_folder)
        recursive_analysis_file = os.path.join(folder, "recursive_analysis.json")
        
        if os.path.exists(recursive_analysis_file):
            print(f"Loading enhanced recursive analysis data from {recursive_analysis_file}...")
            with open(recursive_analysis_file, 'r', encoding='utf-8') as f:
                enhanced_data = json.load(f)
            
            print(f"Enhanced data keys: {list(enhanced_data.keys())}")
            
            # Get the correct data structure
            packaging_reviews_data = enhanced_data.get('packaging_reviews', {})
            if isinstance(packaging_reviews_data, dict):
                reviews = packaging_reviews_data.get('reviews', [])
            else:
                reviews = []
                
            packaging_keywords_flat = enhanced_data.get('packaging_terms_searched', [])
            
            print(f"Type of reviews: {type(reviews)}")
            print(f"Type of packaging_keywords_flat: {type(packaging_keywords_flat)}")
            
            if isinstance(reviews, list):
                print(f"Enhanced data loaded: {len(reviews)} packaging-related reviews")
            else:
                print(f"Reviews is not a list: {reviews}")
                reviews = []
                
            print(f"Packaging keywords: {packaging_keywords_flat}")
            
            # Build keyword maps
            print("\nBuilding keyword sentence map...")
            kw_sent = build_keyword_sentence_map(reviews, packaging_keywords_flat)
            print(f"Keyword sentence map built with {len(kw_sent)} keywords")
            
            print("\nBuilding keyword image map...")
            kw_img = map_keyword_to_images(reviews, packaging_keywords_flat)
            print(f"Keyword image map built with {len(kw_img)} keywords")
            
            # Test specific keywords that should have data
            test_keywords = ['label', 'broke', 'protective', 'crack']
            
            print("\n=== TESTING SPECIFIC KEYWORDS ===")
            for keyword in test_keywords:
                print(f"\nKeyword: '{keyword}'")
                
                # Check sentence map
                sentences = kw_sent.get(keyword, [])
                print(f"  Sentences found: {len(sentences)}")
                if sentences:
                    print(f"  First sentence: {sentences[0]}")
                
                # Check image map
                images = kw_img.get(keyword, [])
                print(f"  Images found: {len(images)}")
                if images:
                    print(f"  First image: {images[0]}")
            
            # Test JSON serialization
            print("\n=== TESTING JSON SERIALIZATION ===")
            try:
                kw_sent_json = json.dumps(kw_sent)
                kw_img_json = json.dumps(kw_img)
                print("JSON serialization successful")
                print(f"kw_sent JSON length: {len(kw_sent_json)}")
                print(f"kw_img JSON length: {len(kw_img_json)}")
            except Exception as e:
                print(f"JSON serialization failed: {e}")
            
            # Test template rendering
            print("\n=== TESTING TEMPLATE DATA PASSING ===")
            from flask import render_template_string
            
            template = """
            <script>
            const keywordSentenceMap = JSON.parse('{{ keyword_sentence_map|tojson|safe }}');
            const keywordImageMap = JSON.parse('{{ keyword_image_map|tojson|safe }}');
            console.log('Template data loaded successfully');
            </script>
            """
            
            try:
                rendered = render_template_string(template, 
                                                keyword_sentence_map=kw_sent,
                                                keyword_image_map=kw_img)
                print("Template rendering successful")
                print(f"Rendered template length: {len(rendered)}")
            except Exception as e:
                print(f"Template rendering failed: {e}")
                
        else:
            print(f"Recursive analysis file not found: {recursive_analysis_file}")

if __name__ == "__main__":
    test_template_data()
