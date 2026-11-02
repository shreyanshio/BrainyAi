"""
BrainyAi Intelligent Task Classification & Response Depth Control
Defines academic, study, scientific, coding, and mathematical task categories,
response-depth modes, and a fast, deterministic, zero-overhead multilingual task classifier.
"""

from enum import Enum
import re
from typing import List, Dict, Any, Optional, Tuple

class TaskType(str, Enum):
    # Core & Educational
    QUICK_CHAT                    = "QUICK_CHAT"
    SIMPLE_EXPLANATION            = "SIMPLE_EXPLANATION"
    DETAILED_EXPLANATION          = "DETAILED_EXPLANATION"
    DEEP_REASONING                = "DEEP_REASONING"

    # Mathematics Specialists
    MATHEMATICS                   = "MATHEMATICS"
    ADVANCED_MATHEMATICS          = "ADVANCED_MATHEMATICS"
    ALGEBRA                       = "ALGEBRA"
    CALCULUS                      = "CALCULUS"
    STATISTICS                    = "STATISTICS"
    MATH_AND_LOGIC                = "MATH_AND_LOGIC"  # Canonical alias

    # Science Specialists
    PHYSICS                       = "PHYSICS"
    CHEMISTRY                     = "CHEMISTRY"
    BIOLOGY                       = "BIOLOGY"
    SCIENCE                       = "SCIENCE"

    # Coding Specialists
    CODING                        = "CODING"
    CODING_DEBUGGING              = "CODING_DEBUGGING"
    CODING_EXPLANATION            = "CODING_EXPLANATION"
    DSA                           = "DSA"
    SQL                           = "SQL"

    # Multimodal & Research
    IMAGE_QUESTION                = "IMAGE_QUESTION"
    DIAGRAM_ANALYSIS              = "DIAGRAM_ANALYSIS"
    WEB_RESEARCH                  = "WEB_RESEARCH"

    # PDF Study Studio Operations
    DOCUMENT_INGESTION            = "DOCUMENT_INGESTION"
    PDF_SUMMARY                   = "PDF_SUMMARY"
    PDF_QUESTION_ANSWERING        = "PDF_QUESTION_ANSWERING"
    NOTE_GENERATION               = "NOTE_GENERATION"
    QUIZ_GENERATION               = "QUIZ_GENERATION"
    FLASHCARD_GENERATION          = "FLASHCARD_GENERATION"
    IMPORTANT_QUESTION_GENERATION = "IMPORTANT_QUESTION_GENERATION"

    # Language & Composition
    TRANSLATION                   = "TRANSLATION"
    WRITING                       = "WRITING"
    CHAT_TITLE_GENERATION         = "CHAT_TITLE_GENERATION"


class ResponseDepth(str, Enum):
    FAST     = "FAST"
    BALANCED = "BALANCED"
    DEEP     = "DEEP"

    @classmethod
    def from_str(cls, val: Optional[str]) -> "ResponseDepth":
        if not val:
            return cls.BALANCED
        v = str(val).strip().upper()
        if v in ("FAST", "SHORT", "QUICK", "CONCISE", "BRIEF"):
            return cls.FAST
        if v in ("DEEP", "LONG", "DETAILED", "THOROUGH", "EXTENSIVE"):
            return cls.DEEP
        return cls.BALANCED


class TaskComplexity(str, Enum):
    FAST     = "FAST"      # Casual greetings, acknowledgments, single-turn chit-chat -> Groq 8B
    LIGHT    = "LIGHT"     # Short definitions, basic facts, simple translations -> Groq 8B / Gemini 3.5 Flash-Lite
    STANDARD = "STANDARD"  # General explanations, tutoring, standard writing -> Gemini 3.8 Flash (med thinking)
    COMPLEX  = "COMPLEX"   # Coding, debugging, DSA, SQL, Science -> Gemini 3.8 Flash (med/high thinking)
    DEEP     = "DEEP"      # Multi-step proofs, architecture, deep reasoning -> Gemini 3.8 Flash (high thinking)

    @classmethod
    def from_str(cls, val: Optional[str]) -> "TaskComplexity":
        if not val:
            return cls.STANDARD
        v = str(val).strip().upper()
        if v in ("FAST", "INSTANT", "TRIVIAL"):
            return cls.FAST
        if v in ("LIGHT", "SIMPLE", "SHORT"):
            return cls.LIGHT
        if v in ("COMPLEX", "HARD"):
            return cls.COMPLEX
        if v in ("DEEP", "ADVANCED", "EXHAUSTIVE"):
            return cls.DEEP
        return cls.STANDARD


# ── REGEX PATTERNS FOR DETERMINISTIC CLASSIFICATION ─────────────────────

# Calculus
_CALCULUS_KEYWORDS = re.compile(
    r"\b(derivative|differential|differentiate|differentiation|integrate|integration|integral|calculus|limits?|series expansion|taylor series|maclaurin|gradient descent|gradient|partial derivative)\b|[\∫\∂]",
    re.IGNORECASE
)

# Algebra
_ALGEBRA_KEYWORDS = re.compile(
    r"\b(algebra|polynomial|quadratic|linear equation|simultaneous|factorize|factorise|expansion|simplify|inequalit(y|ies)|roots of|solve for [a-z])\b",
    re.IGNORECASE
)

# Statistics & Probability
_STATISTICS_KEYWORDS = re.compile(
    r"\b(statistics|mean|median|mode|variance|standard deviation|std dev|probability|permutation|combination|npr|ncr|bayes|normal distribution|poisson|binomial)\b",
    re.IGNORECASE
)

# General Math (English, Hindi, Gujarati, Hinglish)
_MATH_KEYWORDS = re.compile(
    r"(\b(math|maths|mathematics|calculate|evaluate|solve|percentage|percent|fraction|exponent|powers?|root|sqrt|logarithm|trigonometry|geometry|matrix|matrices|determinant|vector|eigenvalue|hisab|ganit|jod|ghatav|guna|bhag|ganatri|ketla thay|pratishat)\b|[\∫\∑\∏\√\∂\±\≤\≥\≠\≈\∞\∈\∉\⊂\⊆\∪\∩]|(\d+\s*[\+\-\*\/\^]\s*\d+))",
    re.IGNORECASE
)

# Physics
_PHYSICS_KEYWORDS = re.compile(
    r"\b(physics|velocity|acceleration|momentum|gravity|newton|kinetic energy|potential energy|thermodynamics|electric field|magnetic field|voltage|resistance|ohm'?s law|optics|refraction|wavelength|frequency|quantum|rms speed|gurutvaakarshan|gati|urja|tarang)\b",
    re.IGNORECASE
)

# Chemistry
_CHEMISTRY_KEYWORDS = re.compile(
    r"\b(chemistry|chemical|reaction|stoichiometry|molar mass|moles|mole concept|compound|periodic table|acid|base|ph value|titration|organic chemistry|oxidation|reduction|parmanu|rasayan|abhikriya)\b",
    re.IGNORECASE
)

# Biology
_BIOLOGY_KEYWORDS = re.compile(
    r"\b(biology|cell|photosynthesis|mitochondria|dna|rna|genetics|evolution|organism|bacteria|virus|enzyme|chlorophyll|respiration|membrane transport|jeev vigyan|koshika)\b",
    re.IGNORECASE
)

# Coding Specialists
_SQL_KEYWORDS = re.compile(
    r"\b(sql|select\s+.*from|insert\s+into|update\s+.*set|delete\s+from|join\s+.*on|group\s+by|order\s+by|database schema|postgres|mysql|sqlite)\b",
    re.IGNORECASE
)

_DSA_KEYWORDS = re.compile(
    r"\b(dsa|data structure|binary tree|bst|linked list|bfs|dfs|graph algorithm|dijkstra|dynamic programming|dp|sorting algorithm|quicksort|mergesort|hashmap|hash table|recursion|heap|trie|time complexity|space complexity|big o)\b",
    re.IGNORECASE
)

_DEBUG_KEYWORDS = re.compile(
    r"\b(debug|bug|error|traceback|syntaxerror|typeerror|indexerror|infinite loop|why is this code failing|fix this code|exception|segfault)\b",
    re.IGNORECASE
)

_CODE_EXPLAIN_KEYWORDS = re.compile(
    r"\b(explain this code|how does this code work|code breakdown|walk through this function|explain the logic of this code)\b",
    re.IGNORECASE
)

_CODE_KEYWORDS = re.compile(
    r"\b(python|javascript|typescript|c\+\+|java|golang|rust|html|css|function|def\s+|class\s+|var\s+|let\s+|const\s+|import\s+|return\s+|syntax|malloc|pointer)\b",
    re.IGNORECASE
)

# Multimodal / Diagram
_IMAGE_KEYWORDS = re.compile(
    r"\b(uploaded image|this image|this photo|this picture|this diagram|this graph|attached image|look at this picture|in the screenshot|from the graph|from this chart|photographed|analyze this image|image)\b",
    re.IGNORECASE
)

# Web Research
_RESEARCH_KEYWORDS = re.compile(
    r"\b(search|current|latest|news|today|recent|who won|who is the current|price of|weather in|weather today|weather|live score|lookup|released date|stock price)\b",
    re.IGNORECASE
)

# Comparison / Evaluation / Analytical
_COMPARISON_KEYWORDS = re.compile(
    r"\b(compare|comparison|versus|vs\.?|difference between|pros and cons|evaluate|which is better|trade-?offs)\b",
    re.IGNORECASE
)

# Grammar / Typo fixes (Lightweight path)
_GRAMMAR_FIX_KEYWORDS = re.compile(
    r"\b(small grammar|minor grammar|typo|spelling mistake|correct this typo|fix this typo|fix (?:the |this )?(?:small )?grammar(?: mistake)?|check (?:the |this )?grammar|grammar mistake)\b",
    re.IGNORECASE
)

# Translation
_TRANSLATION_KEYWORDS = re.compile(
    r"\b(translate|translation|into hindi|into english|into gujarati|ka anuvad|translate to)\b",
    re.IGNORECASE
)

# Writing / Composition
_WRITING_KEYWORDS = re.compile(
    r"\b(write an essay|write a letter|write an application|write a story|draft an email|write a poem|composition|rewrite|rephrase|proofread|correct (?:the )?grammar|fix (?:the )?grammar|format (?:this|the|these)|turn (?:this|the following) into (?:a list|bullet points)|brainstorm)\b",
    re.IGNORECASE
)

# PDF Study Studio
_IMPORTANT_Q_KEYWORDS = re.compile(
    r"\b(important questions?|exam questions?|high-yield questions?|expected questions?|question bank|frequently asked)\b",
    re.IGNORECASE
)

_QUIZ_KEYWORDS = re.compile(
    r"\b(quiz|mcq|multiple choice|test me|practice questions)\b",
    re.IGNORECASE
)

_FLASHCARD_KEYWORDS = re.compile(
    r"\b(flashcard|flashcards|study cards|anki|revision cards|qa cards)\b",
    re.IGNORECASE
)

_SUMMARY_KEYWORDS = re.compile(
    r"\b(summarize|summary|tldr|takeaways|key points|recap|condense|digest)\b",
    re.IGNORECASE
)

_NOTES_KEYWORDS = re.compile(
    r"\b(study notes|revision notes|make notes|generate notes|chapter notes|cheatsheet)\b",
    re.IGNORECASE
)

# Depth Modifiers
_DEEP_KEYWORDS = re.compile(
    r"\b(in detail|detailed|step by step|comprehensive|deep dive|explain thoroughly|all aspects|elaborate|in depth)\b",
    re.IGNORECASE
)

_BRIEF_KEYWORDS = re.compile(
    r"\b(one[- ]line|in 1 line|briefly|short answer|in short|quick definition|concise|tldr|only the answer|just the answer)\b",
    re.IGNORECASE
)

# Casual greetings and quick acknowledgments (Instant Groq 8B candidate)
_CASUAL_GREETING_KEYWORDS = re.compile(
    r"^(hi|hello|hey|hola|namaste|sup|yo|good\s+(morning|afternoon|evening|night)|thanks|thank\s+you|thx|ok|okay|k|bye|cya|see\s+you|how\s+are\s+you|kya\s+haal|kem\s+cho|wassup)[\s\.\!\?]*$",
    re.IGNORECASE
)


def classify_task_multi(
    prompt: Optional[str | List[Dict[str, str]]] = None,
    messages: Optional[List[Dict[str, str]]] = None,
    context: Optional[Dict[str, Any]] = None,
    explicit_task: Optional[TaskType | str] = None,
    depth: Optional[ResponseDepth | str] = None
) -> List[TaskType]:
    """
    Returns a list of matching task types in priority order: [PrimaryTask, SecondaryTask, ...].
    """
    primary = classify_task(prompt, messages, context, explicit_task, depth)
    labels = [primary]

    text = ""
    if isinstance(prompt, str):
        text = prompt.strip()
    elif isinstance(prompt, list):
        messages = prompt
    if not text and messages:
        for m in reversed(messages):
            if m.get("role") == "user":
                text = (m.get("content") or "").strip()
                break

    # Check secondary matches
    if _IMAGE_KEYWORDS.search(text) and TaskType.IMAGE_QUESTION not in labels:
        labels.append(TaskType.IMAGE_QUESTION)
    if _PHYSICS_KEYWORDS.search(text) and TaskType.PHYSICS not in labels:
        labels.append(TaskType.PHYSICS)
    if _CALCULUS_KEYWORDS.search(text) and TaskType.CALCULUS not in labels:
        labels.append(TaskType.CALCULUS)
    if _ALGEBRA_KEYWORDS.search(text) and TaskType.ALGEBRA not in labels:
        labels.append(TaskType.ALGEBRA)
    if _CODE_KEYWORDS.search(text) and TaskType.CODING not in labels:
        labels.append(TaskType.CODING)

    return labels


def classify_task(
    prompt: Optional[str | List[Dict[str, str]]] = None,
    messages: Optional[List[Dict[str, str]]] = None,
    context: Optional[Dict[str, Any]] = None,
    explicit_task: Optional[TaskType | str] = None,
    depth: Optional[ResponseDepth | str] = None
) -> TaskType:
    """
    Fast, deterministic, zero-overhead multilingual task classification.
    Takes into account explicit intent, keywords, prompt length, document context, and image modalities.
    Never executes a remote LLM call just to classify.
    """
    if isinstance(prompt, list):
        messages = prompt
        prompt = ""

    if explicit_task:
        if isinstance(explicit_task, TaskType):
            return explicit_task
        try:
            return TaskType(str(explicit_task).upper())
        except ValueError:
            pass

    ctx = context or {}
    has_pdf_context = bool(ctx.get("document_id") or ctx.get("pdf_text") or ctx.get("document_pages"))
    has_multimodal = bool(ctx.get("multimodal_parts") or ctx.get("has_image"))
    resolved_depth = ResponseDepth.from_str(depth) if depth else ResponseDepth.BALANCED

    text = (prompt or "").strip()
    if not text and messages:
        for m in reversed(messages):
            if m.get("role") == "user":
                text = (m.get("content") or "").strip()
                break

    # 1. Document / PDF tasks (Academic Study Studio)
    is_doc_topic = has_pdf_context or "pdf" in text.lower() or "document" in text.lower()
    if is_doc_topic:
        if _IMPORTANT_Q_KEYWORDS.search(text):
            return TaskType.IMPORTANT_QUESTION_GENERATION
        if _QUIZ_KEYWORDS.search(text):
            return TaskType.QUIZ_GENERATION
        if _FLASHCARD_KEYWORDS.search(text):
            return TaskType.FLASHCARD_GENERATION
        if _NOTES_KEYWORDS.search(text):
            return TaskType.NOTE_GENERATION
        if _SUMMARY_KEYWORDS.search(text):
            return TaskType.PDF_SUMMARY
        if has_pdf_context:
            return TaskType.PDF_QUESTION_ANSWERING

    # 2. Standalone Quizzes, Important Questions, Flashcards, Notes
    if _IMPORTANT_Q_KEYWORDS.search(text):
        return TaskType.IMPORTANT_QUESTION_GENERATION
    if _QUIZ_KEYWORDS.search(text):
        return TaskType.QUIZ_GENERATION
    if _FLASHCARD_KEYWORDS.search(text):
        return TaskType.FLASHCARD_GENERATION
    if _NOTES_KEYWORDS.search(text):
        return TaskType.NOTE_GENERATION

    # 3. Multimodal & Diagram Analysis
    if has_multimodal or _IMAGE_KEYWORDS.search(text):
        if "diagram" in text.lower() or "graph" in text.lower() or "chart" in text.lower():
            return TaskType.DIAGRAM_ANALYSIS
        return TaskType.IMAGE_QUESTION

    # 4. Web Research
    if _RESEARCH_KEYWORDS.search(text) and len(text.split()) < 25:
        return TaskType.WEB_RESEARCH

    # Route short, plain definition questions through Normal Use even when the
    # defined term is also a specialist keyword (e.g. "What is gravity?").
    if len(text.split()) <= 6 and re.match(r"^(?:what is|who is|define|meaning of)\b", text, re.IGNORECASE):
        return TaskType.SIMPLE_EXPLANATION

    # 5. Translation
    if _TRANSLATION_KEYWORDS.search(text):
        return TaskType.TRANSLATION

    # 6. Coding Specialists (SQL, DSA, Debugging, Explanation, General Coding)
    if _SQL_KEYWORDS.search(text):
        return TaskType.SQL
    if _DSA_KEYWORDS.search(text):
        return TaskType.DSA
    if _DEBUG_KEYWORDS.search(text) and (_CODE_KEYWORDS.search(text) or "```" in text):
        return TaskType.CODING_DEBUGGING
    if _CODE_EXPLAIN_KEYWORDS.search(text):
        return TaskType.CODING_EXPLANATION
    if _CODE_KEYWORDS.search(text) or "```" in text:
        return TaskType.CODING

    # Rewriting/formatting comes after code recognition so code edits retain
    # their specialist route (e.g. "rewrite this Python function").
    if _WRITING_KEYWORDS.search(text):
        return TaskType.WRITING

    # 7. Science Specialists (Physics, Chemistry, Biology)
    if _PHYSICS_KEYWORDS.search(text):
        return TaskType.PHYSICS
    if _CHEMISTRY_KEYWORDS.search(text):
        return TaskType.CHEMISTRY
    if _BIOLOGY_KEYWORDS.search(text):
        return TaskType.BIOLOGY

    # 8. Mathematics & Logic Specialists
    if _CALCULUS_KEYWORDS.search(text):
        return TaskType.CALCULUS
    if _ALGEBRA_KEYWORDS.search(text):
        return TaskType.ALGEBRA
    if _STATISTICS_KEYWORDS.search(text):
        return TaskType.STATISTICS
    if _MATH_KEYWORDS.search(text):
        return TaskType.MATHEMATICS

    # 8.5 Comparison & Evaluation
    if _COMPARISON_KEYWORDS.search(text):
        return TaskType.SIMPLE_EXPLANATION if resolved_depth != ResponseDepth.DEEP else TaskType.DETAILED_EXPLANATION

    # 9. Title Generation
    if "generate title" in text.lower() or "conversation title" in text.lower():
        return TaskType.CHAT_TITLE_GENERATION

    # 10. Summary / Depth-based Explanation vs Quick Chat
    if _SUMMARY_KEYWORDS.search(text):
        return TaskType.SIMPLE_EXPLANATION if resolved_depth == ResponseDepth.FAST or len(text.split()) <= 100 else TaskType.DETAILED_EXPLANATION

    if _DEEP_KEYWORDS.search(text) or resolved_depth == ResponseDepth.DEEP:
        return TaskType.DEEP_REASONING

    if _CASUAL_GREETING_KEYWORDS.match(text) or (len(text.split()) <= 3 and _CASUAL_GREETING_KEYWORDS.search(text)):
        return TaskType.QUICK_CHAT

    if _BRIEF_KEYWORDS.search(text) or resolved_depth == ResponseDepth.FAST:
        words = text.split()
        if len(words) <= 4 and not any(k.search(text) for k in (_COMPARISON_KEYWORDS, _WRITING_KEYWORDS, _CODE_KEYWORDS, _RESEARCH_KEYWORDS, _MATH_KEYWORDS, _PHYSICS_KEYWORDS)):
            return TaskType.QUICK_CHAT
        return TaskType.SIMPLE_EXPLANATION

    if len(text.split()) <= 4 and not any(k.search(text) for k in (_COMPARISON_KEYWORDS, _WRITING_KEYWORDS, _CODE_KEYWORDS, _RESEARCH_KEYWORDS, _MATH_KEYWORDS, _PHYSICS_KEYWORDS, _CHEMISTRY_KEYWORDS)):
        return TaskType.QUICK_CHAT

    if len(text.split()) > 40:
        return TaskType.DETAILED_EXPLANATION

    return TaskType.SIMPLE_EXPLANATION


def classify_task_complexity(
    prompt: Optional[str | List[Dict[str, str]]] = None,
    task: Optional[TaskType | str] = None,
    depth: Optional[ResponseDepth | str] = None,
    context: Optional[Dict[str, Any]] = None
) -> TaskComplexity:
    """
    Deterministic zero-cost task complexity estimator.
    Categorizes incoming user requests into:
      - FAST: Casual greetings, simple acknowledgments, lightweight chat (Target: Groq 8B Instant)
      - LIGHT: Short definitions, basic facts, simple translations, minor typo/grammar fixes (Target: Groq 8B / Gemini 3.5 Flash-Lite)
      - STANDARD: Conceptual explanations, tutoring, substantial writing/drafting, comparisons (Target: Gemini 3.8 Flash)
      - COMPLEX: Coding, debugging, algorithms, science, algebra (Target: Gemini 3.8 Flash with thinking)
      - DEEP: Mathematical proofs, roadmaps, architecture reviews, multi-step problem solving (Target: Gemini 3.8 Flash with high thinking)
    """
    text = ""
    if isinstance(prompt, str):
        text = prompt.strip()
    elif isinstance(prompt, list):
        for m in reversed(prompt):
            if isinstance(m, dict) and m.get("role") == "user":
                text = (m.get("content") or "").strip()
                break

    resolved_depth = ResponseDepth.from_str(str(depth)) if depth else ResponseDepth.BALANCED
    resolved_task = None
    if task:
        if isinstance(task, TaskType):
            resolved_task = task
        else:
            try:
                resolved_task = TaskType(str(task).upper())
            except ValueError:
                pass

    words = text.split()
    word_count = len(words)

    # 1. FAST: Casual greetings, single-word acknowledgments, quick conversational turns
    if _CASUAL_GREETING_KEYWORDS.match(text) or (word_count <= 3 and _CASUAL_GREETING_KEYWORDS.search(text)):
        return TaskComplexity.FAST

    if resolved_task == TaskType.QUICK_CHAT and (word_count <= 6 or resolved_depth == ResponseDepth.FAST):
        return TaskComplexity.FAST

    if resolved_task == TaskType.CHAT_TITLE_GENERATION:
        return TaskComplexity.FAST

    # 2. DEEP: Deep reasoning, architectural reviews, roadmaps, multi-step math proofs, explicit deep dive requests
    if resolved_task == TaskType.DEEP_REASONING or resolved_depth == ResponseDepth.DEEP or _DEEP_KEYWORDS.search(text):
        return TaskComplexity.DEEP

    if re.search(r"\b(project roadmap|roadmap|system design|software architecture|step[- ]by[- ]step proof)\b", text, re.IGNORECASE):
        return TaskComplexity.DEEP

    if resolved_task in (TaskType.ADVANCED_MATHEMATICS, TaskType.CALCULUS) and (word_count > 20 or resolved_depth == ResponseDepth.DEEP):
        return TaskComplexity.DEEP

    # 3. LIGHT: Short definitions, basic facts, simple translations, brief explanations, minor grammar/typo fixes
    if _GRAMMAR_FIX_KEYWORDS.search(text):
        return TaskComplexity.LIGHT

    if (_BRIEF_KEYWORDS.search(text) or resolved_depth == ResponseDepth.FAST) and resolved_task not in (
        TaskType.CODING, TaskType.CODING_DEBUGGING, TaskType.DSA
    ):
        return TaskComplexity.LIGHT

    if resolved_task == TaskType.TRANSLATION and word_count <= 25 and resolved_depth != ResponseDepth.DEEP:
        return TaskComplexity.LIGHT

    # Short technical acronym/protocol/term definitions (e.g. "What is HTTP?", "Define API", "What is RAM?", "What is gravity?")
    if word_count <= 4 and re.match(r"^(?:what is|define|meaning of)\s+[A-Za-z0-9\-_/]+[?\.]*$", text, re.IGNORECASE):
        return TaskComplexity.LIGHT

    # Light sentence tweak (< 15 words) or quick brainstorm (< 10 words)
    if resolved_task == TaskType.WRITING and word_count <= 15 and ("sentence" in text.lower() or "clearly" in text.lower() or "brainstorm" in text.lower()) and "professionally" not in text.lower() and "essay" not in text.lower() and "email" not in text.lower() and "story" not in text.lower():
        return TaskComplexity.LIGHT

    # Short paragraph summary
    if resolved_task == TaskType.SIMPLE_EXPLANATION and "summarize" in text.lower() and word_count <= 20:
        return TaskComplexity.LIGHT

    # 4. COMPLEX: Coding, debugging, DSA, SQL, Science (Physics, Chemistry, Biology), Math
    if resolved_task in (
        TaskType.CODING, TaskType.CODING_DEBUGGING, TaskType.CODING_EXPLANATION,
        TaskType.DSA, TaskType.SQL, TaskType.PHYSICS, TaskType.CHEMISTRY,
        TaskType.BIOLOGY, TaskType.SCIENCE, TaskType.MATHEMATICS,
        TaskType.ALGEBRA, TaskType.STATISTICS, TaskType.MATH_AND_LOGIC
    ):
        return TaskComplexity.COMPLEX

    if _CODE_KEYWORDS.search(text) or "```" in text or _SQL_KEYWORDS.search(text) or _DSA_KEYWORDS.search(text):
        return TaskComplexity.COMPLEX
    if _PHYSICS_KEYWORDS.search(text) or _CHEMISTRY_KEYWORDS.search(text) or _CALCULUS_KEYWORDS.search(text):
        return TaskComplexity.COMPLEX

    # 5. STANDARD: Detailed explanations, tutoring, substantial writing/drafting, comparisons, web research, PDF ops
    return TaskComplexity.STANDARD


def classify_task_with_complexity(
    prompt: Optional[str | List[Dict[str, str]]] = None,
    messages: Optional[List[Dict[str, str]]] = None,
    context: Optional[Dict[str, Any]] = None,
    explicit_task: Optional[TaskType | str] = None,
    depth: Optional[ResponseDepth | str] = None
) -> Tuple[TaskType, TaskComplexity]:
    """Classifies both TaskType and TaskComplexity in a single pass."""
    t = classify_task(prompt, messages, context, explicit_task, depth)
    c = classify_task_complexity(prompt or messages, task=t, depth=depth, context=context)
    return t, c
