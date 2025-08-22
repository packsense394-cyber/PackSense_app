import re
import numpy as np
import pandas as pd
from collections import Counter, defaultdict
from datetime import datetime
import math

from sklearn.feature_extraction.text import TfidfVectorizer
from mlxtend.frequent_patterns import fpgrowth, association_rules

from nltk.corpus import wordnet as wn
from nltk.stem import WordNetLemmatizer

from config import sia, components_list, conditions_list

def get_related_words(word):
    related = set()
    lemmatizer = WordNetLemmatizer()
    related.add(lemmatizer.lemmatize(word.lower()))
    for syn in wn.synsets(word):
        for l in syn.lemmas():
            related.add(l.name().replace('_', ' ').lower())
            for ant in l.antonyms():
                related.add(ant.name().replace('_', ' ').lower())
    return related

def determine_category(word, comps, conds):
    lemmatizer = WordNetLemmatizer()
    w = word.lower()
    lemma = lemmatizer.lemmatize(w)
    in_c = (w in comps) or (lemma in comps)
    in_d = (w in conds) or (lemma in conds)
    if not in_c and not in_d:
        rels = get_related_words(w)
        in_c = any(r in comps for r in rels)
        in_d = any(r in conds for r in rels)
    if in_c and in_d: return "both"
    if in_c: return "component"
    if in_d: return "condition"
    return None

# Summarization & Sentiment & Packaging-extraction
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')

# simple patterns → phrase mappings
_PARAPHRASING_PATTERNS = [
    (re.compile(r'delivered.*later', re.I),            'arrived late'),
    (re.compile(r'box.*\b(mess|leak|damage)\b', re.I),  'box damaged and leaking'),
    (re.compile(r'bottle.*cut', re.I),                  'bottle was cut/damaged'),
    # add more as you discover recurring patterns…
]

def summarize_text(text, max_sentences=1):
    """
    1) Try to catch and paraphrase known complaint patterns.
    2) Otherwise, pick the top-scoring sentence by TF‑IDF score.
    """
    # 1) pattern-based paraphrase
    phrases = []
    for pat, phrase in _PARAPHRASING_PATTERNS:
        if pat.search(text):
            phrases.append(phrase)
    if phrases:
        # join distinct paraphrases
        return ' & '.join(dict.fromkeys(phrases))

    # 2) fallback to TF‑IDF extractive summary
    sents = _SENTENCE_SPLIT_RE.split(text.strip())
    if not sents:
        return ''

    # build TF‑IDF matrix over sentences
    vect = TfidfVectorizer(stop_words='english')
    tfidf = vect.fit_transform(sents)

    # score each sentence by the sum of its term weights
    scores = tfidf.sum(axis=1).A1
    top_idx = scores.argsort()[::-1][:max_sentences]
    
    # return sentences in original order
    selected = sorted(top_idx)
    return ' '.join(sents[i] for i in selected)

NEG_OVERRIDE = {"disappointed", "mess", "leak", "broken", "crack", "damage", "spill"}

def analyze_sentiment(text):
    # Ensure text is a string and handle None/float values
    if text is None:
        return "neutral"
    text = str(text)
    if not text.strip():
        return "neutral"
    scores = sia.polarity_scores(text)
    compound = scores['compound']
    if any(tok in text.lower() for tok in NEG_OVERRIDE):
        return "negative"
    if compound >= 0.05:
        return "positive"
    if compound <= -0.05:
        return "negative"
    return "neutral"

def extract_packaging_keywords(text):
    words = set(re.findall(r"\w+", text.lower()))
    found = set()
    for w in words:
        cat = determine_category(w, components_list, conditions_list)
        if cat in ("component","condition"):
            found.add(w)
    return sorted(found)

def build_component_condition_cooccurrence(reviews, df_library):
    from collections import defaultdict
    components = set(df_library[df_library["Category"] == "component"]["Keyword"].str.lower())
    conditions = set(df_library[df_library["Category"] == "condition"]["Keyword"].str.lower())
    pair_counts = defaultdict(int)
    for review in reviews:
        # Ensure review_text is a string before calling lower()
        review_text = review.get("review_text", "")
        if review_text is None:
            review_text = ""
        else:
            review_text = str(review_text)
        review_text = review_text.lower()
        words_in_review = set(re.findall(r"\w+", review_text))
        found_components = components.intersection(words_in_review)
        found_conditions = conditions.intersection(words_in_review)
        for comp in found_components:
            for cond in found_conditions:
                pair_counts[(comp, cond)] += 1
    rows = [{"Component": c, "Condition": d, "Count": cnt}
            for (c, d), cnt in pair_counts.items()]
    df_cooccurrence = pd.DataFrame(rows)
    if df_cooccurrence.empty:
        return pd.DataFrame()
    df_pivot = df_cooccurrence.pivot(index="Condition", columns="Component", values="Count").fillna(0).astype(int)
    return df_pivot

def update_packaging_library(packaging_filter_keywords, components_list, conditions_list, library_path, reviews):
    try:
        df_component_old = pd.read_excel(library_path, sheet_name="Component")
    except Exception:
        df_component_old = pd.DataFrame(columns=["Keyword", "Category"])
    try:
        df_condition_old = pd.read_excel(library_path, sheet_name="Condition")
    except Exception:
        df_condition_old = pd.DataFrame(columns=["Keyword", "Category"])
    existing_components = set(df_component_old["Keyword"].str.lower()) if not df_component_old.empty else set()
    existing_conditions = set(df_condition_old["Keyword"].str.lower()) if not df_condition_old.empty else set()
    expanded_components_list = list(set(components_list + list(existing_components)))
    expanded_conditions_list = list(set(conditions_list + list(existing_conditions)))
    new_components, new_conditions = [], []
    for kw_list in packaging_filter_keywords:
        for word in kw_list:
            w = word.strip().lower()
            cat = determine_category(word, expanded_components_list, expanded_conditions_list)
            if cat == "component" and w not in existing_components:
                new_components.append({"Keyword": w, "Category": "component"})
                existing_components.add(w)
            elif cat == "condition" and w not in existing_conditions:
                new_conditions.append({"Keyword": w, "Category": "condition"})
                existing_conditions.add(w)
            elif cat == "both":
                if w not in existing_components:
                    new_components.append({"Keyword": w, "Category": "component"})
                    existing_components.add(w)
                if w not in existing_conditions:
                    new_conditions.append({"Keyword": w, "Category": "condition"})
                    existing_conditions.add(w)
            for rel in get_related_words(word):
                r = rel.strip().lower()
                rcat = determine_category(rel, expanded_components_list, expanded_conditions_list)
                if rcat == "component" and r not in existing_components:
                    new_components.append({"Keyword": r, "Category": "component"})
                    existing_components.add(r)
                elif rcat == "condition" and r not in existing_conditions:
                    new_conditions.append({"Keyword": r, "Category": "condition"})
                    existing_conditions.add(r)
                elif rcat == "both":
                    if r not in existing_components:
                        new_components.append({"Keyword": r, "Category": "component"})
                        existing_components.add(r)
                    if r not in existing_conditions:
                        new_conditions.append({"Keyword": r, "Category": "condition"})
                        existing_conditions.add(r)
    df_component_updated = pd.concat([df_component_old, pd.DataFrame(new_components)], ignore_index=True)
    df_condition_updated = pd.concat([df_condition_old, pd.DataFrame(new_conditions)], ignore_index=True)
    df_library_combined = pd.concat([df_component_updated, df_condition_updated], ignore_index=True).drop_duplicates(subset=["Keyword"])
    df_pivot = build_component_condition_cooccurrence(reviews, df_library_combined)
    import xlsxwriter
    with pd.ExcelWriter(library_path, engine="xlsxwriter", mode="w") as writer:
        df_component_updated.to_excel(writer, sheet_name="Component", index=False)
        df_condition_updated.to_excel(writer, sheet_name="Condition", index=False)
        pivot_sheet = writer.book.add_worksheet("Comp_Cond_Cooc")
        writer.sheets["Comp_Cond_Cooc"] = pivot_sheet
        if df_pivot.empty:
            pivot_sheet.write(0,0,"No co-occurrence data found.")
        else:
            max_cols = len(df_pivot.columns)+1
            header_fmt = writer.book.add_format({
                "bold":True,"align":"center","bg_color":"#FF6666","font_color":"#FFFFFF","border":1
            })
            pivot_sheet.merge_range(0,0,0,max_cols-1,"component_condition_cooccurence",header_fmt)
            col_fmt = writer.book.add_format({"bold":True,"align":"center","border":1,"bg_color":"#FFD1DC"})
            row_fmt = writer.book.add_format({"bold":True,"align":"center","border":1,"bg_color":"#FFD1DC"})
            data_fmt = writer.book.add_format({"align":"center","border":1})
            pivot_sheet.write(1,0,"Condition",col_fmt)
            for j,c in enumerate(df_pivot.columns): pivot_sheet.write(1,j+1,c,col_fmt)
            for i,(cond,row) in enumerate(df_pivot.iterrows()):
                pivot_sheet.write(i+2,0,cond,row_fmt)
                for j,val in enumerate(row): pivot_sheet.write(i+2,j+1,val,data_fmt)

def filter_packaging_keywords(keyword_list):
    library_path = os.path.join("static","packaging_library.xlsx")
    lib_comps, lib_conds = [], []
    if os.path.exists(library_path):
        try:
            dfc = pd.read_excel(library_path,sheet_name="Component")
            lib_comps = dfc["Keyword"].dropna().astype(str).tolist()
        except: pass
        try:
            dfq = pd.read_excel(library_path,sheet_name="Condition")
            lib_conds = dfq["Keyword"].dropna().astype(str).tolist()
        except: pass
    terms = set([x.lower() for x in components_list+conditions_list+lib_comps+lib_conds])
    filtered = []
    for itemset in keyword_list:
        joined = " ".join(itemset).lower()
        if any(t in joined for t in terms):
            filtered.append(itemset)
    return filtered

def map_keyword_to_images(reviews, keywords):
    kw_images = {}
    for review in reviews:
        # Ensure review_text is a string before calling lower()
        review_text = review.get("review_text", "")
        if review_text is None:
            review_text = ""
        else:
            review_text = str(review_text)
        text = review_text.lower()
        
        # Try image_links first, then review_images as fallback
        image_links = review.get("image_links", "")
        if image_links is None:
            image_links = ""
        else:
            image_links = str(image_links)
        
        # If image_links is empty, try review_images
        if not image_links:
            review_images = review.get("review_images", [])
            if isinstance(review_images, list):
                image_links = ", ".join([str(img) for img in review_images if img])
            else:
                image_links = str(review_images) if review_images else ""
        
        imgs = image_links.split(", ") if image_links else []
        for kw in keywords:
            if kw.lower() in text:
                kw_images.setdefault(kw,[]).extend([i for i in imgs if i])
    return kw_images

def build_keyword_sentence_map(reviews, keywords):
    kw_map = {kw:[] for kw in keywords}
    for i,review in enumerate(reviews):
        # Ensure review_text is a string
        txt = review.get("review_text","")
        if txt is None:
            txt = ""
        else:
            txt = str(txt)
        sents = re.split(r'(?<=[.!?])\s+', txt)
        for sent in sents:
            low = sent.lower()
            for kw in keywords:
                if kw.lower() in low:
                    kw_map[kw].append({
                        "sentence": sent.strip(),
                        "review_text": txt.strip(),
                        "review_title": review.get("review_title",""),
                        "review_index": i
                    })
    return kw_map

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

def build_cooccurrence_data(frequent_itemsets):
    from collections import defaultdict
    from itertools import combinations
    item_counts, pair_counts = defaultdict(int), defaultdict(int)
    
    # Handle both original fpgrowth DataFrame and Excel-loaded DataFrame
    if frequent_itemsets.empty:
        return {"nodes": [], "links": []}
    
    # Check if this is the Excel-loaded format (has 'itemsets' column with string representations)
    if 'itemsets' in frequent_itemsets.columns:
        # Excel format: itemsets column contains string representations of lists
        for _, row in frequent_itemsets.iterrows():
            items_str = row['itemsets']
            # Convert string representation back to list
            if isinstance(items_str, str):
                # Remove brackets and split by comma, then clean up
                items_str = items_str.strip('[]')
                if items_str:
                    items = [item.strip().strip("'\"") for item in items_str.split(',')]
                else:
                    items = []
            else:
                items = items_str if isinstance(items_str, list) else []
            
            # Count individual items
            for it in items:
                item_counts[it] += 1
            
            # Count pairs
            if len(items) > 1:
                for a, b in combinations(sorted(items), 2):
                    pair_counts[(a, b)] += 1
    else:
        # Original fpgrowth format: itemsets column contains frozenset objects
        for _, row in frequent_itemsets.iterrows():
            items = row['itemsets']
            if isinstance(items, (list, frozenset)):
                items = list(items)
            else:
                items = []
            
            # Count individual items
            for it in items:
                item_counts[it] += 1
            
            # Count pairs
            if len(items) > 1:
                for a, b in combinations(sorted(items), 2):
                    pair_counts[(a, b)] += 1
    
    nodes = [{"id": i, "count": cnt} for i, cnt in item_counts.items()]
    links = [{"source": a, "target": b, "value": cnt} for (a, b), cnt in pair_counts.items()]
    return {"nodes": nodes, "links": links}

# Import os for file operations
import os 

def analyze_recursive_packaging_reviews(reviews_data: dict) -> dict:
    """
    NLP-Based Analysis for Recursive Review Extraction Strategy:
    1. Apply sentiment analysis (Positive / Neutral / Negative) on all extracted reviews
    2. Identify and highlight packaging-related reviews among the full dataset
    3. Return comprehensive analysis results
    """
    initial_reviews = reviews_data.get('initial_reviews', [])
    packaging_reviews = reviews_data.get('packaging_reviews', [])
    
    print("Starting NLP-Based Analysis...")
    
    # Step 1: Apply sentiment analysis on all extracted reviews
    print("Step 1: Applying sentiment analysis on all reviews...")
    
    # Analyze initial reviews
    initial_sentiments = []
    for review in initial_reviews:
        sentiment = analyze_sentiment(review.get('review_text', ''))
        initial_sentiments.append(sentiment)
    
    # Analyze packaging reviews
    packaging_sentiments = []
    for review in packaging_reviews:
        sentiment = analyze_sentiment(review.get('review_text', ''))
        packaging_sentiments.append(sentiment)
    
    # Calculate statistics
    initial_sentiment_counts = {
        'positive': initial_sentiments.count('positive'),
        'negative': initial_sentiments.count('negative'),
        'neutral': initial_sentiments.count('neutral')
    }
    
    packaging_sentiment_counts = {
        'positive': packaging_sentiments.count('positive'),
        'negative': packaging_sentiments.count('negative'),
        'neutral': packaging_sentiments.count('neutral')
    }
    
    # Calculate percentages
    total_initial = len(initial_reviews)
    total_packaging = len(packaging_reviews)
    
    initial_sentiment_percentages = {
        'positive': (initial_sentiment_counts['positive'] / total_initial * 100) if total_initial > 0 else 0,
        'negative': (initial_sentiment_counts['negative'] / total_initial * 100) if total_initial > 0 else 0,
        'neutral': (initial_sentiment_counts['neutral'] / total_initial * 100) if total_initial > 0 else 0
    }
    
    packaging_sentiment_percentages = {
        'positive': (packaging_sentiment_counts['positive'] / total_packaging * 100) if total_packaging > 0 else 0,
        'negative': (packaging_sentiment_counts['negative'] / total_packaging * 100) if total_packaging > 0 else 0,
        'neutral': (packaging_sentiment_counts['neutral'] / total_packaging * 100) if total_packaging > 0 else 0
    }
    
    # Step 2: Add sentiment to reviews and identify packaging-related reviews
    print("Step 2: Identifying and highlighting packaging-related reviews...")
    
    # Add sentiment to initial reviews
    for i, review in enumerate(initial_reviews):
        review['sentiment'] = initial_sentiments[i]
        review['is_packaging_related'] = False  # Mark as general review
    
    # Add sentiment to packaging reviews
    for i, review in enumerate(packaging_reviews):
        review['sentiment'] = packaging_sentiments[i]
        review['is_packaging_related'] = True  # Mark as packaging-related
    
    # Combine all reviews for full dataset analysis
    all_reviews = initial_reviews + packaging_reviews
    
    # Calculate overall statistics
    total_reviews = len(all_reviews)
    total_packaging_related = len(packaging_reviews)
    packaging_percentage = (total_packaging_related / total_reviews * 100) if total_reviews > 0 else 0
    
    # Overall sentiment analysis
    all_sentiments = initial_sentiments + packaging_sentiments
    overall_sentiment_counts = {
        'positive': all_sentiments.count('positive'),
        'negative': all_sentiments.count('negative'),
        'neutral': all_sentiments.count('neutral')
    }
    
    overall_sentiment_percentages = {
        'positive': (overall_sentiment_counts['positive'] / total_reviews * 100) if total_reviews > 0 else 0,
        'negative': (overall_sentiment_counts['negative'] / total_reviews * 100) if total_reviews > 0 else 0,
        'neutral': (overall_sentiment_counts['neutral'] / total_reviews * 100) if total_reviews > 0 else 0
    }
    
    # Prepare analysis results
    analysis_results = {
        'total_reviews_extracted': total_reviews,
        'packaging_related_reviews': total_packaging_related,
        'packaging_percentage': packaging_percentage,
        'sentiment_breakdown': {
            'positive': overall_sentiment_counts['positive'],
            'neutral': overall_sentiment_counts['neutral'],
            'negative': overall_sentiment_counts['negative']
        },
        'sentiment_percentages': overall_sentiment_percentages,
        'initial_reviews': {
            'total': total_initial,
            'sentiment_counts': initial_sentiment_counts,
            'sentiment_percentages': initial_sentiment_percentages,
            'reviews': initial_reviews
        },
        'packaging_reviews': {
            'total': total_packaging,
            'sentiment_counts': packaging_sentiment_counts,
            'sentiment_percentages': packaging_sentiment_percentages,
            'reviews': packaging_reviews,
            'keywords_found': list(set([r.get('search_term', '') for r in packaging_reviews if r.get('search_term')]))
        },
        'all_reviews': all_reviews,
        'packaging_terms_searched': reviews_data.get('packaging_terms_searched', [])
    }
    
    print(f"NLP analysis completed successfully!")
    print(f"Total reviews: {total_reviews}")
    print(f"Packaging-related: {total_packaging_related} ({packaging_percentage:.1f}%)")
    print(f"Sentiment breakdown: Positive={overall_sentiment_counts['positive']}, Neutral={overall_sentiment_counts['neutral']}, Negative={overall_sentiment_counts['negative']}")
    
    return analysis_results

def get_packaging_related_reviews(all_reviews: list) -> list:
    """
    Filter and return only packaging-related reviews
    """
    return [review for review in all_reviews if review.get('is_packaging_related', False)]

def get_reviews_by_sentiment(reviews: list, sentiment: str) -> list:
    """
    Filter reviews by sentiment (positive, neutral, negative)
    """
    return [review for review in reviews if review.get('sentiment') == sentiment]

def get_packaging_reviews_by_sentiment(packaging_reviews: list, sentiment: str) -> list:
    """
    Filter packaging-related reviews by sentiment
    """
    return [review for review in packaging_reviews if review.get('sentiment') == sentiment]

def get_most_common_packaging_issues(packaging_reviews: list) -> list:
    """
    Extract most common packaging issues from reviews
    """
    issue_keywords = {
        'damage': ['damage', 'damaged', 'broken', 'crack', 'cracked', 'crushed', 'dent'],
        'leakage': ['leak', 'leaking', 'spill', 'spilled', 'mess'],
        'packaging_quality': ['poor', 'cheap', 'flimsy', 'weak', 'thin'],
        'arrival_condition': ['arrived', 'delivery', 'shipping', 'package'],
        'seal_issues': ['seal', 'sealed', 'unsealed', 'open']
    }
    
    issue_counts = {category: 0 for category in issue_keywords.keys()}
    
    for review in packaging_reviews:
        text = review.get('review_text', '').lower()
        for category, keywords in issue_keywords.items():
            if any(keyword in text for keyword in keywords):
                issue_counts[category] += 1
    
    # Sort by count and return top issues
    sorted_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)
    return [{'issue': issue, 'count': count} for issue, count in sorted_issues if count > 0]

def get_overall_sentiment(sentiments: list) -> str:
    """
    Determine overall sentiment from a list of sentiments
    """
    if not sentiments:
        return 'neutral'
    
    positive_count = sentiments.count('positive')
    negative_count = sentiments.count('negative')
    neutral_count = sentiments.count('neutral')
    
    total = len(sentiments)
    positive_pct = positive_count / total * 100
    negative_pct = negative_count / total * 100
    
    if positive_pct > 60:
        return 'positive'
    elif negative_pct > 60:
        return 'negative'
    else:
        return 'neutral'

def filter_reviews_by_sentiment(reviews: list, sentiment: str) -> list:
    """
    Filter reviews by sentiment
    """
    return [review for review in reviews if review.get('sentiment') == sentiment]

def filter_reviews_by_keyword(reviews: list, keyword: str) -> list:
    """
    Filter reviews by keyword
    """
    return [review for review in reviews if keyword.lower() in review.get('review_text', '').lower()] 

def classify_reviews_as_packaging(reviews: list, components_list: list, conditions_list: list) -> list:
    """
    Comprehensive algorithm to classify reviews as packaging-related or not.
    
    Uses multiple classification techniques:
    1. Keyword-based classification
    2. Semantic similarity analysis
    3. Context analysis
    4. Confidence scoring
    5. Review structure analysis
    
    Args:
        reviews: List of review dictionaries
        components_list: List of packaging component keywords
        conditions_list: List of packaging condition keywords
    
    Returns:
        List of reviews with updated 'is_packaging_related' field and confidence scores
    """
    print("Starting comprehensive review classification...")
    
    # Expand keyword lists with synonyms and related terms
    expanded_components = expand_packaging_keywords(components_list)
    expanded_conditions = expand_packaging_keywords(conditions_list)
    
    # Create comprehensive packaging vocabulary
    packaging_vocabulary = set(expanded_components + expanded_conditions)
    
    # Add common packaging-related phrases
    packaging_phrases = [
        "packaging", "package", "container", "bottle", "box", "bag", "can", "jar", "tube", "pouch",
        "leak", "leaking", "leaked", "broken", "break", "broke", "damage", "damaged", "crack", "cracked",
        "seal", "sealed", "cap", "lid", "top", "cover", "plastic", "glass", "metal", "paper", "cardboard",
        "label", "labeled", "wrapped", "wrap", "protective", "protection", "secure", "secured",
        "spill", "spilled", "mess", "dirty", "clean", "hygienic", "safe", "unsafe", "dangerous",
        "tin", "aluminum", "steel", "foil", "bubble", "cushion", "padding", "tape", "adhesive",
        "transparent", "clear", "opaque", "color", "colored", "design", "shape", "size", "large", "small",
        "shipping", "delivery", "arrived", "damaged", "crushed", "dented", "torn", "ripped",
        "defective", "mold", "expired", "loose", "tight", "secure", "protective", "fragile",
        "handle", "grip", "easy to use", "difficult to open", "hard to open", "easy to pour",
        "drip", "dripping", "overflow", "overflowing", "splash", "splashing", "spray", "spraying"
    ]
    
    packaging_vocabulary.update(packaging_phrases)
    
    classified_reviews = []
    packaging_count = 0
    non_packaging_count = 0
    
    for review in reviews:
        review_text = str(review.get("review_text", "")).lower()
        review_title = str(review.get("review_title", "")).lower()
        full_text = f"{review_title} {review_text}"
        
        # Calculate classification score using multiple methods
        score = 0
        confidence = 0
        classification_methods = []
        
        # Method 1: Direct keyword matching
        keyword_score = calculate_keyword_score(full_text, packaging_vocabulary)
        score += keyword_score * 0.4  # 40% weight
        classification_methods.append(f"Keyword: {keyword_score:.2f}")
        
        # Method 2: Phrase and context analysis
        phrase_score = analyze_packaging_phrases(full_text)
        score += phrase_score * 0.3  # 30% weight
        classification_methods.append(f"Phrase: {phrase_score:.2f}")
        
        # Method 3: Review structure analysis
        structure_score = analyze_review_structure(review_text, review_title)
        score += structure_score * 0.2  # 20% weight
        classification_methods.append(f"Structure: {structure_score:.2f}")
        
        # Method 4: Sentiment-context analysis
        sentiment_score = analyze_sentiment_context(review_text, review.get("sentiment", ""))
        score += sentiment_score * 0.1  # 10% weight
        classification_methods.append(f"Sentiment: {sentiment_score:.2f}")
        
        # Determine classification threshold
        threshold = 0.3  # Reviews with score >= 0.3 are classified as packaging-related
        
        is_packaging = score >= threshold
        confidence = min(score, 1.0)  # Confidence is the score, capped at 1.0
        
        # Update review with classification results
        review['is_packaging_related'] = is_packaging
        review['packaging_score'] = score
        review['packaging_confidence'] = confidence
        review['classification_methods'] = classification_methods
        
        if is_packaging:
            packaging_count += 1
        else:
            non_packaging_count += 1
        
        classified_reviews.append(review)
    
    print(f"Classification completed:")
    print(f"  Packaging-related: {packaging_count}")
    print(f"  Non-packaging: {non_packaging_count}")
    print(f"  Total: {len(reviews)}")
    print(f"  Packaging percentage: {(packaging_count/len(reviews)*100):.1f}%")
    
    return classified_reviews

def expand_packaging_keywords(keywords: list) -> list:
    """Expand keywords with synonyms and related terms."""
    expanded = set(keywords)
    
    # Add common variations and synonyms
    synonym_map = {
        'bottle': ['bottles', 'bottling', 'bottled'],
        'package': ['packages', 'packaging', 'packaged'],
        'container': ['containers', 'containing'],
        'leak': ['leaks', 'leaking', 'leaked', 'leakage'],
        'damage': ['damages', 'damaged', 'damaging'],
        'break': ['breaks', 'breaking', 'broken', 'broke'],
        'spill': ['spills', 'spilling', 'spilled'],
        'mess': ['messy', 'messes'],
        'clean': ['cleans', 'cleaning', 'cleaned'],
        'secure': ['secures', 'securing', 'secured', 'security'],
        'protective': ['protects', 'protecting', 'protected', 'protection'],
        'plastic': ['plastics'],
        'glass': ['glasses'],
        'metal': ['metals', 'metallic'],
        'cardboard': ['cardboards'],
        'tape': ['tapes', 'taping', 'taped'],
        'label': ['labels', 'labeling', 'labeled'],
        'seal': ['seals', 'sealing', 'sealed'],
        'cap': ['caps', 'capping', 'capped'],
        'lid': ['lids'],
        'box': ['boxes', 'boxing', 'boxed'],
        'bag': ['bags', 'bagging', 'bagged'],
        'can': ['cans', 'canning', 'canned'],
        'jar': ['jars'],
        'tube': ['tubes', 'tubing', 'tubed'],
        'pouch': ['pouches'],
        'tin': ['tins'],
        'sachet': ['sachets'],
        'envelope': ['envelopes'],
        'mold': ['molds', 'molding', 'molded'],
        'padding': ['pads', 'padded'],
        'bubble': ['bubbles', 'bubbling', 'bubbled'],
        'cushion': ['cushions', 'cushioning', 'cushioned'],
        'wrap': ['wraps', 'wrapping', 'wrapped'],
        'color': ['colors', 'coloring', 'colored'],
        'design': ['designs', 'designing', 'designed'],
        'size': ['sizes', 'sizing', 'sized'],
        'shape': ['shapes', 'shaping', 'shaped']
    }
    
    for keyword in keywords:
        if keyword in synonym_map:
            expanded.update(synonym_map[keyword])
    
    return list(expanded)

def calculate_keyword_score(text: str, vocabulary: set) -> float:
    """Calculate keyword-based score for packaging classification."""
    words = set(text.split())
    matches = words.intersection(vocabulary)
    
    if not matches:
        return 0.0
    
    # Weight by frequency and importance
    score = 0.0
    for match in matches:
        # Base score for each match
        base_score = 0.1
        
        # Bonus for multiple occurrences
        count = text.count(match)
        if count > 1:
            base_score += min(count * 0.05, 0.2)  # Cap at 0.2 bonus
        
        # Bonus for important terms
        important_terms = {'leak', 'damage', 'broken', 'spill', 'mess', 'packaging', 'container'}
        if match in important_terms:
            base_score += 0.1
        
        score += base_score
    
    return min(score, 1.0)  # Cap at 1.0

def analyze_packaging_phrases(text: str) -> float:
    """Analyze text for packaging-related phrases and context."""
    score = 0.0
    
    # Packaging-specific phrases with weights
    packaging_phrases = {
        'damaged during shipping': 0.8,
        'arrived damaged': 0.8,
        'packaging was': 0.7,
        'container was': 0.7,
        'bottle was': 0.7,
        'box was': 0.7,
        'leaked out': 0.8,
        'spilled out': 0.8,
        'came broken': 0.8,
        'was broken': 0.7,
        'got damaged': 0.7,
        'easy to pour': 0.6,
        'hard to open': 0.6,
        'difficult to open': 0.6,
        'messy to use': 0.7,
        'clean to use': 0.5,
        'secure packaging': 0.6,
        'protective packaging': 0.6,
        'well packaged': 0.5,
        'poorly packaged': 0.7,
        'packaging design': 0.6,
        'container design': 0.6,
        'bottle design': 0.6,
        'cap was loose': 0.8,
        'lid was loose': 0.8,
        'seal was broken': 0.8,
        'tape was': 0.6,
        'label was': 0.6,
        'plastic container': 0.6,
        'glass bottle': 0.6,
        'cardboard box': 0.6,
        'metal can': 0.6
    }
    
    for phrase, weight in packaging_phrases.items():
        if phrase in text:
            score += weight
    
    return min(score, 1.0)

def analyze_review_structure(review_text: str, review_title: str) -> float:
    """Analyze review structure for packaging-related indicators."""
    score = 0.0
    
    # Check title for packaging indicators
    title_words = review_title.split()
    if len(title_words) <= 5:  # Short titles are more likely to be specific
        packaging_title_words = {'packaging', 'bottle', 'container', 'damaged', 'leak', 'broken', 'arrived'}
        if any(word in packaging_title_words for word in title_words):
            score += 0.3
    
    # Check for specific review patterns
    patterns = [
        'arrived', 'shipping', 'delivery', 'packaged', 'wrapped',
        'damaged', 'broken', 'leaked', 'spilled', 'mess',
        'container', 'bottle', 'box', 'package', 'packaging'
    ]
    
    for pattern in patterns:
        if pattern in review_text:
            score += 0.1
    
    # Check for complaint patterns (often packaging-related)
    complaint_indicators = ['but', 'however', 'unfortunately', 'disappointed', 'problem', 'issue']
    if any(indicator in review_text for indicator in complaint_indicators):
        # If complaint + packaging terms, higher score
        packaging_terms = ['packaging', 'container', 'bottle', 'damage', 'leak', 'broken']
        if any(term in review_text for term in packaging_terms):
            score += 0.2
    
    return min(score, 1.0)

def analyze_sentiment_context(review_text: str, sentiment: str) -> float:
    """Analyze sentiment in context of packaging terms."""
    score = 0.0
    
    # Negative sentiment + packaging terms = likely packaging complaint
    if sentiment == "negative":
        packaging_terms = ['packaging', 'container', 'bottle', 'damage', 'leak', 'broken', 'spill', 'mess']
        if any(term in review_text for term in packaging_terms):
            score += 0.4
    
    # Positive sentiment + packaging terms = likely packaging praise
    elif sentiment == "positive":
        packaging_terms = ['packaging', 'container', 'bottle', 'design', 'easy', 'convenient', 'secure']
        if any(term in review_text for term in packaging_terms):
            score += 0.2
    
    return min(score, 1.0)

def get_packaging_classification_summary(reviews: list) -> dict:
    """Generate a summary of the packaging classification results."""
    packaging_reviews = [r for r in reviews if r.get('is_packaging_related', False)]
    non_packaging_reviews = [r for r in reviews if not r.get('is_packaging_related', False)]
    
    # Calculate confidence statistics
    packaging_confidences = [r.get('packaging_confidence', 0) for r in packaging_reviews]
    non_packaging_confidences = [r.get('packaging_confidence', 0) for r in non_packaging_reviews]
    
    summary = {
        'total_reviews': len(reviews),
        'packaging_reviews': len(packaging_reviews),
        'non_packaging_reviews': len(non_packaging_reviews),
        'packaging_percentage': (len(packaging_reviews) / len(reviews) * 100) if reviews else 0,
        'avg_packaging_confidence': sum(packaging_confidences) / len(packaging_confidences) if packaging_confidences else 0,
        'avg_non_packaging_confidence': sum(non_packaging_confidences) / len(non_packaging_confidences) if non_packaging_confidences else 0,
        'high_confidence_packaging': len([c for c in packaging_confidences if c >= 0.7]),
        'low_confidence_packaging': len([c for c in packaging_confidences if c < 0.5])
    }
    
    return summary 