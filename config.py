import nltk
from nltk.corpus import wordnet as wn
from nltk.stem import WordNetLemmatizer
from nltk.sentiment import SentimentIntensityAnalyzer

# NLTK Resource Check and Download
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

# Initialize sentiment analyzer
sia = SentimentIntensityAnalyzer()

# Pre-defined Components & Conditions
components_list = list(set([x.strip().lower() for x in [
    "Bottle", "Box", "Design", "Container", "Seal", "Cap", "Lid", "Package", "Packaging",
    "Paper", "Plastic", "Glass", "Pack", "Tape", "Logo", "Label", "Protective", "Bag",
    "Envelope", "Mold", "Padding", "Recyclable", "Tin", "Sachet", "Jar", "Pouch"
]]))

conditions_list = list(set([x.strip().lower() for x in [
    "mess", "damage", "expiration", "loose", "moldy", "crushed", "broken", "crack",
    "broke", "leak", "spill", "dent", "mold", "puncture"
]])) 