#!/usr/bin/env python3
"""
Test script to verify co-occurrence and defect analysis data generation
"""

import os
import json
from config import components_list, conditions_list

def test_data_generation():
    """Test the data generation logic"""
    
    # Test with a sample recursive analysis file
    test_folder = "static/Tide_Liquid_Laundry_Detergent,_Original,_64_loads,_84_fl_oz,_HE_Compatible_(Packaging_May_Vary)_2025-08-12"
    recursive_analysis_file = os.path.join(test_folder, "recursive_analysis.json")
    
    if not os.path.exists(recursive_analysis_file):
        print(f"Test file not found: {recursive_analysis_file}")
        return
    
    print("Loading test data...")
    with open(recursive_analysis_file, 'r') as f:
        recursive_data = json.load(f)
    
    # Extract test data
    all_reviews = recursive_data.get('all_reviews', [])
    packaging_terms_searched = recursive_data.get('packaging_terms_searched', [])
    
    print(f"Total reviews: {len(all_reviews)}")
    print(f"Packaging terms: {packaging_terms_searched}")
    print(f"Components list: {components_list}")
    print(f"Conditions list: {conditions_list}")
    
    # Test co-occurrence generation
    print("\n=== Testing Co-occurrence Generation ===")
    cooccurrence_data = {}
    
    if packaging_terms_searched:
        print(f"Building co-occurrence matrix for {len(packaging_terms_searched)} terms")
        for i, term1 in enumerate(packaging_terms_searched):
            for j, term2 in enumerate(packaging_terms_searched):
                if i != j:
                    cooccurrence_count = 0
                    for review in all_reviews:
                        review_text = str(review.get("review_text", "")).lower()
                        if term1.lower() in review_text and term2.lower() in review_text:
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
            print("No co-occurrence relationships found")
    
    # Test defect analysis
    print("\n=== Testing Defect Analysis ===")
    defect_pairs = []
    
    # Create a more flexible matching system
    for term in packaging_terms_searched:
        term_lower = term.lower()
        
        # Check if this term is a condition
        is_condition = any(cond.lower() in term_lower or term_lower in cond.lower() 
                          for cond in conditions_list)
        
        if is_condition:
            print(f"Found condition term: {term}")
            # This is a condition term, find component terms it co-occurs with
            for review in all_reviews:
                review_text = str(review.get("review_text", "")).lower()
                if term_lower in review_text:
                    for comp in components_list:
                        comp_lower = comp.lower()
                        if comp_lower in review_text:
                            defect_pairs.append((comp, term))
    
    defect_pairs = list(set(defect_pairs))  # Remove duplicates
    print(f"Found {len(defect_pairs)} defect pairs")
    
    if defect_pairs:
        print("Sample defect pairs:")
        for pair in defect_pairs[:5]:
            print(f"  {pair[0]} → {pair[1]}")
    else:
        print("No defect pairs found with strict matching, trying general approach...")
        for review in all_reviews:
            review_text = str(review.get("review_text", "")).lower()
            review_components = [comp for comp in components_list if comp.lower() in review_text]
            review_conditions = [cond for cond in conditions_list if cond.lower() in review_text]
            
            for comp in review_components:
                for cond in review_conditions:
                    defect_pairs.append((comp, cond))
        
        defect_pairs = list(set(defect_pairs))  # Remove duplicates
        print(f"Found {len(defect_pairs)} defect pairs with general approach")
        if defect_pairs:
            print("Sample defect pairs:")
            for pair in defect_pairs[:5]:
                print(f"  {pair[0]} → {pair[1]}")
    
    return cooccurrence_data, defect_pairs

if __name__ == "__main__":
    cooccurrence_data, defect_pairs = test_data_generation()
    
    print(f"\n=== Summary ===")
    print(f"Co-occurrence data: {len(cooccurrence_data)} terms with relationships")
    print(f"Defect pairs: {len(defect_pairs)} pairs found")
    
    # Test JSON serialization
    try:
        cooccurrence_json = json.dumps(cooccurrence_data)
        defect_json = json.dumps(defect_pairs)
        print("✓ JSON serialization successful")
    except Exception as e:
        print(f"✗ JSON serialization failed: {e}")
