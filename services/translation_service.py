"""
Translation service for multilingual support
Uses deep-translator to translate queries and responses
"""

from deep_translator import GoogleTranslator
from typing import Optional
import logging

logger = logging.getLogger(__name__)


# Language code mapping (ISO 639-1)
SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "te": "Telugu",
    "ta": "Tamil",
    "bn": "Bengali",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "or": "Odia",
    "as": "Assamese",
    "ur": "Urdu"
}


class TranslationService:
    """
    Service for translating text between languages
    """

    def __init__(self):
        """Initialize translation service"""
        pass

    def translate(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """
        Translate text from source language to target language

        Args:
            text: Text to translate
            source_lang: Source language code (e.g., 'hi', 'te')
            target_lang: Target language code (e.g., 'en')

        Returns:
            Translated text or None if translation fails
        """
        # Skip if same language
        if source_lang == target_lang:
            return text

        # Skip if source is already English and target is English
        if source_lang == "en" and target_lang == "en":
            return text

        try:
            translator = GoogleTranslator(source=source_lang, target=target_lang)
            translated = translator.translate(text)

            logger.info(f"Translated ({source_lang}→{target_lang}): '{text[:50]}...' → '{translated[:50]}...'")

            return translated

        except Exception as e:
            logger.error(f"Translation error ({source_lang}→{target_lang}): {str(e)}")
            # Return original text if translation fails
            return text

    def to_english(self, text: str, source_lang: str) -> str:
        """
        Translate text to English

        Args:
            text: Text to translate
            source_lang: Source language code

        Returns:
            English text
        """
        if source_lang == "en":
            return text

        result = self.translate(text, source_lang, "en")
        return result if result else text

    def from_english(self, text: str, target_lang: str) -> str:
        """
        Translate English text to target language

        Args:
            text: English text
            target_lang: Target language code

        Returns:
            Translated text
        """
        if target_lang == "en":
            return text

        result = self.translate(text, "en", target_lang)
        return result if result else text

    def is_supported(self, lang_code: str) -> bool:
        """
        Check if language is supported

        Args:
            lang_code: Language code to check

        Returns:
            True if supported, False otherwise
        """
        return lang_code in SUPPORTED_LANGUAGES


# Global singleton instance
_translation_service = None


def get_translation_service() -> TranslationService:
    """
    Get or create global translation service instance

    Returns:
        TranslationService instance
    """
    global _translation_service

    if _translation_service is None:
        _translation_service = TranslationService()

    return _translation_service
