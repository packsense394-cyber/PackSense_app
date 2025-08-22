#!/usr/bin/env python3

import os
import json
from app import app

def test_browser_debug():
    """Test what data is actually being passed to the template"""
    
    product_folder = "Persil_Intense_Fresh_Everyday_Clean,_Liquid_Laundry_Detergent,_High_Efficiency_(HE),_Deep_Stain_Removal,_2X_Concentrated,_82.5_fl_oz,_110_Loads_2025-08-16"
    
    with app.app_context():
        # Load the recursive analysis data
        folder = os.path.join("static", product_folder)
        recursive_analysis_file = os.path.join(folder, "recursive_analysis.json")
        
        if os.path.exists(recursive_analysis_file):
            with open(recursive_analysis_file, 'r', encoding='utf-8') as f:
                recursive_data = json.load(f)
            
            # Get the correct data structure
            packaging_reviews_data = recursive_data.get("packaging_reviews", {})
            packaging_reviews = packaging_reviews_data.get("reviews", [])
            
            print(f"Found {len(packaging_reviews)} packaging reviews")
            
            # Test a specific keyword
            test_keyword = "label"
            
            # Check if this keyword appears in any reviews
            matching_reviews = []
            for review in packaging_reviews:
                review_text = str(review.get("review_text", "")).lower()
                if test_keyword.lower() in review_text:
                    matching_reviews.append(review)
            
            print(f"Found {len(matching_reviews)} reviews containing '{test_keyword}'")
            
            if matching_reviews:
                print(f"Sample review text: {matching_reviews[0].get('review_text', '')[:200]}...")
                
                # Check for images
                image_links = matching_reviews[0].get("image_links", "")
                review_images = matching_reviews[0].get("review_images", [])
                
                print(f"Image links: {image_links}")
                print(f"Review images: {review_images}")
            
            # Test the keyword mapping functions
            from nlp_utils import build_keyword_sentence_map, map_keyword_to_images
            
            kw_sent = build_keyword_sentence_map(packaging_reviews, [test_keyword])
            kw_img = map_keyword_to_images(packaging_reviews, [test_keyword])
            
            print(f"\nKeyword sentence map for '{test_keyword}': {len(kw_sent.get(test_keyword, []))} items")
            print(f"Keyword image map for '{test_keyword}': {len(kw_img.get(test_keyword, []))} items")
            
            if test_keyword in kw_sent:
                print(f"Sample sentence: {kw_sent[test_keyword][0] if kw_sent[test_keyword] else 'None'}")
            
            if test_keyword in kw_img:
                print(f"Sample image: {kw_img[test_keyword][0] if kw_img[test_keyword] else 'None'}")
            
            # Create a simple HTML file to test the JavaScript
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Debug Test</title>
</head>
<body>
    <h1>Debug Test for '{test_keyword}'</h1>
    
    <script>
        // Simulate the data that would be passed to the template
        const keywordSentenceMap = {json.dumps(kw_sent)};
        const keywordImageMap = {json.dumps(kw_img)};
        
        console.log('Keyword sentence map:', keywordSentenceMap);
        console.log('Keyword image map:', keywordImageMap);
        
        // Test the same logic as in the template
        const nodeName = '{test_keyword}';
        let relatedReviews = keywordSentenceMap[nodeName] || [];
        
        console.log('Node name:', nodeName);
        console.log('Related reviews:', relatedReviews);
        console.log('Related reviews length:', relatedReviews.length);
        
        // Extract sentence text
        let relatedSentences = [];
        if (relatedReviews.length > 0) {{
            if (typeof relatedReviews[0] === 'object' && relatedReviews[0].sentence) {{
                relatedSentences = relatedReviews.map(item => item.sentence);
            }} else {{
                relatedSentences = relatedReviews;
            }}
        }}
        
        console.log('Related sentences:', relatedSentences);
        console.log('Related sentences length:', relatedSentences.length);
        
        // Test images
        let relatedImages = keywordImageMap[nodeName] || [];
        console.log('Related images:', relatedImages);
        console.log('Related images length:', relatedImages.length);
        
        // Display results
        document.body.innerHTML += `
            <h2>Results for '{test_keyword}'</h2>
            <p><strong>Sentences found:</strong> ${{relatedSentences.length}}</p>
            <p><strong>Images found:</strong> ${{relatedImages.length}}</p>
            
            <h3>Sample Sentences:</h3>
            <ul>
                ${{relatedSentences.slice(0, 3).map(s => `<li>${{s}}</li>`).join('')}}
            </ul>
            
            <h3>Sample Images:</h3>
            <ul>
                ${{relatedImages.slice(0, 3).map(img => `<li>${{img}}</li>`).join('')}}
            </ul>
        `;
    </script>
</body>
</html>
            """
            
            with open("debug_test.html", "w") as f:
                f.write(html_content)
            
            print(f"\nCreated debug_test.html - open this in your browser to see the JavaScript output")
            
        else:
            print("Recursive analysis file not found")

if __name__ == "__main__":
    test_browser_debug()
