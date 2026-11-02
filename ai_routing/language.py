"""
Unified Language Intelligence Module for Brainy
Handles deterministic script detection, Hinglish recognition, Gujarati detection,
and explicit language preference routing.
Ensures models reply in natural Roman-script Hinglish for Hinglish inputs,
never inappropriately translating into formal Hindi/Devanagari,
and preserves technical terms in English.
"""

import re
from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class LanguageProfile:
    language: str       # "english", "hinglish", "hindi", "gujarati", "other"
    script: str         # "latin", "devanagari", "gujarati", "mixed"
    confidence: float   # 0.0 to 1.0
    explicit_target: Optional[str] = None  # User explicitly requested language
    directive: str = "" # System prompt instruction snippet


# Common Hinglish/Romanized Hindi token patterns (high precision)
_HINGLISH_PATTERNS = [
    r"\b(?:kya|hai|hain|samjha|samjhao|samajh|kaise|kyu|kyun|ye|yeh|wo|woh)\b",
    r"\b(?:mera|meri|mere|tera|teri|tere|apna|apni|apne|mujhe|tujhe|hume|hum)\b",
    r"\b(?:nahi|nahin|karo|karna|karega|karegi|karta|karti|karte|kar do|kar|kijiye)\b",
    r"\b(?:wala|wali|wale|chahiye|hota|hoti|hote|de do|batao|batado|bata|bataiye|bata do na|bata do)\b",
    r"\b(?:shikha|sikha|sikhna|seekhna|padhna|padhao|samjhado|aa raha|ho raha)\b",
    r"\b(?:lekin|par|magar|aur|ya|ke liye|se|ko|mein|me|pe|bhi|toh|to|hi|na|ke)\b",
    r"\b(?:bhai|yaar|dost|sir|aap|tum|log|waala|theek|sahi|galat|achha|accha)\b",
    r"\b(?:kuch|sab|aisa|waisa|itna|utna|kitna|jyada|zyada|kam|bohot|bahut)\b",
    r"\b(?:aaj|kal|parso|abhi|baad|pehle|jaldi|aaram|batao|suno|dekho)\b",
]
_HINGLISH_REGEX = re.compile("|".join(_HINGLISH_PATTERNS), re.IGNORECASE)

# Common Gujarati Romanized words (Gujlish)
_GUJARATI_ROMAN_PATTERNS = [
    r"\b(?:kem|cho|tame|shu|nathi|mane|tane|amne|tamne|maru|tamaru|aapnu)\b",
    r"\b(?:samjavone|samjavo|samjhavo|samjhavone|madad|karo|karjo|aapo|lakho)\b",
    r"\b(?:rite|karvu|karvo|aavse|aave|bhai|tamare|maare|kevi|kevo)\b",
    r"\b(?:ane|pan|athva|ma|thi|par|mate|joie|nathi)\b",
]
_GUJARATI_ROMAN_REGEX = re.compile("|".join(_GUJARATI_ROMAN_PATTERNS), re.IGNORECASE)

# Explicit user instructions to answer in a particular language
_EXPLICIT_ENGLISH_REGEX = re.compile(
    r"\b(?:answer|explain|reply|write|respond|teach)\s+(?:in|using)\s+english\b|"
    r"\benglish\s+(?:me|mein|ma)\s+(?:dena|batao|samjhao|likho|answer|reply|explain|bol)\b|"
    r"\b(?:translate\s+(?:this\s+)?(?:to|into)\s+english|english\s+translation)\b|"
    r"\b(?:in|into)\s+english\b|"
    r"\b(?:in\s+english\s+only|only\s+in\s+english|in\s+plain\s+english)\b",
    re.IGNORECASE
)

_EXPLICIT_HINGLISH_REGEX = re.compile(
    r"\b(?:answer|explain|reply|write|respond|teach)\s+(?:in|using)\s+hinglish\b|"
    r"\bhinglish\s+(?:me|mein|ma)\s+(?:dena|batao|samjhao|likho|bol)\b|"
    r"\b(?:in|into)\s+hinglish\b|"
    r"\b(?:in\s+hinglish\s+only|only\s+in\s+hinglish)\b",
    re.IGNORECASE
)

_EXPLICIT_HINDI_REGEX = re.compile(
    r"\b(?:answer|explain|reply|write|respond|teach)\s+(?:in|using)\s+hindi\b|"
    r"\bhindi\s+(?:me|mein|ma)\s+(?:dena|batao|samjhao|likho|bol)\b|"
    r"\b(?:translate\s+(?:this\s+)?(?:to|into)\s+hindi|hindi\s+translation)\b|"
    r"\b(?:in|into)\s+hindi\b|"
    r"\b(?:in\s+hindi\s+only|only\s+in\s+hindi)\b",
    re.IGNORECASE
)

_EXPLICIT_GUJARATI_REGEX = re.compile(
    r"\b(?:answer|explain|reply|write|respond|teach)\s+(?:in|using)\s+gujarati\b|"
    r"\bgujarati\s+(?:ma|me|mein)\s+(?:samjavo|aapo|lakho|bol|dena|batao)\b|"
    r"\b(?:translate\s+(?:this\s+)?(?:to|into)\s+gujarati|gujarati\s+translation)\b|"
    r"\b(?:in|into)\s+gujarati\b|"
    r"\b(?:in\s+gujarati\s+only|only\s+in\s+gujarati)\b",
    re.IGNORECASE
)


def detect_language(text: str) -> LanguageProfile:
    """
    Analyzes the user's text for language, script, and explicit language constraints.
    Returns a LanguageProfile with the appropriate system prompt directive.
    """
    clean = (text or "").strip()
    if not clean:
        return LanguageProfile(
            language="english",
            script="latin",
            confidence=1.0,
            directive="Respond in clear, natural English."
        )

    # 1. Check for explicit language requests first
    if _EXPLICIT_ENGLISH_REGEX.search(clean):
        return LanguageProfile(
            language="english",
            script="latin",
            confidence=0.98,
            explicit_target="english",
            directive=(
                "CRITICAL LANGUAGE RULE: The user explicitly requested English. "
                "You MUST reply in clear, natural English regardless of the question's source language."
            )
        )

    if _EXPLICIT_HINGLISH_REGEX.search(clean):
        return LanguageProfile(
            language="hinglish",
            script="latin",
            confidence=0.98,
            explicit_target="hinglish",
            directive=(
                "CRITICAL LANGUAGE RULE: The user explicitly requested Hinglish.\n"
                "1. Respond in natural, conversational Hinglish using ONLY the Latin/Roman script (English letters).\n"
                "2. NEVER use Devanagari script under any circumstances.\n"
                "3. Keep all academic, technical, scientific, and mathematical terms in standard English.\n"
                "4. Example: 'Newton ka third law kehta hai ki har action ka ek equal and opposite reaction hota hai.'"
            )
        )

    if _EXPLICIT_HINDI_REGEX.search(clean):
        return LanguageProfile(
            language="hindi",
            script="devanagari",
            confidence=0.98,
            explicit_target="hindi",
            directive=(
                "CRITICAL LANGUAGE RULE: The user explicitly requested Hindi. "
                "Respond in clear, accessible Hindi using Devanagari script. Keep core technical terms in English where appropriate."
            )
        )

    if _EXPLICIT_GUJARATI_REGEX.search(clean):
        return LanguageProfile(
            language="gujarati",
            script="gujarati",
            confidence=0.98,
            explicit_target="gujarati",
            directive=(
                "CRITICAL LANGUAGE RULE: The user explicitly requested Gujarati. "
                "Respond in clear, natural Gujarati. Keep technical terms in English where appropriate."
            )
        )

    # 2. Check for native scripts (Unicode blocks)
    # Devanagari: \u0900-\u097F
    devanagari_chars = len(re.findall(r"[\u0900-\u097F]", clean))
    # Gujarati: \u0A80-\u0AFF
    gujarati_chars = len(re.findall(r"[\u0A80-\u0AFF]", clean))
    total_alpha = len(re.findall(r"\w", clean)) or 1

    if gujarati_chars / total_alpha > 0.15:
        return LanguageProfile(
            language="gujarati",
            script="gujarati",
            confidence=0.95,
            directive=(
                "The user wrote in Gujarati using the Gujarati script. "
                "Respond naturally in clear Gujarati script. Keep technical terms in English."
            )
        )

    if devanagari_chars / total_alpha > 0.15:
        return LanguageProfile(
            language="hindi",
            script="devanagari",
            confidence=0.95,
            directive=(
                "The user wrote in Hindi using Devanagari script. "
                "Respond naturally in clear Hindi using Devanagari script. Keep core technical terms in English."
            )
        )

    # 3. Text is primarily in Latin/Roman script -> Distinguish English vs. Hinglish vs. Gujlish
    guj_roman_matches = len(_GUJARATI_ROMAN_REGEX.findall(clean))
    hinglish_matches = len(_HINGLISH_REGEX.findall(clean))
    words = re.findall(r"\b\w+\b", clean.lower())
    total_words = len(words) or 1

    if guj_roman_matches >= 2 or (guj_roman_matches >= 1 and guj_roman_matches / total_words >= 0.15):
        return LanguageProfile(
            language="gujarati",
            script="latin",
            confidence=0.90,
            directive=(
                "The user wrote in conversational Gujarati in Roman script (Gujlish). "
                "Respond in natural, friendly Gujarati or Roman Gujarati according to context, keeping technical terms in English."
            )
        )

    # If 2 or more Hinglish indicator words, or 1 indicator word in a short query (<= 8 words)
    if hinglish_matches >= 2 or (hinglish_matches >= 1 and (total_words <= 8 or hinglish_matches / total_words >= 0.15)):
        return LanguageProfile(
            language="hinglish",
            script="latin",
            confidence=0.95,
            directive=(
                "CRITICAL LANGUAGE RULE: The user asked in Hinglish (Roman-script Hindi/Urdu written with English alphabet).\n"
                "1. You MUST reply in natural, conversational Hinglish using ONLY the Latin/Roman script (English letters).\n"
                "2. NEVER translate into formal Hindi or output Devanagari script.\n"
                "3. Keep all academic concepts, formulas, scientific laws, definitions, and technical terminology in standard English.\n"
                "4. Tone: Helpful, enthusiastic study buddy explaining concepts clearly.\n"
                "5. Example of proper Hinglish: 'Photosynthesis ek aisi biological process hai jisme plants sunlight ko use karke glucose banate hain.'"
            )
        )

    # Default to English
    return LanguageProfile(
        language="english",
        script="latin",
        confidence=0.95,
        directive="Respond in clear, accurate, natural English. Format equations and steps with high legibility."
    )


def apply_language_directive(base_prompt: str, user_text_or_profile: Any) -> str:
    """
    Appends the deterministic language directive to any base system prompt.
    Accepts either raw user text (str) or a pre-computed LanguageProfile.
    """
    if isinstance(user_text_or_profile, LanguageProfile):
        profile = user_text_or_profile
    else:
        profile = detect_language(user_text_or_profile)

    directive_block = f"""
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DETERMINISTIC LANGUAGE & SCRIPT DIRECTIVE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Detected Language: {profile.language.upper()} (Script: {profile.script.upper()})
{profile.directive}
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    # If the base prompt already has this language directive, avoid duplicate stacking
    if "DETERMINISTIC LANGUAGE & SCRIPT DIRECTIVE" in base_prompt:
        # Replace existing directive block
        pattern = re.compile(
            r"# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\s*"
            r"# DETERMINISTIC LANGUAGE & SCRIPT DIRECTIVE.*?"
            r"# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            re.DOTALL
        )
        return pattern.sub(directive_block.strip(), base_prompt)

    return f"{base_prompt.rstrip()}\n\n{directive_block.strip()}"
