"""
Item name translation utilities for Diablo 4 unique items.

This module provides functionality to translate equipment names between
English, Simplified Chinese, and Traditional Chinese.
"""

import json
import logging
import os
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

ITEM_TRANSLATION_FILE = "all_items.json"


class ItemTranslator:
    """Handles translation of Diablo 4 unique item names between languages."""
    
    def __init__(self, translation_file: str = ITEM_TRANSLATION_FILE):
        """
        Initialize the item translator.
        
        Args:
            translation_file: Path to the JSON file containing item translations.
        """
        self.translation_file = translation_file
        self.item_translations: List[Dict[str, str]] = []
        self.english_canonical_map: Dict[str, str] = {}
        self.chinese_to_english_map: Dict[str, str] = {}
        self.load_translations()
    
    def load_translations(self) -> None:
        """Load localized unique item names for lookup and display."""
        if not os.path.exists(self.translation_file):
            logger.warning("Item translation file not found: %s", self.translation_file)
            self.item_translations = []
            self.english_canonical_map = {}
            self.chinese_to_english_map = {}
            return

        try:
            with open(self.translation_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            logger.error("Failed to load item translations: %s", exc)
            self.item_translations = []
            self.english_canonical_map = {}
            self.chinese_to_english_map = {}
            return

        self.item_translations = []
        self.english_canonical_map = {}
        self.chinese_to_english_map = {}

        for entry in data:
            if not isinstance(entry, dict):
                continue

            english = (entry.get("english") or "").strip()
            simplified = (entry.get("simplified") or "").strip()
            traditional = (entry.get("traditional") or "").strip()

            if not english:
                continue

            self.item_translations.append({
                "english": english,
                "simplified": simplified,
                "traditional": traditional
            })

            # Build case-insensitive lookup maps
            self.english_canonical_map[english.casefold()] = english

            for localized_name in (simplified, traditional):
                if localized_name:
                    self.chinese_to_english_map[localized_name.casefold()] = english or localized_name

        logger.info(
            f"Loaded {len(self.item_translations)} item translations "
            f"({len(self.chinese_to_english_map)} Chinese mappings)"
        )

    def get_canonical_name(self, query: str) -> Tuple[str, bool]:
        """
        Resolve a user query to the canonical English item name.
        
        Args:
            query: The equipment name to search for (in any language).
            
        Returns:
            A tuple of (canonical_english_name, is_chinese_input).
            If no match is found, returns the original query.
        """
        normalized = query.casefold()

        # Check for exact Chinese match first
        if normalized in self.chinese_to_english_map:
            return self.chinese_to_english_map[normalized], True

        # Check for exact English match
        if normalized in self.english_canonical_map:
            return self.english_canonical_map[normalized], False

        # Fallback: partial match search
        for entry in self.item_translations:
            english = (entry.get("english") or "").strip()
            simplified = (entry.get("simplified") or "").strip()
            traditional = (entry.get("traditional") or "").strip()

            if simplified and normalized in simplified.casefold():
                return english or simplified, True

            if traditional and normalized in traditional.casefold():
                return english or traditional, True

            if english and normalized in english.casefold():
                return english, False

        return query, False
    
    def translate_to_english(self, name: str) -> str:
        """
        Translate Chinese equipment name to English if possible.
        
        Args:
            name: The equipment name (in any language).
            
        Returns:
            The English name if found, otherwise the original name.
        """
        canonical_name, _ = self.get_canonical_name(name)
        return canonical_name
    
    def get_all_translations(self) -> List[Dict[str, str]]:
        """
        Get all item translations.
        
        Returns:
            A list of dictionaries containing english, simplified, and traditional names.
        """
        return self.item_translations.copy()


# Global singleton instance
_translator_instance: ItemTranslator = None


def get_translator() -> ItemTranslator:
    """
    Get the global ItemTranslator instance (singleton pattern).
    
    Returns:
        The global ItemTranslator instance.
    """
    global _translator_instance
    if _translator_instance is None:
        _translator_instance = ItemTranslator()
    return _translator_instance
