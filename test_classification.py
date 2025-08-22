#!/usr/bin/env python3

import sys
import os

# Add the current directory to the path so we can import from nlp_utils
sys.path.append('.')

from nlp_utils import classify_reviews_as_packaging, get_packaging_classification_summary
from config import components_list, conditions_list

def test_classification_algorithm():
    """Test the comprehensive packaging classification algorithm with sample reviews."""
    
    # Sample reviews for testing
    sample_reviews = [
        {
            "review_title": "Great detergent, cleans well",
            "review_text": "This detergent works great and cleans my clothes perfectly. The scent is nice and it's very effective.",
            "sentiment": "positive"
        },
        {
            "review_title": "Bottle was damaged during shipping",
            "review_text": "The product arrived with a damaged bottle. The cap was loose and detergent leaked all over the box. Very disappointed with the packaging.",
            "sentiment": "negative"
        },
        {
            "review_title": "Easy to use container",
            "review_text": "The bottle design is excellent. Easy to pour and the cap seals tightly. No leaks or spills.",
            "sentiment": "positive"
        },
        {
            "review_title": "Good value for money",
            "review_text": "Great price for the amount you get. Works well and lasts a long time.",
            "sentiment": "positive"
        },
        {
            "review_title": "Arrived broken and leaking",
            "review_text": "The container was crushed during delivery and the liquid spilled everywhere. The packaging was inadequate for shipping.",
            "sentiment": "negative"
        },
        {
            "review_title": "Convenient packaging",
            "review_text": "Love the pouch design. Easy to store and use. Much more convenient than traditional bottles.",
            "sentiment": "positive"
        },
        {
            "review_title": "Product quality is good",
            "review_text": "The detergent itself works well, but the bottle is hard to open and the cap is too tight.",
            "sentiment": "neutral"
        },
        {
            "review_title": "Messy to use",
            "review_text": "The bottle design is terrible. It's messy to pour and the cap doesn't seal properly. Product gets everywhere.",
            "sentiment": "negative"
        },
        {
            "review_title": "Excellent cleaning power",
            "review_text": "This detergent removes stains like magic. Highly recommend for tough cleaning jobs.",
            "sentiment": "positive"
        },
        {
            "review_title": "Secure packaging",
            "review_text": "The product was well packaged with protective bubble wrap. Arrived in perfect condition.",
            "sentiment": "positive"
        }
    ]
    
    print("🧪 Testing Comprehensive Packaging Classification Algorithm")
    print("=" * 60)
    
    # Apply classification
    classified_reviews = classify_reviews_as_packaging(sample_reviews, components_list, conditions_list)
    
    # Display results
    print("\n📊 Classification Results:")
    print("-" * 40)
    
    for i, review in enumerate(classified_reviews, 1):
        is_packaging = review.get('is_packaging_related', False)
        score = review.get('packaging_score', 0)
        confidence = review.get('packaging_confidence', 0)
        methods = review.get('classification_methods', [])
        
        status = "✅ PACKAGING" if is_packaging else "❌ NON-PACKAGING"
        print(f"\n{i}. {status}")
        print(f"   Title: {review['review_title']}")
        print(f"   Score: {score:.3f} | Confidence: {confidence:.3f}")
        print(f"   Methods: {', '.join(methods)}")
        print(f"   Text: {review['review_text'][:80]}...")
    
    # Get summary
    summary = get_packaging_classification_summary(classified_reviews)
    
    print("\n📈 Classification Summary:")
    print("-" * 40)
    print(f"Total Reviews: {summary['total_reviews']}")
    print(f"Packaging-Related: {summary['packaging_reviews']}")
    print(f"Non-Packaging: {summary['non_packaging_reviews']}")
    print(f"Packaging Percentage: {summary['packaging_percentage']:.1f}%")
    print(f"Average Packaging Confidence: {summary['avg_packaging_confidence']:.3f}")
    print(f"High Confidence Packaging: {summary['high_confidence_packaging']}")
    print(f"Low Confidence Packaging: {summary['low_confidence_packaging']}")
    
    # Show detailed breakdown
    print("\n🔍 Detailed Analysis:")
    print("-" * 40)
    
    packaging_reviews = [r for r in classified_reviews if r.get('is_packaging_related', False)]
    non_packaging_reviews = [r for r in classified_reviews if not r.get('is_packaging_related', False)]
    
    print(f"\nPackaging-Related Reviews ({len(packaging_reviews)}):")
    for review in packaging_reviews:
        print(f"  • {review['review_title']} (Score: {review.get('packaging_score', 0):.3f})")
    
    print(f"\nNon-Packaging Reviews ({len(non_packaging_reviews)}):")
    for review in non_packaging_reviews:
        print(f"  • {review['review_title']} (Score: {review.get('packaging_score', 0):.3f})")
    
    print("\n✅ Classification Algorithm Test Completed!")

if __name__ == "__main__":
    test_classification_algorithm()
