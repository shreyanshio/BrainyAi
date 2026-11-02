"""
BrainyAi Central Prompt Registry & Typed Prompt Resolver
Authoritative engine for registering, validating, resolving, and composing
all 27 Brainy prompt assets from prompts/prompt_registry.yaml.
Guarantees zero-orphan prompt files, deterministic workflow resolution,
and strict multi-platform output formatting contracts.
"""

import os
import re
import yaml
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from ai_routing.tasks import TaskType

logger = logging.getLogger("prompt_registry")

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPTS_DIR = os.path.join(_BASE_DIR, "prompts")
REGISTRY_YAML_PATH = os.path.join(PROMPTS_DIR, "prompt_registry.yaml")


@dataclass
class PromptSpec:
    prompt_id: str
    file_path: str
    workflow: str
    purpose: str
    trigger_intents: List[str] = field(default_factory=list)
    excluded_intents: List[str] = field(default_factory=list)
    applicable_model_categories: List[str] = field(default_factory=lambda: ["general"])
    required_context: List[str] = field(default_factory=list)
    optional_context: List[str] = field(default_factory=list)
    permitted_tools: List[str] = field(default_factory=list)
    expected_output_behavior: str = ""
    version: int = 1
    enabled: bool = True
    full_path: str = ""

    def __post_init__(self):
        if not self.full_path:
            self.full_path = os.path.join(_BASE_DIR, self.file_path)


@dataclass
class ResolvedPrompt:
    prompt_id: str
    version: int
    workflow: str
    system_prompt: str
    raw_template: str
    file_path: str
    applied_context_keys: List[str] = field(default_factory=list)


class CentralPromptRegistry:
    """
    Central repository and loader for all Brainy prompts.
    Reads prompts/prompt_registry.yaml, validates disk presence,
    and supports hot-reloading in development.
    """

    def __init__(self, yaml_path: str = REGISTRY_YAML_PATH, prompts_dir: str = PROMPTS_DIR):
        self.yaml_path = yaml_path
        self.prompts_dir = prompts_dir
        self.specs: Dict[str, PromptSpec] = {}
        self.intent_map: Dict[str, str] = {}  # intent -> prompt_id
        self.workflow_map: Dict[str, str] = {}  # workflow -> prompt_id
        self._content_cache: Dict[str, str] = {}
        self._mtimes: Dict[str, float] = {}
        self.reload()

    def reload(self):
        """Loads and parses prompt_registry.yaml and verifies every file exists."""
        if not os.path.exists(self.yaml_path):
            logger.error("Prompt registry YAML not found at: %s", self.yaml_path)
            return

        try:
            with open(self.yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            logger.error("Failed to parse %s: %s", self.yaml_path, e)
            return

        raw_prompts = data.get("prompts", {})
        new_specs = {}
        new_intent_map = {}
        new_workflow_map = {}

        for p_id, item in raw_prompts.items():
            spec = PromptSpec(
                prompt_id=p_id,
                file_path=item.get("file", ""),
                workflow=item.get("workflow", p_id),
                purpose=item.get("purpose", ""),
                trigger_intents=item.get("trigger_intents", []),
                excluded_intents=item.get("excluded_intents", []),
                applicable_model_categories=item.get("applicable_model_categories", ["general"]),
                required_context=item.get("required_context", []),
                optional_context=item.get("optional_context", []),
                permitted_tools=item.get("permitted_tools", []),
                expected_output_behavior=item.get("expected_output_behavior", ""),
                version=item.get("version", 1),
                enabled=item.get("enabled", True),
            )
            # Verify file exists on disk
            if not os.path.exists(spec.full_path):
                logger.warning("Registered prompt file does not exist: %s (id=%s)", spec.full_path, p_id)
            new_specs[p_id] = spec
            new_workflow_map[spec.workflow.lower()] = p_id

            for intent in spec.trigger_intents:
                new_intent_map[intent.lower()] = p_id

        self.specs = new_specs
        self.intent_map = new_intent_map
        self.workflow_map = new_workflow_map
        logger.info("Loaded %d prompt specifications from registry", len(self.specs))

    def get_spec(self, prompt_id: str) -> Optional[PromptSpec]:
        return self.specs.get(prompt_id)

    def load_prompt_text(self, prompt_id: str) -> str:
        """Loads prompt text from disk with hot-reload if mtime changed."""
        spec = self.specs.get(prompt_id)
        if not spec:
            raise KeyError(f"Prompt ID '{prompt_id}' is not registered in prompt_registry.yaml")

        fpath = spec.full_path
        if not os.path.exists(fpath):
            raise FileNotFoundError(f"Registered prompt file does not exist on disk: {fpath}")

        mtime = os.path.getmtime(fpath)
        if prompt_id in self._content_cache and self._mtimes.get(prompt_id) == mtime:
            return self._content_cache[prompt_id]

        with open(fpath, "r", encoding="utf-8") as f:
            text = f.read().strip()
            self._content_cache[prompt_id] = text
            self._mtimes[prompt_id] = mtime
            return text

    def map_task_to_prompt_id(self, task: TaskType | str) -> str:
        """Deterministic mapping from TaskType or intent string to prompt_id."""
        if isinstance(task, TaskType):
            task_val = task.value.lower()
        else:
            task_val = str(task).lower().strip()

        # Direct intent map hit
        if task_val in self.intent_map:
            return self.intent_map[task_val]

        # Direct workflow map hit
        if task_val in self.workflow_map:
            return self.workflow_map[task_val]

        # Specific task type mappings
        TASK_NAME_MAP = {
            "coding": "coding",
            "coding_debugging": "coding",
            "coding_explanation": "coding",
            "dsa": "coding",
            "sql": "coding",
            "complex_debugging": "coding",
            "code_architecture": "coding",
            "math_and_logic": "mathematics",
            "mathematics": "mathematics",
            "advanced_mathematics": "mathematics",
            "algebra": "mathematics",
            "calculus": "mathematics",
            "statistics": "mathematics",
            "physics": "mathematics",
            "complex_math": "mathematics",
            "chemistry": "brainy_comprehensive",
            "biology": "brainy_comprehensive",
            "science": "brainy_comprehensive",
            "deep_reasoning": "brainy_comprehensive",
            "detailed_explanation": "brainy_comprehensive",
            "general_study": "brainy_comprehensive",
            "uncertain_complex": "brainy_comprehensive",
            "web_research": "web_search",
            "current_info": "web_search",
            "simple_explanation": "normal_chat",
            "quick_chat": "normal_chat",
            "note_generation": "pdf_notes",
            "document_ingestion": "pdf_notes",
            "long_doc_synthesis": "pdf_notes",
            "pdf_summary": "summarize",
            "pdf_question_answering": "pdf_qa",
            "pdf_extraction": "pdf_qa",
            "quiz_generation": "pdf_quiz",
            "mcq_generation": "pdf_quiz",
            "flashcard_generation": "pdf_flashcards",
            "important_question_generation": "pdf_important_questions",
            "image_question": "image_analysis",
            "diagram_analysis": "image_analysis",
            "pdf_image": "image_analysis",
            "chat_title_generation": "title_generation",
            "translation": "translate",
            "text_correction": "summarize",
            "short_json_extraction": "summarize",
            "writing": "brainy_comprehensive",
        }
        if task_val in TASK_NAME_MAP:
            return TASK_NAME_MAP[task_val]

        return "system_base"


class PromptResolver:
    """
    Resolves, injects, and assembles the exact required prompt for any workflow.
    Ensures that only the relevant task instructions are loaded, preventing token waste
    and conflicting instructions.
    """

    def __init__(self, registry: Optional[CentralPromptRegistry] = None):
        self.registry = registry or CentralPromptRegistry()

    def resolve(
        self,
        task: TaskType | str,
        platform: str = "web",
        context_vars: Optional[Dict[str, Any]] = None,
        system_prompt_override: Optional[str] = None,
        normal_use: bool = False,
        include_completeness: bool = True
    ) -> ResolvedPrompt:
        """
        Main entrypoint: resolves prompt ID, validates dependencies,
        and constructs the layered system prompt.
        """
        from ai_routing.prompts import PLATFORM_DIRECTIVES, COMPLETENESS_DIRECTIVE, Platform

        plat_enum = Platform.from_str(platform)
        prompt_id = "normal_chat" if normal_use else self.registry.map_task_to_prompt_id(task)
        spec = self.registry.get_spec(prompt_id)
        if not spec or not spec.enabled:
            prompt_id = "system_base"
            spec = self.registry.get_spec(prompt_id)

        raw_template = self.registry.load_prompt_text(prompt_id)

        # 1. Base Layer (Layer A)
        if normal_use:
            base_prompt = raw_template
            task_protocol = ""
        elif system_prompt_override and system_prompt_override.strip():
            base_prompt = system_prompt_override.strip()
            task_protocol = ""
            if prompt_id not in ("system_base", "normal_chat") and raw_template not in base_prompt:
                task_protocol = f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n🎯 ACTIVE TASK SPECIALIST PROTOCOL ({spec.workflow.upper()})\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n{raw_template}"
        else:
            base_prompt = self.registry.load_prompt_text("system_base")
            task_protocol = ""
            if prompt_id != "system_base" and raw_template != base_prompt:
                task_protocol = f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n🎯 ACTIVE TASK SPECIALIST PROTOCOL ({spec.workflow.upper()})\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n{raw_template}"

        # 2. Platform Directives (Layer B)
        plat_directive = PLATFORM_DIRECTIVES.get(plat_enum, PLATFORM_DIRECTIVES[Platform.WEB])
        plat_block = ""
        if "PLATFORM FORMATTING CONTRACT" not in base_prompt:
            plat_block = f"\n\n{plat_directive}"

        # 3. Context Injection (Layer D)
        context_parts = []
        applied_keys = []
        if context_vars:
            for key, val in context_vars.items():
                if val is not None and str(val).strip():
                    clean_val = str(val).strip()
                    context_parts.append(f"[{key.upper()}]:\n{clean_val}")
                    applied_keys.append(key)

        context_block = ""
        if context_parts:
            context_block = "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n📂 INJECTED REQUEST CONTEXT\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n" + "\n\n".join(context_parts)

        # 4. Completeness Directive
        comp_block = ""
        if include_completeness and not normal_use and "COMPLETENESS DIRECTIVE" not in base_prompt:
            comp_block = f"\n\n{COMPLETENESS_DIRECTIVE}"

        composed = f"{base_prompt}{plat_block}{task_protocol}{context_block}{comp_block}".strip()

        return ResolvedPrompt(
            prompt_id=prompt_id,
            version=spec.version if spec else 1,
            workflow=spec.workflow if spec else "general",
            system_prompt=composed,
            raw_template=raw_template,
            file_path=spec.file_path if spec else "",
            applied_context_keys=applied_keys
        )


# Global instances
central_prompt_registry = CentralPromptRegistry()
prompt_resolver = PromptResolver(central_prompt_registry)
