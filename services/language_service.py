from langdetect import detect

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
    "batao",
    "mein",
    "acha",
    "nahi",
    "haan",
    "aap"
]


def detect_language(text: str):

    lower_text = text.lower()

    # Hinglish detection
    for word in HINGLISH_WORDS:
        if f" {word} " in f" {lower_text} ":
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