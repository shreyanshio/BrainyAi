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
    normal_use: bool = False


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

            if prior_search_found and re.search(
                r"\b(?:explain|tell me more about|expand on|what about)\s+(?:the\s+)?(?:first|second|third|fourth|1st|2nd|3rd|4th|last)\s+result\b",
                clean_text,
                re.IGNORECASE
            ):
                reuse_search = True

        # 1. Search Intent Detection
        search_res: SearchIntentResult = detect_search_intent(
            clean_text,
            context_turns=messages,
            document_present=has_doc
        )

        search_required = bool(search_res.search_required and not reuse_search)
        planned_queries = plan_search_queries(clean_text) if search_required else []
        search_providers = ["tavily", "duckduckgo"] if search_required else []

        # 2. PDF Studio Workflow Mapping
        if has_doc and not search_required:
            pdf_action = (explicit_intent or "").lower()
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
                    normal_use=False
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
                    normal_use=False
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
                    normal_use=False
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
                    normal_use=False
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
                normal_use=False
            )

        # 3. Web Search Workflow
        if search_required:
            is_coding = bool(re.search(r"\b(python|javascript|typescript|fastapi|react|next\.?js|django|flask|rust|go|c\+\+|java|error|bug|exception)\b", clean_text, re.IGNORECASE))
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
                reason=search_res.reason,
                is_followup=is_followup,
                reuse_prior_search=False,
                normal_use=False
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
                normal_use=False
            )

        # 5. Coding & Programming Workflow
        is_code = bool(re.search(r"\b(?:python|java|javascript|typescript|c\+\+|rust|go|sql|html|css|def |function |class |return |import |const |let |var |print\(|console\.log|for |while |if |elif |else:|try:|except |catch )\b", clean_text, re.IGNORECASE))
        if is_code or explicit_intent == "coding":
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
                normal_use=False
            )

        # 6. Mathematics & Physics Derivations
        is_math = bool(re.search(r"\b(?:integrate|integral|derivative|derivative of|dx|dy/dx|equation|solve\s+for|algebra|calculus|matrix|matrices|eigenvalue|vector|probability|trigonometry|theorem|proof|formula)\b", clean_text, re.IGNORECASE))
        if is_math or explicit_intent in ("math", "maths"):
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
                normal_use=False
            )

        # 7. Stable Educational STEM Concepts (Biology, Chemistry, Physics, DSA)
        is_educational = bool(re.search(r"\b(?:explain|how\s+does|what\s+is|describe|mechanism\s+of|process\s+of)\s+(?:photosynthesis|binary\s+search(?:\s+tree)?|inheritance|gravity|mitosis|meiosis|dna|thermodynamics|polymorphism|relativity)\b", clean_text, re.IGNORECASE))
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
                normal_use=False
            )

        # 8. Lightweight Normal Chat / Greetings / Simple Queries
        is_greeting = bool(re.match(r"^(?:hi|hello|hey|good\s+(?:morning|afternoon|evening)|namaste|hola|yo)\b[!.\s]*$", clean_text, re.IGNORECASE))
        is_short_def = bool(len(clean_text.split()) <= 6 and re.match(r"^(?:what is|who is|define|meaning of)\b", clean_text, re.IGNORECASE))

        if is_greeting or is_short_def or explicit_intent in ("chat", "normal", None, ""):
            return WorkflowRoutingDecision(
                workflow="normal_chat",
                prompt_id="normal_chat",
                prompt_file="normal_use.txt",
                search_required=False,
                search_providers=[],
                planned_queries=[],
                primary_provider="gemini",
                primary_model="gemini-3.5-flash-lite" if is_greeting else "gemini-3.8-flash",
                fallback_provider="groq",
                fallback_model="llama-3.1-8b-instant" if is_greeting else "llama-3.3-70b-versatile",
                reason="Lightweight normal conversation handled with token-efficient prompt",
                normal_use=True
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
            normal_use=False
        )


# Global singleton workflow router
workflow_router = WorkflowRouter()
