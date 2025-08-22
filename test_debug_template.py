#!/usr/bin/env python3

import os
import json
from app import app

def test_template_data():
    """Test the exact data being passed to the template"""
    
    product_folder = "Persil_Intense_Fresh_Everyday_Clean,_Liquid_Laundry_Detergent,_High_Efficiency_(HE),_Deep_Stain_Removal,_2X_Concentrated,_82.5_fl_oz,_110_Loads_2025-08-16"
    
    with app.app_context():
        # Load the recursive analysis data
        folder = os.path.join("static", product_folder)
        recursive_analysis_file = os.path.join(folder, "recursive_analysis.json")
        
        if os.path.exists(recursive_analysis_file):
            with open(recursive_analysis_file, 'r', encoding='utf-8') as f:
                recursive_data = json.load(f)
            
            # Get the correct data structure
            packaging_reviews_data = recursive_data.get('packaging_reviews', {})
            if isinstance(packaging_reviews_data, dict):
                reviews = packaging_reviews_data.get('reviews', [])
            else:
                reviews = []
                
            packaging_keywords_flat = recursive_data.get('packaging_terms_searched', [])
            
            # Build keyword maps
            from nlp_utils import build_keyword_sentence_map, map_keyword_to_images
            
            kw_sent = build_keyword_sentence_map(reviews, packaging_keywords_flat)
            kw_img = map_keyword_to_images(reviews, packaging_keywords_flat)
            
            # Test specific keywords
            test_keywords = ['label', 'broke', 'protective', 'crack']
            
            print("=== TEMPLATE DATA DEBUG ===")
            for keyword in test_keywords:
                print(f"\nKeyword: '{keyword}'")
                
                # Check sentence map
                sentences = kw_sent.get(keyword, [])
                print(f"  Sentences found: {len(sentences)}")
                if sentences:
                    print(f"  First sentence type: {type(sentences[0])}")
                    print(f"  First sentence: {sentences[0]}")
                
                # Check image map
                images = kw_img.get(keyword, [])
                print(f"  Images found: {len(images)}")
                if images:
                    print(f"  First image: {images[0]}")
            
            # Test JSON serialization
            print("\n=== JSON SERIALIZATION TEST ===")
            try:
                kw_sent_json = json.dumps(kw_sent)
                kw_img_json = json.dumps(kw_img)
                print("JSON serialization successful")
                
                # Test template rendering
                from flask import render_template_string
                
                template = """
                <script>
                const keywordSentenceMap = JSON.parse('{{ keyword_sentence_map|tojson|safe }}');
                const keywordImageMap = JSON.parse('{{ keyword_image_map|tojson|safe }}');
                
                console.log('=== TEMPLATE DATA ===');
                console.log('keywordSentenceMap keys:', Object.keys(keywordSentenceMap));
                console.log('keywordImageMap keys:', Object.keys(keywordImageMap));
                
                // Test specific keyword
                const testKeyword = 'label';
                console.log('Test keyword:', testKeyword);
                console.log('In sentence map:', testKeyword in keywordSentenceMap);
                console.log('In image map:', testKeyword in keywordImageMap);
                
                if (testKeyword in keywordSentenceMap) {
                    console.log('Sentence data:', keywordSentenceMap[testKeyword]);
                }
                if (testKeyword in keywordImageMap) {
                    console.log('Image data:', keywordImageMap[testKeyword]);
                }
                </script>
                """
                
                rendered = render_template_string(template, 
                                                keyword_sentence_map=kw_sent,
                                                keyword_image_map=kw_img)
                
                print("Template rendering successful")
                print("Rendered template length:", len(rendered))
                
                # Save the rendered template to a file for inspection
                with open('debug_template.html', 'w') as f:
                    f.write(rendered)
                print("Debug template saved to debug_template.html")
                
            except Exception as e:
                print(f"Error: {e}")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    test_template_data()
