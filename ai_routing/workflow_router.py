"""
BrainyAi Central Workflow Router
Deterministic decision engine that determines:
1. What the user is asking.
2. Which workflow handles the request.
3. Which prompt file must be loaded.
4. Which AI model must be selected (Gemini primary, Groq fallback).
5. Whether web search is required.
6. Whether Tavily and DuckDuckGo must be invoked.
7. How to manage conversation memory and follow-up intent.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple

from ai_routing.tasks import TaskType, ResponseDepth, classify_task_with_complexity, is_conversational_followup
from ai_routing.search_intent import detect_search_intent, SearchIntentResult
from ai_routing.query_planner import plan_search_queries
from ai_routing.prompt_registry import central_prompt_registry
from ai_routing.intent import intent_resolver, UserIntentRequest, IntentResolutionResult

logger = logging.getLogger("workflow_router")


@dataclass
class WorkflowRoutingDecision:
    workflow: str
    prompt_id: str
    prompt_file: str
    search_required: bool
    search_providers: List[str]
    planned_queries: List[str]
    primary_provider: str
    primary_model: str
    fallback_provider: str
    fallback_model: str
    reason: str
    is_followup: bool = False
    reuse_prior_search: bool = False
    is_fast_path: bool = False
    normal_use: bool = False
    intent_result: Optional[IntentResolutionResult] = None
    topic: Optional[str] = None
    primary_intent: Optional[str] = None
    secondary_intents: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)


class WorkflowRouter:
    """
    Central deterministic router mapping requests to workflows, prompt assets,
    search tools, and model candidates.
    """

    def __init__(self):
        self.prompt_registry = central_prompt_registry

    def route(
        self,
        content: str,
        messages: Optional[List[Dict[str, str]]] = None,
        document_context: Optional[Dict[str, Any]] = None,
        explicit_intent: Optional[str] = None
    ) -> WorkflowRoutingDecision:
        clean_text = (content or "").strip()
        has_doc = bool(document_context and (document_context.get("pdf_text") or document_context.get("doc_id")))

        # 0. Central Intent Knowledge Base Resolution
        intent_res = intent_resolver.resolve(
            UserIntentRequest(
                query=clean_text,
                messages=messages,
                document_context=document_context,
                explicit_intent=explicit_intent
            )
        )

        # Check conversation history for follow-ups
        is_followup = False
        reuse_search = False
        prior_search_found = False

        if messages and len(messages) >= 1:
            is_followup = is_conversational_followup(clean_text)
            # Check if prior turn had search results
            for m in reversed(messages):
                if "LIVE WEB RESEARCH FINDINGS" in m.get("content", "") or "EXTERNAL SEARCH FINDINGS" in m.get("content", ""):
                    prior_search_found = True
                    break

            if prior_search_found and (
                "reuse_search" in intent_res.constraints
                or re.search(
                    r"\b(?:explain|tell me more about|expand on|what about)\s+(?:the\s+)?(?:first|second|third|fourth|1st|2nd|3rd|4th|last)\s+result\b",
                    clean_text,
                    re.IGNORECASE
                )
            ):
                reuse_search = True

        # 1. Search Intent Detection
        search_res: SearchIntentResult = detect_search_intent(
            clean_text,
            context_turns=messages,
            document_present=has_doc
        )

        # Honor explicit constraints (e.g. without searching, offline, or search evidence reuse)
        no_search_constraint = "no_web_search" in intent_res.constraints
        search_required = bool(
            (search_res.search_required or intent_res.search_required)
            and not reuse_search
            and not no_search_constraint
        )
        planned_queries = plan_search_queries(clean_text) if search_required else []
        search_providers = ["tavily", "duckduckgo"] if search_required else []

        # 2. PDF Studio Workflow Mapping
        if has_doc and not search_required:
            pdf_action = (explicit_intent or intent_res.primary_intent or "").lower()
            if "quiz" in pdf_action or "mcq" in pdf_action:
                return WorkflowRoutingDecision(
                    workflow="pdf_quiz",
                    prompt_id="pdf_quiz",
                    prompt_file="pdf_quiz_prompt.txt",
                    search_required=False,
                    search_providers=[],
                    planned_queries=[],
                    primary_provider="gemini",
                    primary_model="gemini-3.8-flash",
                    fallback_provider="groq",
                    fallback_model="llama-3.3-70b-versatile",
                    reason="Document quiz generation requested",
                    normal_use=False,
                    intent_result=intent_res,
                    topic=intent_res.topic,
                    primary_intent=intent_res.primary_intent,
                    secondary_intents=intent_res.secondary_intents,
                    constraints=intent_res.constraints
                )
            if "flashcard" in pdf_action:
                return WorkflowRoutingDecision(
                    workflow="pdf_flashcards",
                    prompt_id="pdf_flashcards",
                    prompt_file="pdf_flashcards_prompt.txt",
                    search_required=False,
                    search_providers=[],
                    planned_queries=[],
                    primary_provider="gemini",
                    primary_model="gemini-3.8-flash",
                    fallback_provider="groq",
                    fallback_model="llama-3.3-70b-versatile",
                    reason="Document flashcard extraction requested",
                    normal_use=False,
                    intent_result=intent_res,
                    topic=intent_res.topic,
                    primary_intent=intent_res.primary_intent,
                    secondary_intents=intent_res.secondary_intents,
                    constraints=intent_res.constraints
                )
            if "important" in pdf_action or "exam" in pdf_action:
                return WorkflowRoutingDecision(
                    workflow="pdf_important_questions",
                    prompt_id="pdf_important_questions",
                    prompt_file="pdf_important_questions_prompt.txt",
                    search_required=False,
                    search_providers=[],
                    planned_queries=[],
                    primary_provider="gemini",
                    primary_model="gemini-3.8-flash",
                    fallback_provider="groq",
                    fallback_model="llama-3.3-70b-versatile",
                    reason="Document high-yield question generation requested",
                    normal_use=False,
                    intent_result=intent_res,
                    topic=intent_res.topic,
                    primary_intent=intent_res.primary_intent,
                    secondary_intents=intent_res.secondary_intents,
                    constraints=intent_res.constraints
                )
            if "notes" in pdf_action:
                return WorkflowRoutingDecision(
                    workflow="pdf_notes",
                    prompt_id="pdf_notes",
                    prompt_file="pdf_notes_prompt.txt",
                    search_required=False,
                    search_providers=[],
                    planned_queries=[],
                    primary_provider="gemini",
                    primary_model="gemini-3.8-flash",
                    fallback_provider="groq",
                    fallback_model="llama-3.3-70b-versatile",
                    reason="Document revision notes generation requested",
                    normal_use=False,
                    intent_result=intent_res,
                    topic=intent_res.topic,
                    primary_intent=intent_res.primary_intent,
                    secondary_intents=intent_res.secondary_intents,
                    constraints=intent_res.constraints
                )
            # Default PDF Q&A
            return WorkflowRoutingDecision(
                workflow="pdf_qa",
                prompt_id="pdf_qa",
                prompt_file="pdf_qa_prompt.txt",
                search_required=False,
                search_providers=[],
                planned_queries=[],
                primary_provider="gemini",
                primary_model="gemini-3.8-flash",
                fallback_provider="groq",
                fallback_model="llama-3.3-70b-versatile",
                reason="Document Q&A grounded in uploaded text",
                normal_use=False,
                intent_result=intent_res,
                topic=intent_res.topic,
                primary_intent=intent_res.primary_intent,
                secondary_intents=intent_res.secondary_intents,
                constraints=intent_res.constraints
            )

        # 3. Web Search Workflow
        if search_required:
            is_coding = bool(
                intent_res.workflow == "coding_search"
                or re.search(r"\b(python|javascript|typescript|fastapi|react|next\.?js|django|flask|rust|go|c\+\+|java|error|bug|exception)\b", clean_text, re.IGNORECASE)
            )
            workflow_name = "coding_search" if is_coding else "web_search"
            prompt_id = "coding" if is_coding else "web_search"
            prompt_file = "coding_prompt.txt" if is_coding else "search_prompt.txt"

            return WorkflowRoutingDecision(
                workflow=workflow_name,
                prompt_id=prompt_id,
                prompt_file=prompt_file,
                search_required=True,
                search_providers=search_providers,
                planned_queries=planned_queries,
                primary_provider="gemini",
                primary_model="gemini-3.8-flash",
                fallback_provider="groq",
                fallback_model="llama-3.3-70b-versatile",
                reason=search_res.reason if search_res.search_required else "Structured web search intent identified",
                is_followup=is_followup,
                reuse_prior_search=False,
                normal_use=False,
                intent_result=intent_res,
                topic=intent_res.topic,
                primary_intent=intent_res.primary_intent,
                secondary_intents=intent_res.secondary_intents,
                constraints=intent_res.constraints
            )

        # 4. Contextual Follow-up with Search Evidence Reuse
        if reuse_search:
            return WorkflowRoutingDecision(
                workflow="web_search",
                prompt_id="web_search",
                prompt_file="search_prompt.txt",
                search_required=False,
                search_providers=[],
                planned_queries=[],
                primary_provider="gemini",
                primary_model="gemini-3.8-flash",
                fallback_provider="groq",
                fallback_model="llama-3.3-70b-versatile",
                reason="User is referencing search results from prior turn; reusing existing evidence package",
                is_followup=True,
                reuse_prior_search=True,
                normal_use=False,
                intent_result=intent_res,
                topic=intent_res.topic,
                primary_intent=intent_res.primary_intent,
                secondary_intents=intent_res.secondary_intents,
                constraints=intent_res.constraints
            )

        # 5. Mathematics & Physics Derivations
        # Math is checked before coding so equations with letters (e.g. solve for x) are not confused with code
        is_math = bool(
            intent_res.workflow == "mathematics"
            or explicit_intent in ("math", "maths")
            or re.search(r"\b(?:solve\s+for|evaluate\s+the\s+integral|integral\s+of|derivative\s+of|dy/dx|eigenvalues?|determinant|quadratic\s+equation|differential\s+equation)\b|\d+\s*[xX\+\-\*/=]\s*\d+", clean_text, re.IGNORECASE)
        )
        if is_math and "no_code" in intent_res.constraints or (is_math and intent_res.workflow == "mathematics"):
            return WorkflowRoutingDecision(
                workflow="mathematics",
                prompt_id="mathematics",
                prompt_file="maths.txt",
                search_required=False,
                search_providers=[],
                planned_queries=[],
                primary_provider="gemini",
                primary_model="gemini-3.8-flash",
                fallback_provider="groq",
                fallback_model="llama-3.3-70b-versatile",
                reason="Mathematical working, derivations, or STEM problem solving requested",
                is_fast_path=True,
                normal_use=False,
                intent_result=intent_res,
                topic=intent_res.topic,
                primary_intent=intent_res.primary_intent,
                secondary_intents=intent_res.secondary_intents,
                constraints=intent_res.constraints
            )

        # 6. Coding & Programming Workflow
        # Reliably detects coding tasks, code syntax, and language-specific programming features (e.g. inheritance in Java)
        has_code_syntax = bool(re.search(r"\b(?:def\s+\w+\(|function\s+\w*\(|class\s+\w+[:\{]|console\.log\(|import\s+\w+|from\s+\w+\s+import|<\?php|SELECT\s+.*\s+FROM)\b|```", clean_text, re.IGNORECASE))
        has_programming_concept = bool(
            re.search(r"\b(?:code|debug|script|program|algorithm|implement|error|bug|exception|stack\s*trace)\b", clean_text, re.IGNORECASE)
            or re.search(r"\b(?:in\s+(?:java|python|c\+\+|cpp|rust|javascript|typescript|golang|php|ruby|swift|kotlin|c#))\b", clean_text, re.IGNORECASE)
            or (
                re.search(r"\b(?:java|c\+\+|cpp|rust|typescript|golang|ruby|swift|kotlin|c#)\b", clean_text, re.IGNORECASE)
                and re.search(r"\b(?:inheritance|polymorphism|interface|class|pointer|concurrency|multithreading|syntax|recursion)\b", clean_text, re.IGNORECASE)
            )
        )
        is_coding = bool(
            (intent_res.workflow == "coding" or has_code_syntax or has_programming_concept)
            and "no_code" not in intent_res.constraints
            or explicit_intent == "coding"
        )
        if is_coding and "no_code" not in intent_res.constraints:
            return WorkflowRoutingDecision(
                workflow="coding",
                prompt_id="coding",
                prompt_file="coding_prompt.txt",
                search_required=False,
                search_providers=[],
                planned_queries=[],
                primary_provider="gemini",
                primary_model="gemini-3.8-flash",
                fallback_provider="groq",
                fallback_model="llama-3.3-70b-versatile",
                reason="Programming, debugging, or algorithmic explanation requested",
                is_fast_path=True,
                normal_use=False,
                intent_result=intent_res,
                topic=intent_res.topic,
                primary_intent=intent_res.primary_intent,
                secondary_intents=intent_res.secondary_intents,
                constraints=intent_res.constraints
            )

        # Re-check math if not caught earlier
        if is_math:
            return WorkflowRoutingDecision(
                workflow="mathematics",
                prompt_id="mathematics",
                prompt_file="maths.txt",
                search_required=False,
                search_providers=[],
                planned_queries=[],
                primary_provider="gemini",
                primary_model="gemini-3.8-flash",
                fallback_provider="groq",
                fallback_model="llama-3.3-70b-versatile",
                reason="Mathematical working, derivations, or STEM problem solving requested",
                is_fast_path=True,
                normal_use=False,
                intent_result=intent_res,
                topic=intent_res.topic,
                primary_intent=intent_res.primary_intent,
                secondary_intents=intent_res.secondary_intents,
                constraints=intent_res.constraints
            )

        # 7. Lightweight Normal Chat / Greetings / Simple Queries
        is_greeting = bool(re.search(r"^(?:hi|hello|hey|good\s+(?:morning|afternoon|evening)|namaste|hola|yo)\b|\b(?:how are you|kya haal|what\'?s up|sup|tell me about yourself)\b", clean_text, re.IGNORECASE))
        is_short_def = bool(len(clean_text.split()) <= 6 and re.match(r"^(?:what is|who is|define|meaning of)\b", clean_text, re.IGNORECASE))

        if intent_res.workflow == "normal_chat" or is_greeting or is_short_def or explicit_intent in ("chat", "normal"):
            return WorkflowRoutingDecision(
                workflow="normal_chat",
                prompt_id="normal_chat",
                prompt_file="normal_use.txt",
                search_required=False,
                search_providers=[],
                planned_queries=[],
                primary_provider="gemini",
                primary_model="gemini-3.5-flash-lite",
                fallback_provider="groq",
                fallback_model="llama-3.1-8b-instant",
                reason="Lightweight normal conversation handled with token-efficient prompt",
                is_fast_path=True,
                normal_use=True,
                intent_result=intent_res,
                topic=intent_res.topic,
                primary_intent=intent_res.primary_intent,
                secondary_intents=intent_res.secondary_intents,
                constraints=intent_res.constraints
            )

        # 8. Stable Educational STEM Concepts (Biology, Chemistry, Physics, DSA)
        is_educational = bool(
            intent_res.workflow == "educational"
            or re.search(r"\b(?:explain|how\s+does|what\s+is|describe|mechanism\s+of|process\s+of)\b.*\b(?:photosynthesis|binary\s+search(?:\s+tree)?|inheritance|gravity|mitosis|meiosis|dna|thermodynamics|polymorphism|relativity|cell|quantum)\b", clean_text, re.IGNORECASE)
        )
        if is_educational or explicit_intent == "brainy":
            return WorkflowRoutingDecision(
                workflow="educational",
                prompt_id="brainy_comprehensive",
                prompt_file="brainy_prompt.txt",
                search_required=False,
                search_providers=[],
                planned_queries=[],
                primary_provider="gemini",
                primary_model="gemini-3.8-flash",
                fallback_provider="groq",
                fallback_model="llama-3.3-70b-versatile",
                reason="Deep educational concept explanation from verified knowledge base",
                is_fast_path=False,
                normal_use=False,
                intent_result=intent_res,
                topic=intent_res.topic,
                primary_intent=intent_res.primary_intent,
                secondary_intents=intent_res.secondary_intents,
                constraints=intent_res.constraints
            )

        # Default Fallback: Educational Comprehensive
        return WorkflowRoutingDecision(
            workflow="educational",
            prompt_id="brainy_comprehensive",
            prompt_file="brainy_prompt.txt",
            search_required=False,
            search_providers=[],
            planned_queries=[],
            primary_provider="gemini",
            primary_model="gemini-3.8-flash",
            fallback_provider="groq",
            fallback_model="llama-3.3-70b-versatile",
            reason="Standard educational inquiry routed to primary intelligence",
            is_fast_path=False,
            normal_use=False,
            intent_result=intent_res,
            topic=intent_res.topic,
            primary_intent=intent_res.primary_intent,
            secondary_intents=intent_res.secondary_intents,
            constraints=intent_res.constraints
        )


# Global singleton workflow router
workflow_router = WorkflowRouter()
