#!/usr/bin/env python3

import requests
import json

def test_related_content():
    """Test the related content functionality"""
    
    # Test the analysis page
    url = "http://127.0.0.1:5010/analysis/Persil_Intense_Fresh_Everyday_Clean,_Liquid_Laundry_Detergent,_High_Efficiency_(HE),_Deep_Stain_Removal,_2X_Concentrated,_82.5_fl_oz,_110_Loads_2025-08-16"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            print("✅ Analysis page loaded successfully")
            
            # Check if the page contains the expected data
            content = response.text
            
            # Check for keyword sentence map
            if "keywordSentenceMap" in content:
                print("✅ Keyword sentence map found in page")
            else:
                print("❌ Keyword sentence map not found in page")
            
            # Check for keyword image map
            if "keywordImageMap" in content:
                print("✅ Keyword image map found in page")
            else:
                print("❌ Keyword image map not found in page")
            
            # Check for specific keywords
            test_keywords = ['label', 'broke', 'protective', 'crack']
            for keyword in test_keywords:
                if keyword in content:
                    print(f"✅ Keyword '{keyword}' found in page")
                else:
                    print(f"❌ Keyword '{keyword}' not found in page")
            
            # Test Neo4j endpoints
            print("\n=== Testing Neo4j Endpoints ===")
            
            # Test co-occurrence endpoint
            neo4j_url = f"http://127.0.0.1:5010/neo4j_cooccurrence/Persil_Intense_Fresh_Everyday_Clean,_Liquid_Laundry_Detergent,_High_Efficiency_(HE),_Deep_Stain_Removal,_2X_Concentrated,_82.5_fl_oz,_110_Loads_2025-08-16"
            try:
                neo4j_response = requests.get(neo4j_url)
                if neo4j_response.status_code == 200:
                    neo4j_data = neo4j_response.json()
                    if 'nodes' in neo4j_data and 'relationships' in neo4j_data:
                        print(f"✅ Neo4j co-occurrence data: {len(neo4j_data['nodes'])} nodes, {len(neo4j_data['relationships'])} relationships")
                    else:
                        print("❌ Neo4j co-occurrence data missing nodes or relationships")
                else:
                    print(f"❌ Neo4j co-occurrence endpoint returned status {neo4j_response.status_code}")
            except Exception as e:
                print(f"❌ Neo4j co-occurrence endpoint error: {e}")
            
            # Test term details endpoint
            term_url = "http://127.0.0.1:5010/neo4j_term_details/label"
            try:
                term_response = requests.get(term_url)
                if term_response.status_code == 200:
                    term_data = term_response.json()
                    if 'name' in term_data:
                        print(f"✅ Neo4j term details for 'label': {term_data['name']}")
                    else:
                        print("❌ Neo4j term details missing name")
                else:
                    print(f"❌ Neo4j term details endpoint returned status {term_response.status_code}")
            except Exception as e:
                print(f"❌ Neo4j term details endpoint error: {e}")
            
        else:
            print(f"❌ Analysis page returned status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error testing analysis page: {e}")

if __name__ == "__main__":
    test_related_content()
