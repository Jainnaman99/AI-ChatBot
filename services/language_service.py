from langdetect import detect
import re

COMMON_ENGLISH_WORDS = [
    "where",
    "what",
    "who",
    "when",
    "why",
    "museum",
    "history",
    "india",
    "tell",
    "about"
]

HINGLISH_WORDS = [
    "hai",
    "ka",
    "ke",
    "kya",
    "kaise",
    "kyun",
    "kahan",  # where
    "kab",    # when
    "kaun",   # who
    "batao",
    "bataiye",
    "mein",
    "acha",
    "nahi",
    "haan",
    "aap",
    "koi",
    "yeh",
    "woh",
    "tha",
    "thi",
    "the"
]


def detect_language(text: str):

    lower_text = text.lower()

    # Remove punctuation for better word matching
    clean_text = re.sub(r'[^\w\s]', ' ', lower_text)

    # Hinglish detection - check if any Hindi/Hinglish word is present
    for word in HINGLISH_WORDS:
        # Use word boundary regex for better matching
        if re.search(r'\b' + re.escape(word) + r'\b', clean_text):
            return "hi"

    # English keyword detection
    english_matches = 0

    for word in COMMON_ENGLISH_WORDS:
        if word in lower_text:
            english_matches += 1

    if english_matches >= 1:
        return "en"

    try:

        detected = detect(text)

        # Prevent weird language detections
        allowed_languages = [
            "en",
            "hi"
            # ,
            # "ta",
            # "te",
            # "bn",
            # "pa",
            # "ml",
            # "mr",
            # "gu",
            # "kn"
        ]

        if detected not in allowed_languages:
            return "en"

        return detected

    except:
        return "en"