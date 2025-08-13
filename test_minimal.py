#!/usr/bin/env python3
"""
Minimal Flask app to test template syntax
"""

from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('results_enhanced.html', 
                         cooccurrence_data={},
                         defect_pairs=[],
                         reviews=[],
                         total_reviews=0,
                         positive_count=0,
                         neutral_count=0,
                         negative_count=0,
                         enhanced_metrics={'has_enhanced_data': False},
                         packaging_keywords=[],
                         packaging_dropdown_data=[],
                         image_files=[],
                         excel_file='',
                         keyword_image_map={},
                         product_folder='',
                         packaging_library_url='',
                         keyword_sentence_map={},
                         defect_image_url='',
                         base_image_url='',
                         packaging_freq={},
                         product_description_url='',
                         review_filters={})

if __name__ == '__main__':
    print("Starting minimal Flask app...")
    app.run(debug=True, port=5011)
