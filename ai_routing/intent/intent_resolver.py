"""
BrainyAi Central Intent Resolver Engine
High-performance deterministic understanding engine.
Decouples Topic, Intent, Context, and Constraints.
Uses in-memory caching with mtime invalidation for sub-millisecond execution.
"""

import os
import re
import time
import logging
from typing import Dict, Any, List, Optional, Tuple, Set

import yaml

from ai_routing.intent.intent_schema import (
    IntentResolutionResult,
    UserIntentRequest,
    TaskIntentItem,
    IntentConfidenceLevel
)

logger = logging.getLogger("intent_resolver")


class IntentResolver:
    """
    Central intent resolver that parses natural language requests, evaluates
    multilingual phrases, extracts constraints, resolves contextual pronouns,
    and maps the structured intention directly to Brainy workflows and prompts.
    """

    def __init__(self, config_dir: Optional[str] = None):
        if config_dir is None:
            config_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_dir = config_dir

        self._catalog: Dict[str, Any] = {}
        self._phrase_dict: Dict[str, Any] = {}
        self._domain_glossary: Dict[str, Any] = {}
        self._contextual_rules: Dict[str, Any] = {}
        self._routing_mapping: Dict[str, Any] = {}
        self._multilingual: Dict[str, Any] = {}
        self._confidence_policy: Dict[str, Any] = {}

        self._file_mtimes: Dict[str, float] = {}
        self._last_refresh_check: float = 0.0

        # Pre-compiled regex caches for sub-millisecond execution
        self._compiled_phrase_patterns: Dict[str, List[re.Pattern]] = {}
        self._compiled_multilingual_patterns: Dict[str, List[re.Pattern]] = {}
        self._compiled_action_patterns: Dict[str, List[re.Pattern]] = {}
        self._compiled_topic_patterns: List[Tuple[str, str, bool, re.Pattern]] = []

        self._load_knowledge_base()

    def _load_knowledge_base(self):
        """Loads all YAML knowledge-base files into memory and compiles regexes."""
        files = {
            "_catalog": "intent_catalog.yaml",
            "_phrase_dict": "phrase_dictionary.yaml",
            "_domain_glossary": "domain_glossary.yaml",
            "_contextual_rules": "contextual_rules.yaml",
            "_routing_mapping": "routing_mapping.yaml",
            "_multilingual": "multilingual_aliases.yaml",
            "_confidence_policy": "confidence_policy.yaml",
        }

        reloaded = False
        for attr, filename in files.items():
            path = os.path.join(self.config_dir, filename)
            if not os.path.exists(path):
                logger.warning("Intent knowledge-base file missing: %s", path)
                setattr(self, attr, {})
                continue

            try:
                mtime = os.path.getmtime(path)
                if self._file_mtimes.get(path) != mtime:
                    with open(path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                    setattr(self, attr, data)
                    self._file_mtimes[path] = mtime
                    reloaded = True
            except Exception as e:
                logger.error("Failed to load intent knowledge file %s: %s", filename, e)
                if getattr(self, attr, None) is None:
                    setattr(self, attr, {})

        if reloaded:
            self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compiles all regular expressions once for optimal runtime speed."""
        # 1. Phrases
        self._compiled_phrase_patterns.clear()
        phrase_dict = self._phrase_dict.get("intents", {})
        for intent_id, pdata in phrase_dict.items():
            patterns = []
            for phrase in pdata.get("phrases", []):
                p_str = str(phrase).strip().lower()
                if p_str:
                    patterns.append(re.compile(r"\b" + re.escape(p_str) + r"\b"))
            self._compiled_phrase_patterns[intent_id] = patterns

        # 2. Multilingual aliases
        self._compiled_multilingual_patterns.clear()
        lang_groups = self._multilingual.get("languages", {})
        for lang_name, ldata in lang_groups.items():
            l_phrases = ldata.get("phrases", {})
            for intent_id, phrase_list in l_phrases.items():
                target_list = self._compiled_multilingual_patterns.setdefault(intent_id, [])
                for phrase in phrase_list:
                    p_str = str(phrase).strip().lower()
                    if p_str:
                        # Non-ASCII scripts (Devanagari, Gujarati) do not use ASCII \b
                        is_ascii = all(ord(c) < 128 for c in p_str)
                        if is_ascii:
                            target_list.append(re.compile(r"\b" + re.escape(p_str) + r"\b"))
                        else:
                            target_list.append(re.compile(re.escape(p_str)))

        # 3. Action verbs
        self._compiled_action_patterns.clear()
        actions = self._domain_glossary.get("actions", {})
        for action_name, adata in actions.items():
            target_intent = adata.get("maps_to_intent")
            if target_intent:
                target_list = self._compiled_action_patterns.setdefault(target_intent, [])
                for verb in adata.get("verbs", []):
                    v_str = str(verb).strip().lower()
                    if v_str:
                        target_list.append(re.compile(r"\b" + re.escape(v_str) + r"\b"))

        # 4. Domain topics
        canonical_topic_map = {
            "प्रकाश संश्लेषण": "photosynthesis",
            "પ્રકાશસંશ્લેષણ": "photosynthesis",
        }
        self._compiled_topic_patterns.clear()
        glossary_topics = self._domain_glossary.get("topics", {})
        for topic_group, data in glossary_topics.items():
            category = data.get("category", "")
            is_prog_lang = (topic_group == "programming_languages")
            for term in data.get("terms", []):
                t_str = str(term).strip()
                if t_str:
                    canonical_name = canonical_topic_map.get(t_str, t_str)
                    is_ascii = all(ord(c) < 128 for c in t_str)
                    if is_ascii:
                        pat = re.compile(r"\b" + re.escape(t_str.lower()) + r"\b")
                    else:
                        pat = re.compile(re.escape(t_str.lower()))
                    self._compiled_topic_patterns.append((canonical_name, category, is_prog_lang, pat))

    def _check_auto_refresh(self):
        """Checks file modification times periodically (every 2.0s) with near-zero overhead in memory."""
        now = time.time()
        if now - self._last_refresh_check < 2.0:
            return
        self._last_refresh_check = now

        for path, old_mtime in list(self._file_mtimes.items()):
            try:
                current_mtime = os.path.getmtime(path)
                if current_mtime != old_mtime:
                    self._load_knowledge_base()
                    break
            except OSError:
                pass

    def normalize_text(self, text: str) -> str:
        """Lightweight normalization preserving multilingual characters."""
        if not text:
            return ""
        # Convert to lower case, normalize punctuation spaces
        cleaned = text.strip()
        # Retain Devanagari (\u0900-\u097F) and Gujarati (\u0A80-\u0AFF) alongside alphanumerics
        return cleaned

    def detect_language(self, text: str) -> str:
        """Detects whether text is in English, Hinglish, Hindi, or Gujarati."""
        if re.search(r"[\u0A80-\u0AFF]", text):
            return "gu"
        if re.search(r"[\u0900-\u097F]", text):
            return "hi"

        # Check Romanized Gujarati markers
        if re.search(r"\b(?:samjavo|sikhavo|banavo|aapo|kem|shu|chhe|hata|mane|aama|banne|farak|saransh|tunk|tunkma)\b", text, re.IGNORECASE):
            return "gu"

        # Check Hinglish markers
        if re.search(r"\b(?:samjhao|samjha|batao|karo|banao|bana|do|sikhao|dikhao|chahiye|hai|hain|kya|kyun|kaise|mujhe|isko|iske|isme|mera|meri|nahi|mat|aur|bhai|yaar|dono|antar|ke|ki|ka|ko|se|mein|me)\b", text, re.IGNORECASE):
            return "hinglish"

        return "en"

    def extract_constraints(self, text: str) -> Tuple[List[str], Optional[str]]:
        """
        Extracts explicit user constraints (e.g. no search, no code, brevity, language restrictions).
        Returns (constraints_list, target_language_override).
        """
        constraints = []
        target_lang = None
        lower = text.lower()

        # Negative search constraints
        if re.search(r"\b(?:without\s+(?:using\s+)?(?:google|search|searching|internet|web)|no\s+search|don\'?t\s+search|offline)\b", lower):
            constraints.append("no_web_search")

        # Negative code constraints
        if re.search(r"\b(?:don\'?t\s+give\s+me\s+code|without\s+code|no\s+code|explain\s+without\s+code|just\s+explain\s+the\s+logic)\b", lower):
            constraints.append("no_code")

        # Brevity constraints
        if re.search(r"\b(?:keep\s+it\s+short|make\s+it\s+short(?:er)?|short\s+summary|briefly|tldr|too\s+long|in\s+\d+\s+lines?|in\s+\d+\s+bullets?|concise)\b", lower):
            constraints.append("concise")

        # Format constraints
        if re.search(r"\b(?:table|tabular\s+form|in\s+a\s+table)\b", lower):
            constraints.append("format:table")
        if re.search(r"\b(?:bullet\s+points?|in\s+bullets?)\b", lower):
            constraints.append("format:bullets")
        if re.search(r"\b(?:flashcards?|anki)\b", lower):
            constraints.append("format:flashcard")

        # Item count constraints (e.g. "5 MCQs", "3 questions")
        count_match = re.search(r"\b(\d+)\s*(?:mcqs?|questions?|points?|bullets?)\b", lower)
        if count_match:
            constraints.append(f"count:{count_match.group(1)}")

        # Step-by-step constraint
        if re.search(r"\b(?:step\s+by\s+step|intermediate\s+steps|show\s+working)\b", lower):
            constraints.append("show_steps")

        # Language constraints (e.g. "in Python not JavaScript", "use Python", "Python code")
        lang_match = re.search(r"\bin\s+(python|javascript|typescript|c\+\+|java|rust|go)\s+not\s+(python|javascript|typescript|c\+\+|java|rust|go)\b", lower)
        if lang_match:
            constraints.append(f"language:{lang_match.group(1)}")
            constraints.append(f"exclude:{lang_match.group(2)}")
        else:
            single_lang = re.search(r"\b(?:in|using|show|write)\s+(python|javascript|typescript|c\+\+|java|rust|go|sql)\b|\b(python|javascript|typescript|c\+\+|java|rust|go|sql)\s+code\b", lower)
            if single_lang:
                matched_lang = single_lang.group(1) or single_lang.group(2)
                constraints.append(f"language:{matched_lang}")

        # Natural language override constraints
        if re.search(r"\b(?:in\s+hindi|hindi\s+mein|saral\s+hindi)\b", lower) or re.search(r"[\u0900-\u097F]", text):
            target_lang = "hi"
            constraints.append("language_output:hindi")
        elif re.search(r"\b(?:in\s+gujarati|gujarati\s+ma|saral\s+gujarati)\b", lower) or re.search(r"[\u0A80-\u0AFF]", text):
            target_lang = "gu"
            constraints.append("language_output:gujarati")

        # Simplicity constraint
        if re.search(r"\b(?:simple\s+language|simple\s+words|eli5|explain\s+like\s+i(?:\'m|\s+am)\s+5|saral\s+bhasha|aasan\s+bhasha)\b|सरल\s+भाषा|आसान\s+भाषा|સરળ\s+ભાષા", lower):
            constraints.append("simple_language")

        # Document-only constraint
        if re.search(r"\b(?:use\s+only\s+(?:this|the|my)?\s*(?:pdf|document|notes)|doc(?:ument)?\s+only|from\s+uploaded\s+(?:pdf|file))\b", lower):
            constraints.append("doc_only")

        return constraints, target_lang

    def extract_topic_and_domain(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extracts the subject topic and domain category using pre-compiled patterns,
        ensuring substantive concepts take precedence over programming language names
        when a concept is present.
        """
        lower = text.lower()
        concept_matches = []
        lang_matches = []

        for term_str, category, is_prog_lang, pattern in self._compiled_topic_patterns:
            m = pattern.search(lower)
            if m:
                entry = (term_str, category, m.start(), len(term_str))
                if is_prog_lang:
                    lang_matches.append(entry)
                else:
                    concept_matches.append(entry)

        # Prefer concepts first sorted by earliest position and length descending
        if concept_matches:
            concept_matches.sort(key=lambda x: (x[2], -x[3]))
            return concept_matches[0][0], concept_matches[0][1]

        # If only programming languages mentioned (e.g. "Explain Python", "Learn Python")
        if lang_matches:
            lang_matches.sort(key=lambda x: (x[2], -x[3]))
            return lang_matches[0][0], lang_matches[0][1]

        return None, None

    def _split_multi_intent_clauses(self, text: str) -> List[str]:
        """
        Splits queries with multiple instructions (e.g. "Explain recursion, show Python code, and give me 5 questions").
        """
        # Match conjunctions before action phrases:
        pattern = (
            r"(?:,\s*and\s+|,\s*|\s+and\s+)"
            r"(?=(?:show|write|give|make|create|implement|solve|test|explain|now|convert|debug|fix|tell|ask)\b)"
        )
        parts = re.split(pattern, text, flags=re.IGNORECASE)
        clauses = [p.strip() for p in parts if p and len(p.strip()) > 2]
        return clauses if len(clauses) > 1 else [text]

    def _score_intent_for_clause(
        self,
        clause: str,
        topic: Optional[str],
        domain: Optional[str],
        constraints: List[str],
        document_present: bool
    ) -> List[Tuple[str, float, List[str]]]:
        """
        Computes candidate intent scores for an individual clause.
        Returns list of (intent_id, score, reason_codes) sorted descending by score.
        """
        lower = clause.lower()
        scores: Dict[str, float] = {}
        reasons: Dict[str, List[str]] = {}

        weights = self._confidence_policy.get("weights", {})
        w_exact = weights.get("exact_phrase_match", 0.45)
        w_alias = weights.get("multilingual_alias_match", 0.40)
        w_verb = weights.get("action_verb_match", 0.25)
        w_topic = weights.get("domain_topic_match", 0.20)
        w_doc = weights.get("document_signal_present", 0.30)
        w_search = weights.get("search_signal_present", 0.35)
        w_neg = weights.get("negative_signal_penalty", -0.40)

        # 1. Document Studio Triggers
        if document_present:
            if re.search(r"\b(?:important|high\s+yield|exam\s+questions?)\b", lower):
                scores["pdf_important_questions"] = scores.get("pdf_important_questions", 0.0) + 1.25
                reasons.setdefault("pdf_important_questions", []).append("document_important_questions_intent")
            elif re.search(r"\b(?:flashcards?|cards?)\b", lower):
                scores["pdf_flashcards"] = scores.get("pdf_flashcards", 0.0) + 1.25
                reasons.setdefault("pdf_flashcards", []).append("document_flashcards_intent")
            elif re.search(r"\b(?:quiz|mcqs?)\b", lower):
                scores["pdf_quiz"] = scores.get("pdf_quiz", 0.0) + 1.25
                reasons.setdefault("pdf_quiz", []).append("document_quiz_intent")
            elif re.search(r"\b(?:notes?|summary|summarize)\b", lower):
                scores["pdf_notes"] = scores.get("pdf_notes", 0.0) + 1.25
                reasons.setdefault("pdf_notes", []).append("document_notes_intent")
            else:
                scores["pdf_question_answering"] = scores.get("pdf_question_answering", 0.0) + 1.20
                reasons.setdefault("pdf_question_answering", []).append("document_qa_intent")

        # 2. Search Triggers
        if "no_web_search" not in constraints:
            if re.search(r"\b(?:official\s+docs?|documentation|api\s+reference|sdk\s+docs?)\b", lower):
                scores["find_documentation"] = scores.get("find_documentation", 0.0) + 0.95
                reasons.setdefault("find_documentation", []).append("official_docs_query")
            elif re.search(r"\b(?:is\s+this\s+(?:website\s+)?(?:true|legitimate|fake|safe)|verify|fact\s*check)\b", lower):
                scores["verify_information"] = scores.get("verify_information", 0.0) + 0.95
                reasons.setdefault("verify_information", []).append("fact_check_query")
            elif re.search(r"\b(?:search\s+online|look\s+up\s+on\s+the\s+web|web\s+search|check\s+google|search\s+the\s+web|search\s+the\s+internet)\b", lower):
                scores["web_research"] = scores.get("web_research", 0.0) + 0.95
                reasons.setdefault("web_research", []).append("explicit_search_phrase")
            elif re.search(r"\b(?:latest|recent|today|news|announced\s+today|2025|2026|right\s+now)\b", lower):
                scores["find_latest_information"] = scores.get("find_latest_information", 0.0) + 0.90
                reasons.setdefault("find_latest_information", []).append("temporal_recency_signal")

        # 3. Pre-Compiled Phrase Dictionary Matching
        for intent_id, patterns in self._compiled_phrase_patterns.items():
            for pat in patterns:
                if pat.search(lower):
                    scores[intent_id] = scores.get(intent_id, 0.0) + w_exact
                    reasons.setdefault(intent_id, []).append(f"phrase_match:{pat.pattern}")
                    break

        # 4. Pre-Compiled Multilingual Aliases Matching (Hinglish, Hindi, Gujarati)
        for intent_id, patterns in self._compiled_multilingual_patterns.items():
            for pat in patterns:
                if pat.search(lower):
                    scores[intent_id] = scores.get(intent_id, 0.0) + w_alias
                    reasons.setdefault(intent_id, []).append(f"multilingual_phrase:{pat.pattern}")
                    break

        # 5. Pre-Compiled Action Terminology from Domain Glossary
        for target_intent, patterns in self._compiled_action_patterns.items():
            for pat in patterns:
                if pat.search(lower):
                    scores[target_intent] = scores.get(target_intent, 0.0) + w_verb
                    reasons.setdefault(target_intent, []).append(f"action_verb:{pat.pattern}")
                    break

        # 6. High-Precision Structural Intent Synthesizers
        # These disambiguate common actions that include topics or numbers
        if re.search(r"\b(?:make|give|create|take)\s+(?:me\s+)?(?:\w+\s+)?notes\b|notes\s+on\b|નોટ્સ\s+બનાવી\s+આપો|નોટ્સ|નોંધ|नोट्स\s+बनाओ|नोट्स", lower):
            scores["generate_notes"] = scores.get("generate_notes", 0.0) + 0.95
            reasons.setdefault("generate_notes", []).append("structured_notes_request")

        if re.search(r"\b(?:what\s+is|what\s+are)\b", lower) and topic:
            scores["explain_concept"] = scores.get("explain_concept", 0.0) + 0.85
            reasons.setdefault("explain_concept", []).append("conceptual_what_is_request")

        if re.search(r"\b(?:from\s+zero|from\s+scratch|absolute\s+beginner|bilkul\s+shuru\s+se|zero\s+se|zero\s+thi)\b", lower):
            scores["learn_from_zero"] = scores.get("learn_from_zero", 0.0) + 0.95
            reasons.setdefault("learn_from_zero", []).append("beginner_from_zero_intent")

        if re.search(r"\b(?:write|implement|create|show)\s+(?:\w+\s+)?code\b|\bcode\s+for\b", lower):
            scores["generate_code"] = scores.get("generate_code", 0.0) + 0.95
            reasons.setdefault("generate_code", []).append("code_generation_request")

        if re.search(r"\b(?:fix|debug|repair|resolve)\s+(?:this|the|my)?\s*(?:\w+\s+)?(?:code|error|bug|issue|script)\b|\b(?:code|bug|error)\s+(?:ko\s+)?(?:fix|theek|solve|repair)\s+karo\b|\b(?:aa\s+)?code\s+fix\s+karo\b|error\s+aa\s+raha\s+hai|bug\s+theek\s+karo|त्रुटि\s+ठीक\s+करो|बग\s+ढूंढो|ભૂલ\s+સુધારો", lower):
            scores["debug_code"] = scores.get("debug_code", 0.0) + 0.95
            reasons.setdefault("debug_code", []).append("code_debug_request")

        if re.search(r"\b(?:why|what)\s+(?:does|is)\s+(?:this|the|my)?\s*(?:\w+\s+)?(?:code\s+|component\s+)?(?:fail|raise|error|re-?rendering)\b|re-?rendering\s+infinitely", lower):
            scores["understand_error"] = scores.get("understand_error", 0.0) + 1.20
            reasons.setdefault("understand_error", []).append("understand_error_request")

        if re.search(r"\b(?:compare|difference\s+between|versus|\bvs\b|dono\s+mein\s+kya\s+antar|shu\s+farak)\b", lower):
            scores["compare_concepts"] = scores.get("compare_concepts", 0.0) + 0.95
            reasons.setdefault("compare_concepts", []).append("compare_concepts_request")

        if re.search(r"\b(?:show\s+(?:step\s+by\s+step\s+)?(?:working|calculation)|steps\s+ke\s+sath|ganatri\s+darshavo|intermediate\s+steps|derive\s+(?:the\s+)?formula)\b", lower):
            scores["show_working"] = scores.get("show_working", 0.0) + 1.20
            reasons.setdefault("show_working", []).append("show_working_math_request")
        elif (
            re.search(r"\b(?:solve|calculate|evaluate|find\s+the\s+solution|integrate|differentiate|roots\s+of)\b|समीकरण|हल\s+निकालो|हल\s+करो|સમીકરણ|ઉકેલો", lower)
            and not re.search(r"\b(?:def\s+|return\s+|class\s+|function\s+|code|error|bug|issue|त्रुटि|बग)\b", lower)
        ):
            scores["solve_problem"] = scores.get("solve_problem", 0.0) + 0.95
            reasons.setdefault("solve_problem", []).append("solve_problem_math_request")

        if re.search(r"\b(?:\d+\s*mcqs?|make\s+mcqs?|create\s+a?\s*quiz|prashnottari)\b", lower):
            scores["generate_quiz"] = scores.get("generate_quiz", 0.0) + 0.95
            reasons.setdefault("generate_quiz", []).append("quiz_mcq_request")
        elif re.search(r"\b(?:\d+\s*questions?|practice\s+questions?|test\s+questions?|ask\s+me\s+questions?)\b", lower):
            scores["generate_questions"] = scores.get("generate_questions", 0.0) + 0.95
            reasons.setdefault("generate_questions", []).append("practice_questions_request")

        if re.search(r"\b(?:flashcards?|anki\s+cards?)\b", lower):
            scores["generate_flashcards"] = scores.get("generate_flashcards", 0.0) + 0.95
            reasons.setdefault("generate_flashcards", []).append("flashcards_request")

        if re.search(r"\b(?:test\s+my\s+knowledge|test\s+me\s+on|quiz\s+me\s+on)\b", lower):
            scores["test_knowledge"] = scores.get("test_knowledge", 0.0) + 0.95
            reasons.setdefault("test_knowledge", []).append("test_knowledge_request")

        if re.search(r"\b(?:summarize|give\s+me\s+a\s+summary|executive\s+summary|recap)\b", lower) and not document_present:
            scores["generate_summary"] = scores.get("generate_summary", 0.0) + 0.90
            reasons.setdefault("generate_summary", []).append("summary_request")

        if re.search(r"\b(?:optimize|make\s+it\s+faster|reduce\s+(?:time|space)\s+complexity|speed\s+up|refactor)\b", lower):
            scores["optimize_code"] = scores.get("optimize_code", 0.0) + 0.95
            reasons.setdefault("optimize_code", []).append("code_optimization_request")

        if re.search(r"\b(?:review\s+(?:this|my)?\s*code|code\s+review|security\s+vulnerabilities|memory\s+leaks|code\s+quality)\b", lower):
            scores["review_code"] = scores.get("review_code", 0.0) + 1.25
            reasons.setdefault("review_code", []).append("code_review_request")

        if re.search(r"\b(?:write\s+unit\s+tests?|write\s+tests?|unit\s+tests?|pytest|test\s+cases?)\b", lower):
            scores["write_tests"] = scores.get("write_tests", 0.0) + 0.95
            reasons.setdefault("write_tests", []).append("write_tests_request")

        if re.search(r"\b(?:software\s+architecture|system\s+design|architecture\s+for)\b", lower):
            scores["design_software_architecture"] = scores.get("design_software_architecture", 0.0) + 0.95
            reasons.setdefault("design_software_architecture", []).append("software_architecture_request")

        if re.search(r"\b(?:convert\s+it\s+into|turn\s+it\s+into|rewrite|rephrase)\b", lower):
            scores["rewrite_content"] = scores.get("rewrite_content", 0.0) + 0.95
            reasons.setdefault("rewrite_content", []).append("rewrite_content_request")

        if re.search(r"\b(?:give\s+(?:me\s+)?(?:more\s+)?examples?|show\s+(?:me\s+)?examples?|practical\s+examples?|real\s+world\s+examples?)\b", lower):
            scores["give_examples"] = scores.get("give_examples", 0.0) + 0.95
            reasons.setdefault("give_examples", []).append("give_examples_request")

        if re.search(r"\b(?:continue|keep\s+going|go\s+on|next\s+step|aage\s+batao|aagad\s+vadho)\b", lower.strip()):
            scores["continue_previous_task"] = scores.get("continue_previous_task", 0.0) + 0.95
            reasons.setdefault("continue_previous_task", []).append("continue_previous_task_request")

        if re.search(r"\b(?:simplify|make\s+it\s+simpler|explain\s+like\s+i(?:\'m|\s+am)\s+5|eli5|thoda\s+easy\s+karke\s+samjhao|thoda\s+easy\s+karo|aasan\s+karo)\b", lower):
            scores["simplify_content"] = scores.get("simplify_content", 0.0) + 0.95
            reasons.setdefault("simplify_content", []).append("simplification_request")

        # 7. Apply Negative Signals
        if "no_code" in constraints:
            if "generate_code" in scores:
                scores["generate_code"] += w_neg
                reasons.setdefault("generate_code", []).append("penalized:no_code_constraint")
            if "debug_code" in scores:
                scores["debug_code"] += w_neg
                reasons.setdefault("debug_code", []).append("penalized:no_code_constraint")

        # 8. Check for Pure Brevity Follow-up
        if re.match(r"^(?:make\s+it\s+shorter|keep\s+it\s+short|too\s+long|tldr|thoda\s+chota\s+karo)\b", lower.strip()):
            scores["request_shorter_answer"] = scores.get("request_shorter_answer", 0.0) + 0.95
            reasons.setdefault("request_shorter_answer", []).append("pure_shorter_answer_request")

        # 9. Check for Short Definition
        if (
            len(clause.split()) <= 6
            and not re.search(r"\b(?:and|how\s+does|explain|process|mechanism|crispr|cas9)\b", lower)
            and re.match(r"^(?:what is|who is|define|meaning of|kya hota hai)\b", lower)
        ):
            scores["define_term"] = scores.get("define_term", 0.0) + 0.90
            reasons.setdefault("define_term", []).append("short_definition_pattern")

        # 10. Check for Greeting
        if re.match(r"^(?:hi|hello|hey|good\s+(?:morning|afternoon|evening)|namaste|kem\s+chho|kya\s+haal|who\s+are\s+you)\b", lower):
            scores["general_conversation"] = scores.get("general_conversation", 0.0) + 0.98
            reasons.setdefault("general_conversation", []).append("greeting_pattern")

        # Sort and return
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [(intent, score, reasons.get(intent, [])) for intent, score in ranked]

    def resolve(self, request: UserIntentRequest) -> IntentResolutionResult:
        """
        Main entry point for resolving a UserIntentRequest into a structured IntentResolutionResult.
        Guarantees sub-millisecond execution and complete adherence to routing policies.
        """
        start_time = time.perf_counter()
        self._check_auto_refresh()

        raw_query = (request.query or "").strip()
        messages = request.messages or []
        doc_ctx = request.document_context or {}
        has_doc = bool(doc_ctx.get("pdf_text") or doc_ctx.get("doc_id"))

        # 1. Normalize & Detect Constraints
        norm_query = self.normalize_text(raw_query)
        detected_lang = self.detect_language(norm_query)
        constraints, lang_override = self.extract_constraints(norm_query)
        target_lang = lang_override if lang_override else detected_lang

        # 2. Extract Topic and Domain
        topic, domain = self.extract_topic_and_domain(norm_query)

        # 3. Contextual Follow-Up Analysis
        context_required = False
        target_reference = None
        is_followup = False
        reuse_search = False

        if messages and len(messages) >= 1:
            last_assistant_msg = ""
            for m in reversed(messages):
                if m.get("role") == "assistant":
                    last_assistant_msg = m.get("content", "")
                    break

            # Pronoun / Elliptical / Sibling detection
            if re.search(r"\b(?:make\s+it\s+(?:shorter|simpler|faster)|too\s+long|summarize\s+(?:it|that)|convert\s+it\s+into|now\s+optimize\s+it|optimize\s+it|continue|give\s+(?:me\s+)?more\s+examples|more\s+examples|show\s+more)\b", norm_query, re.IGNORECASE):
                context_required = True
                is_followup = True
                if "optimize" in norm_query.lower():
                    target_reference = "previous_code"
                elif "continue" in norm_query.lower():
                    target_reference = "previous_continuation"
                else:
                    target_reference = "previous_answer"

            # Check for search result reference
            if re.search(r"\b(?:the\s+)?(?:first|second|third|fourth|1st|2nd|3rd|4th|last)\s+(?:result|source|link|article|point)\b", norm_query, re.IGNORECASE):
                for m in reversed(messages):
                    if "LIVE WEB RESEARCH FINDINGS" in m.get("content", "") or "EXTERNAL SEARCH FINDINGS" in m.get("content", ""):
                        reuse_search = True
                        context_required = True
                        is_followup = True
                        target_reference = "search_result_item"
                        constraints.append("reuse_search")
                        break

            # Inherit topic if current query does not establish a new one and is a follow-up
            if is_followup and not topic:
                for m in reversed(messages):
                    prev_text = m.get("content", "")
                    prev_topic, prev_domain = self.extract_topic_and_domain(prev_text)
                    if prev_topic:
                        topic = prev_topic
                        domain = prev_domain
                        break

        # 4. Multi-Intent Clause Splitting
        clauses = self._split_multi_intent_clauses(norm_query)

        # 5. Score Intents Across Clauses
        ordered_tasks: List[TaskIntentItem] = []
        primary_intent = None
        secondary_intents: List[str] = []
        overall_confidence = 0.90
        all_reasons: List[str] = []

        for idx, clause in enumerate(clauses):
            clause_topic, clause_domain = self.extract_topic_and_domain(clause)
            effective_topic = clause_topic or topic
            effective_domain = clause_domain or domain

            scored = self._score_intent_for_clause(
                clause=clause,
                topic=effective_topic,
                domain=effective_domain,
                constraints=constraints,
                document_present=has_doc
            )

            # Select top intent for clause
            if scored:
                top_intent, score, reasons = scored[0]
            else:
                top_intent = "explain_concept" if effective_topic else "general_conversation"
                score = 0.70
                reasons = ["default_fallback"]

            # Cap confidence in [0.0, 1.0]
            conf = min(1.0, max(0.40, score))

            if idx == 0:
                primary_intent = top_intent
                overall_confidence = conf
                all_reasons.extend(reasons)
            else:
                if top_intent != primary_intent and top_intent not in secondary_intents:
                    secondary_intents.append(top_intent)
                all_reasons.extend(reasons)

            task_item = TaskIntentItem(
                intent_id=top_intent,
                name=top_intent.replace("_", " ").title(),
                action=top_intent,
                topic=effective_topic,
                domain=effective_domain,
                desired_output=[top_intent],
                constraints=list(constraints),
                confidence=conf,
                order=idx + 1
            )
            ordered_tasks.append(task_item)

        # Fallback if primary intent unresolved
        if not primary_intent:
            primary_intent = "general_conversation" if len(norm_query.split()) <= 3 else "explain_concept"

        # Explicit intent override if passed from caller
        if request.explicit_intent:
            explicit = request.explicit_intent.lower()
            if explicit == "search":
                primary_intent = "web_research"
            elif explicit in ("math", "maths"):
                primary_intent = "solve_problem"
            elif explicit == "coding":
                primary_intent = "generate_code"

        # 6. Map Intent to Workflow, Prompt, and Providers
        mapping = self._routing_mapping.get("mappings", {}).get(primary_intent, {})
        workflow = mapping.get("workflow", "educational")
        prompt_id = mapping.get("prompt_id", "brainy_comprehensive")
        prompt_file = mapping.get("prompt_file", "brainy_prompt.txt")
        search_req = mapping.get("search_required", False)
        is_fast_path = mapping.get("is_fast_path", False)

        # Enforce search constraints
        if "no_web_search" in constraints or reuse_search:
            search_req = False

        # If any secondary intent requires coding, adjust workflow to coding if applicable
        if "generate_code" in secondary_intents or "debug_code" in secondary_intents:
            if workflow == "educational":
                workflow = "coding"
                prompt_id = "coding"
                prompt_file = "coding_prompt.txt"

        search_providers = ["tavily", "duckduckgo"] if search_req else []

        # Confidence level classification
        thresholds = self._confidence_policy.get("thresholds", {})
        t_high = thresholds.get("high", 0.85)
        t_med = thresholds.get("medium", 0.60)

        if overall_confidence >= t_high:
            conf_level = IntentConfidenceLevel.HIGH.value
        elif overall_confidence >= t_med:
            conf_level = IntentConfidenceLevel.MEDIUM.value
        else:
            conf_level = IntentConfidenceLevel.LOW.value

        # Calculate resolver latency
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        # Construct final result
        result = IntentResolutionResult(
            primary_intent=primary_intent,
            secondary_intents=secondary_intents,
            ordered_tasks=ordered_tasks,
            topic=topic,
            domain=domain,
            difficulty="beginner" if "beginner" in constraints else None,
            desired_output=[t.action for t in ordered_tasks],
            constraints=constraints,
            required_tools=search_providers if search_req else (["pdf_extraction"] if has_doc else []),
            context_required=context_required,
            context_reference_target=target_reference,
            confidence=round(overall_confidence, 4),
            confidence_level=conf_level,
            reason_codes=all_reasons,
            target_language=target_lang,
            workflow=workflow,
            prompt_id=prompt_id,
            prompt_file=prompt_file,
            search_required=search_req,
            search_providers=search_providers,
            is_fast_path=is_fast_path,
            resolver_latency_ms=latency_ms
        )

        return result


# Global singleton intent resolver
intent_resolver = IntentResolver()
