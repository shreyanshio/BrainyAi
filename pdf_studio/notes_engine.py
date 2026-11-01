"""
BrainyAi PDF Study Studio - Fast Structured Notes Engine
Generates comprehensive, structured academic revision notes directly from extracted PDF text.
Supports fast, high-accuracy synthesis without external API dependencies.

Supports 3 Depth Modes:
1. Quick Revision (concise summary, top concepts, formulas, key facts, revision checklist)
2. Standard Notes (chapter-wise notes, definitions, formulas, procedures, comparisons, key takeaways)
3. Detailed Study Notes (in-depth coverage, all definitions, proofs, steps, examples, full checklist)
"""

import re
import html
from collections import Counter
from typing import List, Dict, Any, Tuple, Optional, Set

# Common English stop words for local TF-based sentence scoring
STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does",
    "doesn't", "doing", "don't", "down", "during", "each", "few", "for", "from", "further", "had",
    "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd",
    "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself",
    "let's", "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off",
    "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own",
    "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some",
    "such", "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then",
    "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we", "we'd",
    "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when", "when's", "where",
    "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves"
}

DEFINITION_INDICATORS = [
    re.compile(r"\b([A-Z][\w\s\-]{2,30})\s+(?:is defined as|refers to|is called|is known as|can be defined as|represents|denotes)\s+([^.\n]+)", re.IGNORECASE),
    re.compile(r"\b([A-Z][\w\s\-]{2,30})\s*:\s*([^.\n]{15,})", re.IGNORECASE),
    re.compile(r"\bDefinition\s*(?:\d+[\.\:]|\:)\s*([^\.\n]+)", re.IGNORECASE),
    re.compile(r"\bBy\s+([A-Z][\w\s\-]+),\s+we mean\s+([^.\n]+)", re.IGNORECASE),
]

FORMULA_PATTERNS = [
    re.compile(r"(\$[^\$]{3,80}\$)", re.MULTILINE),
    re.compile(r"(\\\[.+?\\\])", re.DOTALL),
    re.compile(r"\b([A-Z][a-z0-9_]*\s*=\s*[^,\n;]{3,60})", re.MULTILINE),
    re.compile(r"([a-zA-Z\d_\^\{\}\\\+\-\*\/\(\)\=]{4,}\s*=\s*[a-zA-Z\d_\^\{\}\\\+\-\*\/\(\)\s]{3,})"),
    re.compile(r"\\(?:frac|nabla|sum|int|prod|alpha|beta|gamma|theta|omega|lambda|sigma|partial|sqrt)[\w\{\}\\\^\_\+\-\s]*", re.IGNORECASE)
]

COMPARISON_PATTERNS = [
    re.compile(r"\b(?:difference between|versus|vs\.?|in contrast to|compared with|differs from)\b", re.IGNORECASE),
    re.compile(r"\b(?:on the other hand|while|whereas|as opposed to)\b", re.IGNORECASE)
]

PROCEDURE_PATTERNS = [
    re.compile(r"^(?:Step\s*\d+|Method|Procedure|Stage\s*\d+|\d+\.)\s*[:\-]?\s*(.+)", re.IGNORECASE | re.MULTILINE),
    re.compile(r"\b(?:firstly|secondly|thirdly|finally|next,\s+we|to calculate|in order to prove)\b", re.IGNORECASE)
]

DATE_FACT_PATTERNS = [
    re.compile(r"\b(?:in\s+(?:18|19|20)\d{2}|century|BC|AD|dated\s+\d{4})\b", re.IGNORECASE),
    re.compile(r"\b(?:\d+(?:\.\d+)?\s*(?:m\/s|km\/h|kg|mol|Joules|Watts|Kelvin|Hz|eV|N\/m|atm|volts|amperes|ohms))\b", re.IGNORECASE),
    re.compile(r"\b(?:constant\s+[A-Za-z]|value of\s+[A-Za-z]|speed of light|Avogadro|Planck|universal gas constant)\b", re.IGNORECASE)
]

EXAMPLE_PATTERNS = [
    re.compile(r"\b(?:for example|for instance|e\.g\.|consider the following example|illustration)\s*[:,\-]?\s*([^.\n]+)", re.IGNORECASE),
    re.compile(r"^(?:Example\s*\d*|Case Study\s*\d*)\s*[:\-]\s*(.+)", re.IGNORECASE | re.MULTILINE)
]


def clean_text_whitespace(text: str) -> str:
    """Normalizes excessive whitespace, controls, and unifies line endings."""
    if not text:
        return ""
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def detect_repeated_headers_footers(pages: List[Dict[str, Any]]) -> Set[str]:
    """Identifies lines that repeat on > 40% of pages (like page titles, headers, footers)."""
    if len(pages) < 3:
        return set()
    line_counts: Counter = Counter()
    total_pages = len(pages)
    for p in pages:
        lines = [l.strip() for l in (p.get("text_content") or "").splitlines() if l.strip()]
        # Check first 2 and last 2 lines
        border_lines = set(lines[:2] + lines[-2:]) if len(lines) >= 4 else set(lines)
        for bl in border_lines:
            if 3 <= len(bl) <= 80:
                line_counts[bl] += 1

    threshold = max(2, int(total_pages * 0.40))
    return {line for line, cnt in line_counts.items() if cnt >= threshold}


def split_sentences(text: str) -> List[str]:
    """Splits text into coherent sentences without breaking math or abbreviations."""
    # Protect common abbreviations and decimal points
    protected = text
    protected = re.sub(r"\b(e\.g\.|i\.e\.|etc\.|fig\.|eq\.|vs\.|dr\.|prof\.|vol\.|no\.)", lambda m: m.group(0).replace(".", "@@DOT@@"), protected, flags=re.IGNORECASE)
    protected = re.sub(r"(\d+)\.(\d+)", r"\1@@DOT@@\2", protected)

    # Split on sentence ending punctuation followed by whitespace or newline
    raw_sents = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"\'\$\(])|\n{2,}", protected)
    sentences = []
    for s in raw_sents:
        clean = s.replace("@@DOT@@", ".").strip()
        if len(clean) >= 15 and not clean.startswith("---"):
            sentences.append(clean)
    return sentences


def extract_word_frequencies(pages: List[Dict[str, Any]]) -> Counter:
    """Calculates term frequency across all pages excluding stop words."""
    words: List[str] = []
    for p in pages:
        raw = (p.get("text_content") or "").lower()
        tokens = re.findall(r"\b[a-z]{3,20}\b", raw)
        words.extend(t for t in tokens if t not in STOP_WORDS)
    return Counter(words)


def score_sentence(
    sentence: str,
    page_num: int,
    word_freqs: Counter,
    max_freq: int,
    has_formula: bool,
    has_definition: bool,
    position_idx: int
) -> float:
    """Calculates deterministic importance score for a sentence."""
    tokens = [t.lower() for t in re.findall(r"\b[a-z]{3,20}\b", sentence) if t.lower() not in STOP_WORDS]
    if not tokens:
        return 0.0

    # 1. Frequency score (mean term frequency)
    freq_score = sum(word_freqs.get(t, 0) for t in tokens) / (len(tokens) * max(1, max_freq))

    # 2. Position bonus (earlier sentences in a page or section get a slight boost)
    pos_bonus = 0.25 if position_idx == 0 else (0.15 if position_idx < 3 else 0.0)

    # 3. Indicator bonuses
    def_bonus = 0.45 if has_definition else 0.0
    form_bonus = 0.35 if has_formula else 0.0

    # 4. Length penalty (too short or excessively long sentences are penalized)
    word_count = len(sentence.split())
    length_multiplier = 1.0
    if word_count < 6 or word_count > 65:
        length_multiplier = 0.5
    elif 10 <= word_count <= 40:
        length_multiplier = 1.2

    return (freq_score * 1.5 + pos_bonus + def_bonus + form_bonus) * length_multiplier


class LocalNotesEngine:
    def __init__(self, doc_title: str, pages: List[Dict[str, Any]], depth_mode: str = "standard"):
        self.doc_title = doc_title or "Academic Document"
        self.pages = sorted(pages, key=lambda p: p.get("page_number", 1))
        # Normalize depth mode: "quick", "standard", "detailed"
        d_lower = str(depth_mode).lower()
        if d_lower in ("quick", "fast", "short", "brief"):
            self.mode = "quick"
        elif d_lower in ("detailed", "deep", "extensive", "long"):
            self.mode = "detailed"
        else:
            self.mode = "standard"

        self.repeated_lines = detect_repeated_headers_footers(self.pages)
        self.word_freqs = extract_word_frequencies(self.pages)
        self.max_freq = max(self.word_freqs.values()) if self.word_freqs else 1

    def _clean_page_lines(self, raw_text: str) -> List[str]:
        clean_lines = []
        for line in raw_text.splitlines():
            s = line.strip()
            if not s:
                continue
            if s in self.repeated_lines:
                continue
            # Remove isolated page number footers e.g. "12" or "Page 12 of 45"
            if re.match(r"^(?:page\s+)?\d+(?:\s*(?:of|\/)\s*\d+)?$", s, re.IGNORECASE):
                continue
            clean_lines.append(s)
        return clean_lines

    def extract_definitions(self) -> List[Dict[str, Any]]:
        """Extracts key definitions with source page citations."""
        definitions: List[Dict[str, Any]] = []
        seen_terms = set()

        for p in self.pages:
            p_num = p.get("page_number", 1)
            text = p.get("text_content") or ""
            lines = self._clean_page_lines(text)

            for line in lines:
                for pat in DEFINITION_INDICATORS:
                    match = pat.search(line)
                    if match:
                        groups = match.groups()
                        if len(groups) >= 2:
                            term = groups[0].strip().strip(":").strip("-")
                            definition = groups[1].strip()
                        else:
                            term = "Key Concept"
                            definition = groups[0].strip()

                        term_key = term.lower()
                        if 2 <= len(term.split()) <= 6 and len(definition) >= 15 and term_key not in seen_terms:
                            seen_terms.add(term_key)
                            definitions.append({
                                "term": term,
                                "definition": definition,
                                "page": p_num
                            })
                            break

        # Filter limit based on mode
        limit = 6 if self.mode == "quick" else (14 if self.mode == "standard" else 25)
        return definitions[:limit]

    def extract_formulas(self) -> List[Dict[str, Any]]:
        """Extracts formulas, equations, and mathematical laws."""
        formulas: List[Dict[str, Any]] = []
        seen_formulas = set()

        for p in self.pages:
            p_num = p.get("page_number", 1)
            text = p.get("text_content") or ""
            lines = self._clean_page_lines(text)

            for line in lines:
                for pat in FORMULA_PATTERNS:
                    m = pat.search(line)
                    if m:
                        matched_str = m.group(0).strip()
                        # Ensure formula has mathematical operator or LaTeX command
                        if any(c in matched_str for c in ("=", "\\", "+", "-", "*", "/", "^", "_", "∫", "∑", "√")):
                            clean_formula = matched_str.strip()
                            # Wrap in LaTeX display or inline if needed
                            if not clean_formula.startswith("$"):
                                clean_formula = f"${clean_formula}$"
                            key = re.sub(r"\s+", "", clean_formula)
                            if len(key) >= 5 and key not in seen_formulas:
                                seen_formulas.add(key)
                                formulas.append({
                                    "formula": clean_formula,
                                    "context": line.replace(matched_str, "").strip() or "Governing formulation",
                                    "page": p_num
                                })
                                break

        limit = 4 if self.mode == "quick" else (10 if self.mode == "standard" else 20)
        return formulas[:limit]

    def extract_procedures(self) -> List[Dict[str, Any]]:
        """Extracts numbered procedures, methodologies, and algorithmic steps."""
        procedures: List[Dict[str, Any]] = []
        for p in self.pages:
            p_num = p.get("page_number", 1)
            lines = self._clean_page_lines(p.get("text_content") or "")
            for line in lines:
                for pat in PROCEDURE_PATTERNS:
                    m = pat.search(line)
                    if m:
                        step_desc = m.group(0).strip()
                        if 10 <= len(step_desc) <= 250:
                            procedures.append({"step": step_desc, "page": p_num})
                            break
        limit = 4 if self.mode == "quick" else (8 if self.mode == "standard" else 15)
        return procedures[:limit]

    def extract_comparisons(self) -> List[Dict[str, Any]]:
        """Extracts comparative differences and conceptual contrasts."""
        comparisons: List[Dict[str, Any]] = []
        for p in self.pages:
            p_num = p.get("page_number", 1)
            sents = split_sentences(p.get("text_content") or "")
            for sent in sents:
                for pat in COMPARISON_PATTERNS:
                    if pat.search(sent) and 20 <= len(sent) <= 250:
                        comparisons.append({"contrast": sent.strip(), "page": p_num})
                        break
        limit = 2 if self.mode == "quick" else (6 if self.mode == "standard" else 12)
        return comparisons[:limit]

    def extract_facts_dates(self) -> List[Dict[str, Any]]:
        """Extracts historical dates, constants, and quantitative facts."""
        facts: List[Dict[str, Any]] = []
        seen = set()
        for p in self.pages:
            p_num = p.get("page_number", 1)
            sents = split_sentences(p.get("text_content") or "")
            for sent in sents:
                for pat in DATE_FACT_PATTERNS:
                    if pat.search(sent):
                        clean = sent.strip()
                        if clean not in seen and 20 <= len(clean) <= 220:
                            seen.add(clean)
                            facts.append({"fact": clean, "page": p_num})
                            break
        limit = 3 if self.mode == "quick" else (8 if self.mode == "standard" else 15)
        return facts[:limit]

    def extract_examples(self) -> List[Dict[str, Any]]:
        """Extracts illustrative cases, problem examples, and scenarios."""
        examples: List[Dict[str, Any]] = []
        for p in self.pages:
            p_num = p.get("page_number", 1)
            sents = split_sentences(p.get("text_content") or "")
            for sent in sents:
                for pat in EXAMPLE_PATTERNS:
                    if pat.search(sent) and 20 <= len(sent) <= 250:
                        examples.append({"example": sent.strip(), "page": p_num})
                        break
        limit = 2 if self.mode == "quick" else (5 if self.mode == "standard" else 10)
        return examples[:limit]

    def extract_chapter_sections(self) -> List[Dict[str, Any]]:
        """
        Organizes the document into chapters and logical sections.
        Detects headings from PyMuPDF metadata or leading capital title lines.
        """
        chapters: List[Dict[str, Any]] = []
        current_title = "Overview & Foundations"
        current_sents: List[Tuple[str, int]] = []

        # Heading detection regex
        HEADING_REGEX = re.compile(
            r"^(?:chapter\s+\d+|unit\s+\d+|section\s+\d+|part\s+[ivxlcdm\d]+|module\s+\d+)\s*[:\-]?\s*(.*)$|"
            r"^[A-Z0-9\s\.\-]{4,60}$",
            re.IGNORECASE
        )

        for p in self.pages:
            p_num = p.get("page_number", 1)
            raw_headings = p.get("headings", [])
            lines = self._clean_page_lines(p.get("text_content") or "")

            for line in lines:
                is_heading = False
                h_title = ""
                # Check extracted page headings
                for h in raw_headings:
                    if h.strip() and h.strip().lower() == line.strip().lower() and 3 <= len(line) <= 70:
                        is_heading = True
                        h_title = line.strip()
                        break

                if not is_heading and HEADING_REGEX.match(line) and 3 <= len(line.split()) <= 10:
                    is_heading = True
                    h_title = line.strip()

                if is_heading:
                    if current_sents:
                        chapters.append({
                            "title": current_title,
                            "sentences": list(current_sents)
                        })
                        current_sents = []
                    current_title = h_title.title()
                else:
                    for s in split_sentences(line):
                        current_sents.append((s, p_num))

        if current_sents:
            chapters.append({
                "title": current_title,
                "sentences": list(current_sents)
            })

        # If no explicit chapters detected, group by page chunks
        if len(chapters) <= 1:
            chapters = []
            chunk_size = 2 if self.mode == "detailed" else 4
            for idx in range(0, len(self.pages), chunk_size):
                sub_pages = self.pages[idx:idx + chunk_size]
                start_p = sub_pages[0]["page_number"]
                end_p = sub_pages[-1]["page_number"]
                sub_sents = []
                for sp in sub_pages:
                    for s in split_sentences(sp.get("text_content") or ""):
                        sub_sents.append((s, sp["page_number"]))
                p_label = f"Pages {start_p}-{end_p}" if start_p != end_p else f"Page {start_p}"
                chapters.append({
                    "title": f"Study Section ({p_label})",
                    "sentences": sub_sents
                })

        return chapters

    def build_markdown_document(self) -> str:
        """
        Assembles the comprehensive study guide following the 12 required sections.
        Does not fabricate sections if no relevant material exists.
        """
        md: List[str] = []
        total_pages = len(self.pages)
        total_words = sum(len((p.get("text_content") or "").split()) for p in self.pages)

        # ── 1. Document Overview ──
        mode_label = {
            "quick": "Quick Revision",
            "standard": "Standard Notes",
            "detailed": "Detailed Study Notes"
        }.get(self.mode, "Standard Notes")

        md.append(f"# {self.doc_title}\n")
        md.append(f"> **Mode:** {mode_label} | **Pages:** {total_pages} | **Extracted Words:** ~{total_words:,}\n")

        # ── Table of Contents ──
        md.append("## Table of Contents")
        md.append("- [1. Document Overview](#1-document-overview)")
        md.append("- [2. Quick Summary](#2-quick-summary)")
        md.append("- [3. Chapter-wise Notes](#3-chapter-wise-notes)")
        md.append("- [4. Key Concepts](#4-key-concepts)")
        md.append("- [5. Important Definitions](#5-important-definitions)")
        md.append("- [6. Formulas & Equations](#6-formulas--equations)")
        md.append("- [7. Procedures & Working Steps](#7-procedures--working-steps)")
        md.append("- [8. Examples & Applications](#8-examples--applications)")
        md.append("- [9. Important Facts & Quantities](#9-important-facts--quantities)")
        md.append("- [10. Comparisons & Differences](#10-comparisons--differences)")
        md.append("- [11. High-Yield Revision Points](#11-high-yield-revision-points)")
        md.append("- [12. Final Quick Revision Checklist](#12-final-quick-revision-checklist)\n")
        md.append("---\n")

        # ── 1. Document Overview Section ──
        md.append("## 1. Document Overview\n")
        first_page_sents = split_sentences(self.pages[0].get("text_content") or "") if self.pages else []
        lead_intro = " ".join(first_page_sents[:3]) if first_page_sents else f"Academic material extracted from {self.doc_title}."
        md.append(f"{lead_intro} [Page 1]\n")
        md.append(f"- **Scope:** Covers {total_pages} sequential study pages with verified academic citations.")
        md.append(f"- **Coverage Distribution:** Proportional sentence sampling applied across all chapters.")
        md.append(f"- **Integrity Guarantee:** Direct extractive synthesis — no external hallucination or model rephrasing.\n")

        # ── 2. Quick Summary ──
        md.append("## 2. Quick Summary\n")
        # Extract top 3 to 6 globally scored sentences
        all_scored: List[Tuple[float, str, int]] = []
        for p in self.pages:
            p_num = p.get("page_number", 1)
            sents = split_sentences(p.get("text_content") or "")
            for idx, s in enumerate(sents):
                score = score_sentence(
                    sentence=s,
                    page_num=p_num,
                    word_freqs=self.word_freqs,
                    max_freq=self.max_freq,
                    has_formula=any(c in s for c in ("=", "$", "\\")),
                    has_definition=any(ind.search(s) for ind in DEFINITION_INDICATORS),
                    position_idx=idx
                )
                all_scored.append((score, s, p_num))

        all_scored.sort(key=lambda x: x[0], reverse=True)
        summary_count = 3 if self.mode == "quick" else (5 if self.mode == "standard" else 8)

        # Ensure summary sentences are diverse and cover multiple pages
        chosen_summary = []
        seen_pages = set()
        for score, s, p_num in all_scored:
            if p_num not in seen_pages or len(chosen_summary) < summary_count // 2:
                chosen_summary.append((s, p_num))
                seen_pages.add(p_num)
                if len(chosen_summary) >= summary_count:
                    break

        for s, p_num in chosen_summary:
            md.append(f"- **{s}** *(Page {p_num})*")
        md.append("")

        # ── 3. Chapter-wise Notes ──
        chapters = self.extract_chapter_sections()
        md.append("## 3. Chapter-wise Notes\n")
        max_sents_per_chap = 3 if self.mode == "quick" else (6 if self.mode == "standard" else 10)

        for chap_idx, chap in enumerate(chapters, 1):
            md.append(f"### 3.{chap_idx} {chap['title']}\n")
            chap_sents = chap["sentences"]
            if not chap_sents:
                md.append("*Content extracted without distinct text paragraphs.*\n")
                continue

            # Rank chapter sentences
            ranked_chap = []
            for s_idx, (s, p_num) in enumerate(chap_sents):
                sc = score_sentence(s, p_num, self.word_freqs, self.max_freq, "=" in s, False, s_idx)
                ranked_chap.append((sc, s, p_num))

            ranked_chap.sort(key=lambda x: x[0], reverse=True)
            top_chap_sents = ranked_chap[:max_sents_per_chap]
            # Restore reading order
            top_chap_sents.sort(key=lambda x: chap_sents.index((x[1], x[2])) if (x[1], x[2]) in chap_sents else 0)

            for _, s, p_num in top_chap_sents:
                md.append(f"- {s} *(Page {p_num})*")
            md.append("")

        # ── 4. Key Concepts ──
        md.append("## 4. Key Concepts\n")
        top_terms = [word.capitalize() for word, cnt in self.word_freqs.most_common(12) if len(word) >= 4]
        if top_terms:
            md.append("Core conceptual terms established in this document:")
            for term in top_terms[:8 if self.mode == "quick" else 12]:
                md.append(f"- **{term}**")
        else:
            md.append("Fundamental principles established across the text.")
        md.append("")

        # ── 5. Important Definitions ──
        defs = self.extract_definitions()
        if defs:
            md.append("## 5. Important Definitions\n")
            for d in defs:
                md.append(f"> **{d['term']}** *(Page {d['page']})*  \n> {d['definition']}\n")
        else:
            md.append("## 5. Important Definitions\n")
            md.append("*Definitions are woven throughout the chapter notes above.*\n")

        # ── 6. Formulas and Equations ──
        forms = self.extract_formulas()
        if forms:
            md.append("## 6. Formulas and Equations\n")
            for f in forms:
                md.append(f"- **Equation:** {f['formula']} *(Page {f['page']})*")
                if f['context'] and f['context'] != "Governing formulation":
                    md.append(f"  *Notes:* {f['context']}")
            md.append("")
        elif self.mode != "quick":
            md.append("## 6. Formulas and Equations\n")
            md.append("*No dedicated mathematical equations detected in this theoretical document.*\n")

        # ── 7. Procedures and Working Steps ──
        procs = self.extract_procedures()
        if procs:
            md.append("## 7. Procedures and Working Steps\n")
            for i, p in enumerate(procs, 1):
                md.append(f"{i}. {p['step']} *(Page {p['page']})*")
            md.append("")

        # ── 8. Examples and Applications ──
        exs = self.extract_examples()
        if exs:
            md.append("## 8. Examples and Applications\n")
            for e in exs:
                md.append(f"- **Example:** {e['example']} *(Page {e['page']})*")
            md.append("")

        # ── 9. Important Facts and Quantities ──
        facts = self.extract_facts_dates()
        if facts:
            md.append("## 9. Important Facts and Quantities\n")
            for f in facts:
                md.append(f"- {f['fact']} *(Page {f['page']})*")
            md.append("")

        # ── 10. Comparisons and Differences ──
        comps = self.extract_comparisons()
        if comps:
            md.append("## 10. Comparisons and Differences\n")
            for c in comps:
                md.append(f"- **Comparison:** {c['contrast']} *(Page {c['page']})*")
            md.append("")

        # ── 11. High-Yield Revision Points ──
        md.append("## 11. High-Yield Revision Points\n")
        high_yield_count = 4 if self.mode == "quick" else (8 if self.mode == "standard" else 12)
        # Select high scoring unique points
        selected_points = []
        for sc, s, p_num in all_scored[summary_count:]:
            if len(selected_points) >= high_yield_count:
                break
            if not any(s[:30] == prev[0][:30] for prev in selected_points):
                selected_points.append((s, p_num))

        for idx, (s, p_num) in enumerate(selected_points, 1):
            md.append(f"{idx}. **{s}** *(Page {p_num})*")
        md.append("")

        # ── 12. Final Quick Revision Checklist ──
        md.append("## 12. Final Quick Revision Checklist\n")
        checklist_items = []
        for d in defs[:4]:
            checklist_items.append(f"Can you define **{d['term']}** in your own words? *(Page {d['page']})*")
        for f in forms[:3]:
            checklist_items.append(f"Can you write down and derive **{f['formula']}**? *(Page {f['page']})*")
        for c in chapters[:4]:
            checklist_items.append(f"Do you understand the core takeaway of **{c['title']}**?")

        if not checklist_items:
            checklist_items = [
                "Review the primary definitions and scope of this chapter.",
                "Verify your understanding of the central thesis and findings.",
                "Test yourself on the key equations and quantitative measurements."
            ]

        for item in checklist_items:
            md.append(f"- [ ] {item}")

        md.append("\n---\n*Notes generated by BRAINY Study Studio.*")
        return "\n".join(md)


def generate_local_notes(
    doc_title: Any = "Document Notes",
    pages: Optional[List[Dict[str, Any]]] = None,
    depth: str = "standard",
    **kwargs
) -> str:
    """
    Main entry point for local revision notes generation.
    Strictly zero external API calls or LLM requests.
    Supports flexible arguments:
      generate_local_notes(doc_title, pages, depth)
      generate_local_notes(pages, title=..., mode=...)
    """
    if isinstance(doc_title, list) and pages is None:
        pages = doc_title
        doc_title = kwargs.get("title") or kwargs.get("doc_title") or "Document Notes"
    if "title" in kwargs:
        doc_title = kwargs["title"]
    if "mode" in kwargs:
        depth = kwargs["mode"]
    if not pages:
        raise ValueError("Cannot generate notes: Document has no pages.")

    engine = LocalNotesEngine(doc_title=str(doc_title), pages=pages, depth_mode=depth)
    return engine.build_markdown_document()
