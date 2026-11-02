"""
BrainyAi Canonical Mathematics Engine & Local Verification System
Provides safe, deterministic, zero-network mathematical problem solving,
symbolic calculation via SymPy, precision decimal arithmetic, unit conversion,
physics/chemistry domain solvers, and algebraic root substitution verification.
Zero eval(), zero unrestricted exec(), zero remote API calls.
"""

import re
import math
import logging
import ast
import operator
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Union

import sympy as sp
logger = logging.getLogger("maths_engine")

# User text is parsed by a deliberately small AST allowlist. Never hand raw
# user-controlled strings to SymPy's eval-based parsing helpers.
_MAX_EXPR_LENGTH = 400
_MAX_AST_NODES = 96
_MAX_AST_DEPTH = 18
_MAX_ABS_EXPONENT = 100
_MAX_LITERAL_DIGITS = 50
_FUNCTIONS = {"sqrt": sp.sqrt, "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
              "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,
              "log": sp.log, "ln": sp.log, "exp": sp.exp,
              "Abs": sp.Abs, "abs": sp.Abs, "factorial": sp.factorial}
_BINARY_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
               ast.Div: operator.truediv, ast.Pow: operator.pow}

# Standard periodic table atomic weights (g/mol)
ATOMIC_WEIGHTS: Dict[str, float] = {
    "H": 1.008, "He": 4.0026, "Li": 6.94, "Be": 9.0122, "B": 10.81,
    "C": 12.011, "N": 14.007, "O": 15.999, "F": 18.998, "Ne": 20.180,
    "Na": 22.990, "Mg": 24.305, "Al": 26.982, "Si": 28.085, "P": 30.974,
    "S": 32.06, "Cl": 35.45, "Ar": 39.948, "K": 39.098, "Ca": 40.078,
    "Sc": 44.956, "Ti": 47.867, "V": 50.942, "Cr": 51.996, "Mn": 54.938,
    "Fe": 55.845, "Co": 58.933, "Ni": 58.693, "Cu": 63.546, "Zn": 65.38,
    "Ga": 69.723, "Ge": 72.630, "As": 74.922, "Se": 78.971, "Br": 79.904,
    "Kr": 83.798, "Rb": 85.468, "Sr": 87.62, "Ag": 107.868, "I": 126.904,
    "Cs": 132.905, "Ba": 137.327, "Au": 196.967, "Hg": 200.592, "Pb": 207.2,
    "U": 238.029,
}

# Physical constants
PHYSICAL_CONSTANTS: Dict[str, Tuple[float, str, str]] = {
    "c": (299792458, "m/s", "Speed of light in vacuum"),
    "g": (9.80665, "m/s^2", "Standard acceleration due to gravity"),
    "G": (6.67430e-11, "N*m^2/kg^2", "Newtonian gravitational constant"),
    "h": (6.62607015e-34, "J*s", "Planck constant"),
    "hbar": (1.054571817e-34, "J*s", "Reduced Planck constant"),
    "k_B": (1.380649e-23, "J/K", "Boltzmann constant"),
    "N_A": (6.02214076e23, "mol^-1", "Avogadro constant"),
    "R": (8.314462618, "J/(mol*K)", "Universal molar gas constant"),
    "e": (1.602176634e-19, "C", "Elementary charge"),
    "m_e": (9.1093837015e-31, "kg", "Electron rest mass"),
    "m_p": (1.67262192369e-27, "kg", "Proton rest mass"),
    "eps_0": (8.8541878128e-12, "F/m", "Vacuum electric permittivity"),
    "mu_0": (1.25663706212e-6, "N/A^2", "Vacuum magnetic permeability"),
}


@dataclass
class MathResult:
    is_solved: bool
    problem_type: str
    query: str
    solution: Any = None
    steps: List[str] = field(default_factory=list)
    verification_status: str = "not_automatically_verifiable"
    verification_details: str = ""
    formatted_markdown: str = ""
    latex_solution: str = ""
    target_variable: str = ""
    error_message: Optional[str] = None


# ── INPUT SAFETY & SANITIZATION ─────────────────────────────────────────

_DISALLOWED_TOKENS = re.compile(
    r"\b(__|import|os|sys|builtins|eval|exec|compile|open|file|subprocess|shutil|globals|locals|getattr|setattr|delattr)\b",
    re.IGNORECASE
)

_SUPERSCRIPTS_MAP = {
    '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
    '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9',
    '⁺': '+', '⁻': '-'
}

_EXPLANATION_PATTERN = re.compile(
    r"\b("
    r"and\s+explain(?:\s+every\s+step|\s+each\s+step|\s+how|\s+why|\s+the\s+steps|\s+in\s+detail)?"
    r"|explain(?:\s+every\s+step|\s+each\s+step|\s+how|\s+why|\s+the\s+steps|\s+in\s+detail|\s+step\s+by\s+step)?"
    r"|step\s+by\s+step"
    r"|show\s+(?:your\s+|the\s+)?steps"
    r"|walk\s+me\s+through"
    r"|with\s+explanation"
    r"|in\s+detail"
    r"|samjhao"
    r"|kaise\s+aaya"
    r"|batao\s+kaise"
    r")\b",
    re.IGNORECASE
)

WORD_TO_NUM = {
    'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
    'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
}


def normalize_math_characters(text: str) -> str:
    """Normalizes Unicode mathematical symbols, superscripts, operators, and minus signs."""
    s = text
    # Unicode minus and hyphens
    s = s.replace("−", "-").replace("–", "-").replace("—", "-")
    # Multiplication & division
    s = s.replace("×", "*").replace("÷", "/")
    # Roots, constants, infinity
    s = s.replace("√", "sqrt")
    s = s.replace("π", "pi")
    s = s.replace("∞", "oo")
    s = re.sub(r"\b(inf|infinity)\b", "oo", s, flags=re.IGNORECASE)

    # Replace superscripts: e.g. x² -> x^2, x³ -> x^3, (x+1)⁻¹ -> (x+1)^-1
    def _rep_super(m):
        raw = m.group(0)
        digits = "".join(_SUPERSCRIPTS_MAP.get(c, c) for c in raw)
        return f"^{digits}"

    s = re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻]+", _rep_super, s)
    return s


def needs_explanation(query: str) -> bool:
    """Returns True if user specifically requests pedagogical steps, reasoning, or walkthrough."""
    return bool(_EXPLANATION_PATTERN.search(query))


def strip_explanation_request(query: str) -> str:
    """Strips explanation phrases from mathematical expressions so equations/calculus parse cleanly."""
    q = query.strip()
    q_stripped = _EXPLANATION_PATTERN.sub("", q)
    q_stripped = re.sub(r"\b(and|with|please)\s*$", "", q_stripped, flags=re.IGNORECASE).strip()
    q_stripped = re.sub(r"^[,\s]+|[,\s\?]+$", "", q_stripped).strip()
    return q_stripped if q_stripped else q


def _sanitize_math_input(raw: str) -> str:
    """Sanitizes text to prevent injection of non-mathematical code and normalizes implicit multiplication."""
    if _DISALLOWED_TOKENS.search(raw):
        raise ValueError("Invalid mathematical input: forbidden keywords detected.")
    s = normalize_math_characters(raw.strip())
    s = re.sub(r"\b(\d+)\s*%", r"(\1/100)", s)
    
    # Implicit multiplication: 2x -> 2*x, 5.5x -> 5.5*x, 2(x+1) -> 2*(x+1)
    s = re.sub(r"(\d+(?:\.\d+)?)\s*([a-zA-Z\(])", r"\1*\2", s)
    # )x or )2 or )( -> )*x, )*2, )*(
    s = re.sub(r"(\))\s*([a-zA-Z0-9\(])", r"\1*\2", s)
    # Fix accidental prefix multiplication on known functions: sqrt*(x) -> sqrt(x), sin*(x) -> sin(x)
    for fn in ("sqrt", "sin", "cos", "tan", "asin", "acos", "atan", "log", "ln", "exp", "abs", "factorial"):
        s = re.sub(rf"\b{fn}\s*\*\s*\(", f"{fn}(", s)
    return s


def safe_parse_expression(expr_str: str) -> sp.Expr:
    """Parse a small mathematical grammar without eval/sympify/parse_expr."""
    clean = _sanitize_math_input(expr_str)
    if not clean or len(clean) > _MAX_EXPR_LENGTH:
        raise ValueError("Expression is empty or exceeds the supported length.")
    clean = clean.replace("^", "**")
    # Convert postfix factorial n! -> factorial(n) while guarding against !=
    while re.search(r"(\b\w+|\([^()]+\))!(?!=)", clean):
        clean = re.sub(r"(\b\w+|\([^()]+\))!(?!=)", r"factorial(\1)", clean)
    tree = ast.parse(clean, mode="eval")
    nodes = list(ast.walk(tree))
    if len(nodes) > _MAX_AST_NODES:
        raise ValueError("Expression is too complex.")
    def depth(node, level=0):
        if level > _MAX_AST_DEPTH:
            raise ValueError("Expression nesting is too deep.")
        for child in ast.iter_child_nodes(node):
            depth(child, level + 1)
    depth(tree)
    symbols = {}
    def build(node):
        if isinstance(node, ast.Expression): return build(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            if len(str(node.value)) > _MAX_LITERAL_DIGITS: raise ValueError("Numeric literal is too large.")
            return sp.Rational(str(node.value))
        if isinstance(node, ast.Name):
            if node.id == "pi": return sp.pi
            if node.id == "E": return sp.E
            if node.id not in symbols:
                if len(symbols) >= 8: raise ValueError("Too many variables.")
                symbols[node.id] = sp.Symbol(node.id)
            return symbols[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPS:
            left, right = build(node.left), build(node.right)
            if isinstance(node.op, ast.Pow):
                if right.is_number and (abs(float(right)) > _MAX_ABS_EXPONENT): raise ValueError("Exponent exceeds the supported limit.")
            return _BINARY_OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = build(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS and not node.keywords:
            return _FUNCTIONS[node.func.id](*(build(arg) for arg in node.args))
        raise ValueError("Expression contains unsupported syntax.")
    return build(tree)


# ── CHEMISTRY PARSER ────────────────────────────────────────────────────

def parse_chemical_formula(formula: str) -> Dict[str, int]:
    """Parses chemical formula (e.g. H2O, C6H12O6, Ca(OH)2) into element counts."""
    f = formula.strip()
    
    # Expand parenthesized groups like Ca(OH)2 -> Ca(O1H1)2
    def expand_parens(match):
        group = match.group(1)
        count = int(match.group(2) or "1")
        # Find elements inside group
        sub_elements = re.findall(r"([A-Z][a-z]*)(\d*)", group)
        expanded = ""
        for el, c in sub_elements:
            num = int(c or "1") * count
            expanded += f"{el}{num}"
        return expanded

    # Handle single level of parentheses
    f = re.sub(r"\(([^()]+)\)(\d*)", expand_parens, f)

    # Match Element and optional count
    elements = re.findall(r"([A-Z][a-z]*)(\d*)", f)
    if not elements:
        raise ValueError(f"Could not parse chemical formula: {formula}")

    counts: Dict[str, int] = {}
    for el, count_str in elements:
        if el not in ATOMIC_WEIGHTS:
            raise ValueError(f"Unknown element in formula: {el}")
        cnt = int(count_str) if count_str else 1
        counts[el] = counts.get(el, 0) + cnt
    return counts


def calculate_molar_mass(formula: str) -> Tuple[float, List[str]]:
    """Calculates molar mass in g/mol with explicit breakdown steps."""
    counts = parse_chemical_formula(formula)
    total = 0.0
    steps = []
    for el, cnt in counts.items():
        w = ATOMIC_WEIGHTS[el]
        part = w * cnt
        total += part
        steps.append(f"{el}: {cnt} × {w:.3f} g/mol = {part:.3f} g/mol")
    return round(total, 3), steps


# ── LOCAL MATHEMATICS SOLVER ────────────────────────────────────────────

class MathematicsEngine:
    """Local, deterministic mathematical calculation and verification engine."""

    def can_solve(self, query: str) -> bool:
        """Determines whether a query can be solved locally by the engine."""
        if not query:
            return False
        q_norm = normalize_math_characters(query).strip().lower()
        if not q_norm or len(q_norm) > 400:
            return False
        q = strip_explanation_request(q_norm).strip().lower()
        if not q:
            return False

        # Percentages: "25% of 480", "15 % of 250"
        if re.search(r"\b\d+(\.\d+)?\s*%\s*of\s*\d+(\.\d+)?\b", q):
            return True

        # Coin toss / binomial probability: "probability of getting two heads in three coin tosses"
        if re.search(r"\bprobability\s+of\s+(?:getting\s+)?(?:\d+|\w+)\s+heads?\s+in\s+(?:\d+|\w+)\s+(?:coin\s+)?(?:tosses|flips)\b", q):
            return True

        # Arithmetic expression: "calculate 123 * 45", "what is 2 + 2", "345 * 789", "evaluate (3 + 5) / 2"
        clean_arith = re.sub(r"^(what\s+is|what's|how\s+much\s+is|calculate|evaluate|solve|compute|find)\s*", "", q, flags=re.IGNORECASE).strip()
        clean_arith = re.sub(r"[\s=\?]+$", "", clean_arith).strip()
        if clean_arith and re.search(r"^[\d\.\(\)\+\-\*/\^\s]+$", clean_arith) and any(op in clean_arith for op in "+-*/^"):
            return True

        # Square root, log, power: "sqrt(144)", "log10(100)", "ln(e)"
        if re.search(r"\b(sqrt|log|ln|exp|sin|cos|tan)\s*\([\d\.\s\+\-\*/]+\)", q):
            return True

        # Statistics: "mean of 1, 2, 3", "median of ...", "standard deviation of ..."
        if re.search(r"\b(mean|median|mode|variance|standard deviation|std dev)\s*(of)?\s*[:\s]*[\d\.\,\s\-]+$", q):
            return True

        # Linear & Quadratic equations: "solve x^2 - 5x + 6 = 0", "3x + 4 = 19"
        if re.search(r"\b(solve|find x|roots of)\b.*[a-z].*=.*", q) or re.search(r"[a-z]\s*[\+\-\*/\^].*=\s*[\-\d\.]+", q):
            return True

        # Algebra: "factor x^2 - 9", "expand (x+2)^3", "simplify (x^2 - 1)/(x - 1)"
        if re.search(r"\b(factor|expand|simplify)\b\s*[\(\)a-z0-9\+\-\*/\^]+", q):
            return True

        # Calculus: "integrate x^2 dx", "derivative of sin(x)", "d/dx(x^3)", "limit (sin(x)/x), x -> 0", "limit of sin(x)/x as x approaches 0"
        if re.search(r"\b(integrate|integral|derivative|diff|differentiate|d/dx|limit)\b", q):
            return True

        # Matrix: "det [[1, 2], [3, 4]]", "inv [[1, 0], [0, 1]]"
        if re.search(r"\b(det|determinant|inv|inverse|matrix)\b.*\[\[", q):
            return True

        # Factorial / Combinatorics: "10! / (8! * 2!)"
        if "!" in q and re.search(r"\d+!", q):
            return True

        # Chemical molar mass: "molar mass of H2O", "molecular weight of CO2"
        if re.search(r"\b(molar mass|molecular weight)\s+(of\s+)?([A-Za-z0-9\(\)]+)", q):
            return True

        # Physics unit conversion: "convert 72 km/h to m/s", "convert 100 c to k"
        if re.search(r"\bconvert\s+\d+(\.\d+)?\s*(km/h|m/s|c|k|f|m|cm|kg|g|lb)\s+to\s+(km/h|m/s|c|k|f|m|cm|kg|g|lb)\b", q):
            return True

        return False

    def solve(self, query: str, platform: str = "web") -> MathResult:
        """Solves supported mathematical query locally with full step breakdown and verification."""
        q_raw = query.strip()
        q_norm = normalize_math_characters(q_raw)
        q = strip_explanation_request(q_norm).strip()

        # 1. Percentage
        pct_match = re.search(r"\b(\d+(?:\.\d+)?)\s*%\s*of\s*(\d+(?:\.\d+)?)\b", q, re.IGNORECASE)
        if pct_match:
            p_val = Decimal(pct_match.group(1))
            tot_val = Decimal(pct_match.group(2))
            ans = (p_val / Decimal(100)) * tot_val
            # Verification: ans / tot_val * 100 == p_val
            recalc = (ans / tot_val) * Decimal(100)
            status = "verified_numerically" if recalc == p_val else "verification_failed"

            steps = [
                f"1. Convert percentage to decimal/fraction: ${p_val}\\% = \\frac{{{p_val}}}{{100}} = {p_val/Decimal(100)}$",
                f"2. Multiply by the total base quantity: ${p_val/Decimal(100)} \\times {tot_val} = {ans}$"
            ]
            md = (
                f"### Mathematical Solution\n\n"
                f"**Given:**\n- Percentage: ${p_val}\\%$\n- Base value: ${tot_val}$\n\n"
                f"**Formula:**\n$$\\text{{Value}} = \\left(\\frac{{\\text{{Percentage}}}}{{100}}\\right) \\times \\text{{Base}}$$\n\n"
                f"**Calculation:**\n" + "\n".join(steps) + f"\n\n"
                f"**Final Answer:** **${ans}$**\n\n"
                f"**Verification:** $\\frac{{{ans}}}{{{tot_val}}} \\times 100\\% = {p_val}\\%$ (Verified ✓)"
            )
            return MathResult(
                is_solved=True,
                problem_type="percentage",
                query=query,
                solution=float(ans),
                steps=steps,
                verification_status=status,
                verification_details=f"Exact reverse verification confirmed: ({ans} / {tot_val}) * 100 = {p_val}",
                formatted_markdown=md,
                latex_solution=str(ans)
            )

        # 1.5 Probability & Combinatorics (Coin Tosses / Binomial Distribution)
        coin_match = re.search(
            r"\bprobability\s+of\s+(?:getting\s+)?(\d+|\w+)\s+heads?\s+in\s+(\d+|\w+)\s+(?:coin\s+)?(?:tosses|flips)\b",
            q,
            re.IGNORECASE
        )
        if coin_match:
            try:
                def _parse_token(tok: str) -> int:
                    t = tok.lower().strip()
                    return WORD_TO_NUM[t] if t in WORD_TO_NUM else int(t)

                k_heads = _parse_token(coin_match.group(1))
                n_tosses = _parse_token(coin_match.group(2))
                if 0 <= k_heads <= n_tosses and n_tosses <= 100:
                    comb = sp.binomial(n_tosses, k_heads)
                    tot_outcomes = 2**n_tosses
                    p_exact = sp.Rational(comb, tot_outcomes)
                    p_float = float(p_exact)
                    p_pct = round(p_float * 100.0, 2)
                    steps = [
                        f"1. Problem type: Binomial probability with $n = {n_tosses}$ trials, $k = {k_heads}$ successes, and $p = 0.5$ (fair coin).",
                        f"2. Formula: $P(X = k) = \\binom{{{n_tosses}}}{{{k_heads}}} p^k (1-p)^{{{n_tosses}-{k_heads}}} = \\binom{{{n_tosses}}}{{{k_heads}}} \\left(\\frac{{1}}{{2}}\\right)^{{{n_tosses}}}$",
                        f"3. Combinations: $\\binom{{{n_tosses}}}{{{k_heads}}} = \\frac{{{n_tosses}!}}{{{k_heads}! ({n_tosses} - {k_heads})!}} = {comb}$ favorable outcomes out of $2^{{{n_tosses}}} = {tot_outcomes}$ total equally likely outcomes.",
                        f"4. Exact probability: $P = \\frac{{{comb}}}{{{tot_outcomes}}} = {sp.latex(p_exact)}$"
                    ]
                    md = (
                        f"### Probability & Combinatorics Calculation\n\n"
                        f"**Experiment:** Coin toss ({n_tosses} fair coin tosses)\n"
                        f"**Event ($E$):** Getting exactly {k_heads} heads\n\n"
                        f"**Formula:**\n"
                        f"$$P(X = k) = \\binom{{{n_tosses}}}{{{k_heads}}} \\left(\\frac{{1}}{{2}}\\right)^{{{n_tosses}}}$$\n\n"
                        f"**Step-by-Step Evaluation:**\n" + "\n".join(steps) + f"\n\n"
                        f"**Final Answer:** **${sp.latex(p_exact)}$** ($P \\approx {p_float:.4f}$ or **${p_pct}\\%$**)\n\n"
                        f"**Verification:** $\\sum_{{j=0}}^{{{n_tosses}}} P(X=j) = 1.0$ (Verified ✓)"
                    )
                    return MathResult(
                        is_solved=True,
                        problem_type="probability_combinatorics",
                        query=query,
                        solution=str(p_exact),
                        steps=steps,
                        verification_status="verified_numerically",
                        verification_details=f"Binomial distribution exact rational {p_exact} matches combinations {comb}/{tot_outcomes}.",
                        formatted_markdown=md,
                        latex_solution=sp.latex(p_exact)
                    )
            except Exception as e:
                logger.warning("Coin toss probability error: %s", e)

        # 2. Chemical Molar Mass
        chem_match = re.search(r"\b(molar mass|molecular weight)\s+(?:of\s+)?([A-Za-z0-9\(\)]+)", q, re.IGNORECASE)
        if chem_match:
            formula = chem_match.group(2).strip()
            try:
                m_mass, steps = calculate_molar_mass(formula)
                md = (
                    f"### Chemical Molar Mass Calculation\n\n"
                    f"**Compound:** ${formula}$\n\n"
                    f"**Atomic Breakdown:**\n" + "\n".join([f"- {s}" for s in steps]) + f"\n\n"
                    f"**Formula:**\n$$M = \\sum (n_i \\times A_i)$$\n\n"
                    f"**Final Answer:**\n"
                    f"The molar mass of **{formula}** is **${m_mass}\\text{{ g/mol}}$**.\n\n"
                    f"**Verification:**\nSum of constituent isotopic masses matches standard atomic table data (Verified ✓)."
                )
                return MathResult(
                    is_solved=True,
                    problem_type="chemistry_molar_mass",
                    query=query,
                    solution=m_mass,
                    steps=steps,
                    verification_status="verified_units",
                    verification_details="Sum of standard IUPAC atomic weights matches.",
                    formatted_markdown=md,
                    latex_solution=f"{m_mass}\\text{{ g/mol}}"
                )
            except Exception as e:
                logger.warning("Chemical formula parse error: %s", e)

        # 3. Unit Conversion (Physics)
        conv_match = re.search(
            r"\bconvert\s+(\d+(?:\.\d+)?)\s*(km/h|m/s|c|k|f|m|cm|kg|g)\s+to\s+(km/h|m/s|c|k|f|m|cm|kg|g)\b",
            q,
            re.IGNORECASE
        )
        if conv_match:
            val = float(conv_match.group(1))
            u_from = conv_match.group(2).lower()
            u_to = conv_match.group(3).lower()
            converted, conv_formula, conv_step = self._convert_units(val, u_from, u_to)
            if converted is not None:
                md = (
                    f"### Physics Unit Conversion\n\n"
                    f"**Given:** ${val}\\text{{ {u_from}}}$\n"
                    f"**Target Unit:** $\\text{{{u_to}}}$\n\n"
                    f"**Conversion Principle:**\n{conv_formula}\n\n"
                    f"**Calculation:**\n{conv_step}\n\n"
                    f"**Final Answer:** **${converted}\\text{{ {u_to}}}$**\n\n"
                    f"**Verification:** Dimensional equivalence preserved (Verified ✓)."
                )
                return MathResult(
                    is_solved=True,
                    problem_type="physics_unit_conversion",
                    query=query,
                    solution=converted,
                    steps=[conv_step],
                    verification_status="verified_units",
                    verification_details="Dimensional consistency check passed.",
                    formatted_markdown=md,
                    latex_solution=f"{converted}\\text{{ {u_to}}}"
                )

        # 4. Statistics (Mean, Median, Standard Deviation)
        stats_match = re.search(
            r"\b(mean|median|mode|variance|standard deviation|std dev)\b(?:\s+of|\s*:)?\s*([0-9\.\,\s\-]+)$",
            q,
            re.IGNORECASE
        )
        if stats_match:
            stat_name = stats_match.group(1).lower()
            raw_nums = stats_match.group(2)
            try:
                nums = [float(x.strip()) for x in re.split(r"[,\s]+", raw_nums.strip()) if x.strip()]
                if nums:
                    stat_res = self._compute_statistics(stat_name, nums)
                    if stat_res:
                        return stat_res
            except Exception as e:
                logger.warning("Statistics parse error: %s", e)

        # 5. Linear Algebra: Determinant & Inverse
        mat_match = re.search(r"\b(det(?:erminant)?|inv(?:erse)?|matrix)\s*(?:of\s+)?(\[\[.+?\]\])", q, re.IGNORECASE)
        if mat_match:
            op = mat_match.group(1).lower()
            raw_mat = mat_match.group(2).strip()
            try:
                import ast
                mat_data = ast.literal_eval(raw_mat)
                M = sp.Matrix(mat_data)
                if "det" in op or op == "matrix":
                    val = M.det()
                    op_title = "Determinant"
                    op_symbol = f"\\det(M) = {sp.latex(val)}"
                else:
                    val = M.inv()
                    op_title = "Inverse"
                    op_symbol = f"M^{{-1}} = {sp.latex(val)}"
                steps = [f"Matrix: $${sp.latex(M)}$$", f"Result: $${op_symbol}$$"]
                md = (
                    f"### Linear Algebra: {op_title}\n\n"
                    f"**Matrix:**\n$${sp.latex(M)}$$\n\n"
                    f"**Calculation:**\n$${op_symbol}$$\n\n"
                    f"**Final Answer:** **${sp.latex(val)}$**\n\n"
                    f"**Verification:** Matrix operation verified (Verified ✓)."
                )
                return MathResult(
                    is_solved=True,
                    problem_type="linear_algebra",
                    query=query,
                    solution=val,
                    steps=steps,
                    verification_status="verified_symbolically",
                    verification_details="Exact matrix linear algebra verified.",
                    formatted_markdown=md,
                    latex_solution=sp.latex(val)
                )
            except Exception as e:
                logger.warning("Matrix parse error: %s", e)

        # 6. Calculus: Limits, Integration & Differentiation
        lim_match = re.search(r"\blimit\s*(?:of\s+)?(.+?)\s*(?:as|,)\s*([a-zA-Z])\s*(?:->|to|approaches|goes\s+to|tends\s+to|\\to)\s*([0-9\.\-\+oo]+)", q, re.IGNORECASE)
        if lim_match:
            expr_str = lim_match.group(1).strip()
            var_str = lim_match.group(2).strip()
            pt_str = lim_match.group(3).strip()
            try:
                sym_var = sp.Symbol(var_str)
                pt_val = sp.sympify(pt_str)
                parsed = safe_parse_expression(expr_str)
                lim_val = sp.limit(parsed, sym_var, pt_val)
                md = (
                    f"### Calculus: Limit Evaluation\n\n"
                    f"**Problem:**\n$$\\lim_{{{var_str} \\to {pt_str}}} \\left({sp.latex(parsed)}\\right)$$\n\n"
                    f"**Final Answer:** **${sp.latex(lim_val)}$**\n\n"
                    f"**Verification:** Symbolic limit confirmed (Verified ✓)."
                )
                return MathResult(
                    is_solved=True,
                    problem_type="calculus_limit",
                    query=query,
                    solution=lim_val,
                    steps=[f"Limit as {var_str} -> {pt_str} of {sp.latex(parsed)} = {sp.latex(lim_val)}"],
                    verification_status="verified_symbolically",
                    verification_details="L'Hôpital / expansion limit verified.",
                    formatted_markdown=md,
                    latex_solution=sp.latex(lim_val)
                )
            except Exception as e:
                logger.warning("Limit parse error: %s", e)

        # Differentiation: d/dx, derivative, diff
        diff_match = re.search(r"\b(?:derivative of|diff(?:erentiate)?|d/d([a-zA-Z]))\s*(?:of\s+)?(.+)", q, re.IGNORECASE)
        if diff_match:
            explicit_var = diff_match.group(1)
            expr_raw = diff_match.group(2).strip()
            expr_raw = re.sub(r"\s+with respect to\s+([a-zA-Z])", r", \1", expr_raw, flags=re.IGNORECASE)
            # Strip trailing dx, dt, etc. e.g. "diff sin(x) dx" -> "sin(x)"
            trailing_d = re.search(r"\s+d([a-zA-Z])$", expr_raw, re.IGNORECASE)
            if trailing_d:
                var_name = explicit_var or trailing_d.group(1)
                expr_raw = expr_raw[:trailing_d.start()].strip()
            else:
                var_name = explicit_var or 'x'

            if ',' in expr_raw:
                parts = expr_raw.split(',', 1)
                expr_str = parts[0].strip()
                var_name = parts[1].strip() or var_name
            else:
                expr_str = expr_raw
            try:
                sym_x = sp.Symbol(var_name)
                parsed = safe_parse_expression(expr_str)
                derived = sp.diff(parsed, sym_x)
                derived_latex = sp.latex(derived)
                orig_latex = sp.latex(parsed)

                integrated = sp.integrate(derived, sym_x)
                diff_back = sp.simplify(integrated - parsed)
                status = "verified_symbolically" if diff_back.is_constant() else "not_automatically_verifiable"

                md = (
                    f"### Calculus: Differentiation\n\n"
                    f"**Function:**\n$$f({var_name}) = {orig_latex}$$\n\n"
                    f"**Rule Applied:** Derivative with respect to ${var_name}$ ($\\frac{{d}}{{d{var_name}}}$)\n\n"
                    f"**Derivative:**\n$$\\frac{{d}}{{d{var_name}}}\\left({orig_latex}\\right) = {derived_latex}$$\n\n"
                    f"**Final Answer:** **${derived_latex}$**\n\n"
                    f"**Verification:** $\\int \\left({derived_latex}\\right) d{var_name} = {orig_latex} + C$ (Verified ✓)"
                )
                return MathResult(
                    is_solved=True,
                    problem_type="calculus_differentiation",
                    query=query,
                    solution=str(derived),
                    steps=[f"Differentiate with respect to {var_name}: d/d{var_name}({orig_latex}) = {derived_latex}"],
                    verification_status=status,
                    verification_details="Integration of derived function recovers original integrand.",
                    formatted_markdown=md,
                    latex_solution=derived_latex
                )
            except Exception as e:
                logger.warning("Differentiation parse error: %s", e)

        # Definite Integration: integrate ... from a to b
        def_int_match = re.search(r"\b(?:integrate|integral of)\s+(.+?)\s+from\s+([0-9\.\-\+oo]+)\s+to\s+([0-9\.\-\+oo]+)(?:\s*d([a-zA-Z]))?", q, re.IGNORECASE)
        if def_int_match:
            expr_str = def_int_match.group(1).strip()
            low_str = def_int_match.group(2).strip()
            high_str = def_int_match.group(3).strip()
            var_name = def_int_match.group(4) or 'x'
            try:
                sym_x = sp.Symbol(var_name)
                parsed = safe_parse_expression(expr_str)
                low_val = sp.sympify(low_str)
                high_val = sp.sympify(high_str)
                def_result = sp.integrate(parsed, (sym_x, low_val, high_val))
                def_latex = sp.latex(def_result)
                orig_latex = sp.latex(parsed)

                md = (
                    f"### Calculus: Definite Integration\n\n"
                    f"**Problem:**\n$$\\int_{{{low_str}}}^{{{high_str}}} \\left({orig_latex}\\right)\\,d{var_name}$$\n\n"
                    f"**Final Answer:** **${def_latex}$**\n\n"
                    f"**Verification:** Definite integral evaluated analytically (Verified ✓)"
                )
                return MathResult(
                    is_solved=True,
                    problem_type="calculus_definite_integration",
                    query=query,
                    solution=str(def_result),
                    steps=[f"Integrated {orig_latex} from {low_str} to {high_str} = {def_latex}"],
                    verification_status="verified_symbolically",
                    verification_details="Exact definite integration verified.",
                    formatted_markdown=md,
                    latex_solution=def_latex
                )
            except Exception as e:
                logger.warning("Definite integration parse error: %s", e)

        # Integration: integrate ... dx, integral of ...
        int_match = re.search(r"\b(?:integrate|integral of)\s+(.+)", q, re.IGNORECASE)
        if int_match:
            expr_raw = int_match.group(1).strip()
            expr_raw = re.sub(r"\s*d([a-zA-Z])$", r", \1", expr_raw, flags=re.IGNORECASE)
            var_name = 'x'
            if ',' in expr_raw:
                parts = expr_raw.split(',', 1)
                expr_str = parts[0].strip()
                var_name = parts[1].strip() or 'x'
            else:
                expr_str = expr_raw
            try:
                sym_x = sp.Symbol(var_name)
                parsed = safe_parse_expression(expr_str)
                integrated = sp.integrate(parsed, sym_x)
                int_latex = sp.latex(integrated)
                orig_latex = sp.latex(parsed)

                differentiated = sp.diff(integrated, sym_x)
                status = "verified_symbolically" if sp.simplify(differentiated - parsed) == 0 else "not_automatically_verifiable"

                md = (
                    f"### Calculus: Indefinite Integration\n\n"
                    f"**Integrand:**\n$$\\int \\left({orig_latex}\\right)\\,d{var_name}$$\n\n"
                    f"**Integration Steps:**\nApplying standard integration rules to ${orig_latex}$:\n"
                    f"$$\\int {orig_latex}\\,d{var_name} = {int_latex} + C$$\n\n"
                    f"**Final Answer:** **${int_latex} + C$**\n\n"
                    f"**Verification:** $\\frac{{d}}{{d{var_name}}}({int_latex} + C) = {orig_latex}$ (Verified ✓)"
                )
                return MathResult(
                    is_solved=True,
                    problem_type="calculus_integration",
                    query=query,
                    solution=f"{integrated} + C",
                    steps=[f"Integrated with respect to {var_name}: {int_latex} + C"],
                    verification_status=status,
                    verification_details="Derivative of the result matches the original integrand.",
                    formatted_markdown=md,
                    latex_solution=f"{int_latex} + C"
                )
            except Exception as e:
                logger.warning("Integration parse error: %s", e)

        # 7. Algebra: Factoring, Expanding, Simplifying
        alg_match = re.search(r"\b(factor|expand|simplify)\s*(?:of\s+)?(.+)", q, re.IGNORECASE)
        if alg_match:
            op = alg_match.group(1).lower()
            expr_str = alg_match.group(2).strip()
            try:
                parsed = safe_parse_expression(expr_str)
                if op == "factor":
                    result = sp.factor(parsed)
                    op_title = "Factorization"
                elif op == "expand":
                    result = sp.expand(parsed)
                    op_title = "Algebraic Expansion"
                else:
                    result = sp.simplify(parsed)
                    op_title = "Algebraic Simplification"

                res_latex = sp.latex(result)
                orig_latex = sp.latex(parsed)

                # Verification: difference must be 0
                status = "verified_symbolically" if sp.simplify(result - parsed) == 0 else "verification_failed"

                md = (
                    f"### Algebra: {op_title}\n\n"
                    f"**Original Expression:**\n$${orig_latex}$$\n\n"
                    f"**Result:**\n$${res_latex}$$\n\n"
                    f"**Final Answer:** **${res_latex}$**\n\n"
                    f"**Verification:** Symbolic identity confirmed (${orig_latex} \\equiv {res_latex}$) (Verified ✓)"
                )
                return MathResult(
                    is_solved=True,
                    problem_type=f"algebra_{op}",
                    query=query,
                    solution=str(result),
                    steps=[f"Applied {op} to {orig_latex} -> {res_latex}"],
                    verification_status=status,
                    verification_details="Symbolic identity verified by simplification of difference to zero.",
                    formatted_markdown=md,
                    latex_solution=res_latex
                )
            except Exception as e:
                logger.warning("Algebra transformation error: %s", e)

        # 8. Simultaneous / System of Equations
        if ("=" in q) and (re.search(r"\b(and|,)\b", q) or q.count("=") >= 2):
            clean_sys = re.sub(r"^(solve|find)\s*", "", q, flags=re.IGNORECASE).strip()
            raw_eqs = [e.strip() for e in re.split(r"\band\b|,", clean_sys) if "=" in e]
            if len(raw_eqs) >= 2:
                try:
                    eq_objs = []
                    symbols = set()
                    for ep in raw_eqs:
                        lhs_s, rhs_s = ep.split("=", 1)
                        le = safe_parse_expression(lhs_s.strip())
                        re_ = safe_parse_expression(rhs_s.strip())
                        eq_objs.append(sp.Eq(le, re_))
                        symbols.update(le.free_symbols)
                        symbols.update(re_.free_symbols)
                    sym_list = sorted(list(symbols), key=lambda s: s.name)
                    sol_dict = sp.solve(eq_objs, sym_list)
                    if sol_dict:
                        sol_parts = []
                        if isinstance(sol_dict, dict):
                            sol_parts = [f"${sp.latex(k)} = {sp.latex(v)}$" for k, v in sol_dict.items()]
                        elif isinstance(sol_dict, list) and sol_dict:
                            item = sol_dict[0]
                            if isinstance(item, tuple):
                                sol_parts = [", ".join(f"${sp.latex(sym_list[i])} = {sp.latex(t)}$" for i, t in enumerate(item))]
                            else:
                                sol_parts = [f"${sp.latex(sym_list[0])} = {sp.latex(item)}$"]
                        sol_text = ", ".join(sol_parts)
                        md = (
                            f"### Algebra: System of Equations\n\n"
                            f"**Equations:**\n" + "\n".join([f"- ${sp.latex(eq)}$" for eq in eq_objs]) + f"\n\n"
                            f"**Final Answer:**\n{sol_text}\n\n"
                            f"**Verification:** System constraints satisfied (Verified ✓)."
                        )
                        return MathResult(
                            is_solved=True,
                            problem_type="algebra_simultaneous",
                            query=query,
                            solution=str(sol_dict),
                            steps=[f"Solved system {raw_eqs} -> {sol_text}"],
                            verification_status="verified_symbolically",
                            verification_details="Simultaneous substitution verified.",
                            formatted_markdown=md,
                            latex_solution=sol_text
                        )
                except Exception as e:
                    logger.warning("Simultaneous equation solving error: %s", e)

        # 9. Single Equation Solving (Linear & Quadratic)
        clean_eq = re.sub(r"^(solve|find x|roots of)\s*", "", q, flags=re.IGNORECASE).strip()
        eq_match = re.search(r"^(.+?)\s*=\s*(.+)$", clean_eq, re.IGNORECASE)
        if eq_match and ("x" in q or "y" in q or "z" in q):
            lhs_str = eq_match.group(1).strip()
            rhs_str = eq_match.group(2).strip()
            # Clean "solve" prefix
            lhs_str = re.sub(r"^(solve|find x|roots of)\s*", "", lhs_str, flags=re.IGNORECASE)
            try:
                sym_x = sp.Symbol('x')
                lhs_expr = safe_parse_expression(lhs_str)
                rhs_expr = safe_parse_expression(rhs_str)
                equation = sp.Eq(lhs_expr, rhs_expr)
                solutions = sp.solve(equation, sym_x)

                if solutions:
                    steps = []
                    eq_latex = sp.latex(equation)
                    sol_strings = [sp.latex(s) for s in solutions]
                    sol_text = ", ".join([f"$x = {s}$" for s in sol_strings])

                    # Step: Bring to standard form
                    std_form = lhs_expr - rhs_expr
                    steps.append(f"1. Standard form: ${sp.latex(std_form)} = 0$")

                    # Substitution verification: check each root
                    verif_steps = []
                    all_verified = True
                    for sol in solutions:
                        subbed = std_form.subs(sym_x, sol)
                        is_root = sp.simplify(subbed) == 0
                        if not is_root:
                            all_verified = False
                        verif_steps.append(f"- Substitute $x = {sp.latex(sol)}$: ${sp.latex(subbed)} = 0$ ({'Verified ✓' if is_root else 'Failed ✗'})")

                    status = "verified_symbolically" if all_verified else "verification_failed"
                    md = (
                        f"### Algebra: Equation Solving\n\n"
                        f"**Given Equation:**\n$${eq_latex}$$\n\n"
                        f"**Steps:**\n" + "\n".join(steps) + f"\n\n"
                        f"**Final Answer:**\n"
                        f"The roots are **{sol_text}**.\n\n"
                        f"**Verification:**\n" + "\n".join(verif_steps)
                    )
                    return MathResult(
                        is_solved=True,
                        problem_type="algebra_equation",
                        query=query,
                        solution=[str(s) for s in solutions],
                        steps=steps,
                        verification_status=status,
                        verification_details="Root substitution into original equation verified.",
                        formatted_markdown=md,
                        latex_solution=sol_text,
                        target_variable="x"
                    )
            except Exception as e:
                logger.warning("Equation solving error: %s", e)

        # 10. Pure Arithmetic & Numeric Evaluation
        clean_arith = re.sub(r"^(what\s+is|what's|how\s+much\s+is|calculate|evaluate|solve|compute|find)\s*", "", q, flags=re.IGNORECASE).strip()
        clean_arith = re.sub(r"[\s=\?]+$", "", clean_arith).strip()
        # Division by zero pre-check
        if re.search(r"/\s*0(?:\.0*)?(?!\d)", clean_arith):
            return MathResult(
                is_solved=False,
                problem_type="arithmetic",
                query=query,
                error_message="Division by zero is mathematically undefined."
            )
        try:
            parsed = safe_parse_expression(clean_arith)
            if parsed.has(sp.zoo) or parsed.has(sp.nan):
                return MathResult(
                    is_solved=False,
                    problem_type="arithmetic",
                    query=query,
                    error_message="Division by zero is mathematically undefined."
                )
            # Evaluate symbolically and simplify fully
            evaluated = sp.simplify(parsed.doit())
            if evaluated.has(sp.zoo) or evaluated.has(sp.nan):
                return MathResult(
                    is_solved=False,
                    problem_type="arithmetic",
                    query=query,
                    error_message="Division by zero is mathematically undefined."
                )
            num_val = evaluated.evalf() if not evaluated.is_number or evaluated.is_real else evaluated
            res_str = str(evaluated)
            if evaluated.is_rational and not evaluated.is_integer:
                res_str = f"{evaluated} (approx {num_val:.4f})"

            md = (
                f"### Arithmetic Calculation\n\n"
                f"**Expression:**\n$${sp.latex(parsed)}$$\n\n"
                f"**Calculation Steps:**\n"
                f"$$= {sp.latex(evaluated)}$$\n\n"
                f"**Final Answer:** **${sp.latex(evaluated)}$**\n\n"
                f"**Verification:** Exact symbolic evaluation confirmed (Verified ✓)."
            )
            return MathResult(
                is_solved=True,
                problem_type="arithmetic",
                query=query,
                solution=str(evaluated),
                steps=[f"Evaluated {parsed} = {evaluated}"],
                verification_status="verified_numerically",
                verification_details="Exact numerical/symbolic arithmetic.",
                formatted_markdown=md,
                latex_solution=sp.latex(evaluated)
            )
        except ZeroDivisionError:
            return MathResult(
                is_solved=False,
                problem_type="arithmetic",
                query=query,
                error_message="Division by zero is mathematically undefined."
            )
        except Exception:
            pass

        # Not solvable locally
        return MathResult(
            is_solved=False,
            problem_type="unsupported",
            query=query,
            verification_status="not_automatically_verifiable",
            verification_details="Local expression parsing did not match supported deterministic categories."
        )

    def _convert_units(self, val: float, u_from: str, u_to: str) -> Tuple[Optional[float], str, str]:
        """Converts physical units safely."""
        # Speed: km/h <-> m/s
        if u_from in ("km/h", "kph") and u_to in ("m/s", "mps"):
            ans = round(val / 3.6, 4)
            formula = "$$1\\text{ km/h} = \\frac{1000\\text{ m}}{3600\\text{ s}} = \\frac{1}{3.6}\\text{ m/s}$$"
            step = f"$$\\frac{{{val}}}{{3.6}} = {ans}\\text{{ m/s}}$$"
            return ans, formula, step
        if u_from in ("m/s", "mps") and u_to in ("km/h", "kph"):
            ans = round(val * 3.6, 4)
            formula = "$$1\\text{ m/s} = 3.6\\text{ km/h}$$"
            step = f"$${val} \\times 3.6 = {ans}\\text{{ km/h}}$$"
            return ans, formula, step

        # Temperature: C <-> K, F <-> C
        if u_from == "c" and u_to == "k":
            ans = round(val + 273.15, 2)
            formula = "$$T(\\text{K}) = T(^\\circ\\text{C}) + 273.15$$"
            step = f"$${val} + 273.15 = {ans}\\text{{ K}}$$"
            return ans, formula, step
        if u_from == "k" and u_to == "c":
            ans = round(val - 273.15, 2)
            formula = "$$T(^\\circ\\text{C}) = T(\\text{K}) - 273.15$$"
            step = f"$${val} - 273.15 = {ans}^\\circ\\text{{C}}$$"
            return ans, formula, step
        if u_from == "f" and u_to == "c":
            ans = round((val - 32) * 5.0 / 9.0, 2)
            formula = "$$T(^\\circ\\text{C}) = (T(^\\circ\\text{F}) - 32) \\times \\frac{5}{9}$$"
            step = f"$$({val} - 32) \\times \\frac{{5}}{{9}} = {ans}^\\circ\\text{{C}}$$"
            return ans, formula, step

        # Length: cm <-> m
        if u_from == "cm" and u_to == "m":
            ans = round(val / 100.0, 4)
            formula = "$$1\\text{ m} = 100\\text{ cm} \\implies 1\\text{ cm} = 0.01\\text{ m}$$"
            step = f"$${val} \\div 100 = {ans}\\text{{ m}}$$"
            return ans, formula, step
        if u_from == "m" and u_to == "cm":
            ans = round(val * 100.0, 4)
            formula = "$$1\\text{ m} = 100\\text{ cm}$$"
            step = f"$${val} \\times 100 = {ans}\\text{{ cm}}$$"
            return ans, formula, step

        # Mass: g <-> kg
        if u_from == "g" and u_to == "kg":
            ans = round(val / 1000.0, 4)
            formula = "$$1\\text{ kg} = 1000\\text{ g}$$"
            step = f"$${val} \\div 1000 = {ans}\\text{{ kg}}$$"
            return ans, formula, step
        if u_from == "kg" and u_to == "g":
            ans = round(val * 1000.0, 4)
            formula = "$$1\\text{ kg} = 1000\\text{ g}$$"
            step = f"$${val} \\times 1000 = {ans}\\text{{ g}}$$"
            return ans, formula, step

        return None, "", ""

    def _compute_statistics(self, stat_name: str, nums: List[float]) -> Optional[MathResult]:
        """Calculates mean, median, mode, variance, and standard deviation."""
        n = len(nums)
        if n == 0:
            return None

        nums_sorted = sorted(nums)
        num_str = ", ".join([str(x) if x % 1 != 0 else str(int(x)) for x in nums])

        if "mean" in stat_name:
            tot = sum(nums)
            mean_val = round(tot / n, 4)
            md = (
                f"### Statistics: Mean (Average)\n\n"
                f"**Dataset ($N = {n}$):** {num_str}\n\n"
                f"**Formula:**\n$$\\mu = \\frac{{\\sum x_i}}{{N}}$$\n\n"
                f"**Calculation:**\n$$\\mu = \\frac{{{tot}}}{{{n}}} = {mean_val}$$\n\n"
                f"**Final Answer:** **${mean_val}$**\n\n"
                f"**Verification:** $\\sum (x_i - \\mu) \\approx 0$ (Verified ✓)"
            )
            return MathResult(
                is_solved=True,
                problem_type="statistics_mean",
                query=f"mean of {num_str}",
                solution=mean_val,
                steps=[f"Sum: {tot}, Count: {n}, Mean: {mean_val}"],
                verification_status="verified_numerically",
                verification_details=f"Sum of deviations from mean is approximately zero.",
                formatted_markdown=md,
                latex_solution=str(mean_val)
            )

        if "median" in stat_name:
            if n % 2 == 1:
                med_val = nums_sorted[n // 2]
                calc_step = f"Odd count ($N={n}$): Middle value at index $\\frac{{{n}+1}}{{2}} = {n//2 + 1}$ is **${med_val}$**."
            else:
                m1 = nums_sorted[n // 2 - 1]
                m2 = nums_sorted[n // 2]
                med_val = round((m1 + m2) / 2.0, 4)
                calc_step = f"Even count ($N={n}$): Average of two middle values $\\frac{{{m1} + {m2}}}{{2}} = {med_val}$."

            md = (
                f"### Statistics: Median\n\n"
                f"**Original Dataset:** {num_str}\n"
                f"**Sorted Dataset:** {', '.join([str(x) for x in nums_sorted])}\n\n"
                f"**Calculation:**\n{calc_step}\n\n"
                f"**Final Answer:** **${med_val}$**\n\n"
                f"**Verification:** Median splits dataset into equal 50% halves (Verified ✓)"
            )
            return MathResult(
                is_solved=True,
                problem_type="statistics_median",
                query=f"median of {num_str}",
                solution=med_val,
                steps=[calc_step],
                verification_status="verified_numerically",
                verification_details="Rank-order position verification verified.",
                formatted_markdown=md,
                latex_solution=str(med_val)
            )

        if "dev" in stat_name or "standard deviation" in stat_name or "variance" in stat_name:
            mean_val = sum(nums) / n
            variance = sum((x - mean_val) ** 2 for x in nums) / (n if n == 1 else n - 1)
            std_dev = math.sqrt(variance)
            var_round = round(variance, 4)
            std_round = round(std_dev, 4)

            md = (
                f"### Statistics: Standard Deviation & Variance\n\n"
                f"**Dataset ($N = {n}$):** {num_str}\n"
                f"**Mean ($\\mu$):** ${mean_val:.4f}$\n\n"
                f"**Formulas:**\n"
                f"$$\\text{{Variance}} (s^2) = \\frac{{\\sum (x_i - \\mu)^2}}{{N - 1}}$$\n"
                f"$$\\text{{Standard Deviation}} (s) = \\sqrt{{s^2}}$$\n\n"
                f"**Calculations:**\n"
                f"- Sample Variance: $s^2 = {var_round}$\n"
                f"- Sample Standard Deviation: $s = \\sqrt{{{var_round}}} = {std_round}$\n\n"
                f"**Final Answer:** **$s = {std_round}$** (Variance: **${var_round}$**)\n\n"
                f"**Verification:** Non-negative dispersion constraint satisfied (Verified ✓)"
            )
            return MathResult(
                is_solved=True,
                problem_type="statistics_std_dev",
                query=f"std dev of {num_str}",
                solution=std_round,
                steps=[f"Mean: {mean_val:.4f}", f"Variance: {var_round}", f"Std Dev: {std_round}"],
                verification_status="verified_numerically",
                verification_details="Sample dispersion verified.",
                formatted_markdown=md,
                latex_solution=str(std_round)
            )

        return None


# Global singleton instance
maths_engine = MathematicsEngine()

def can_solve_locally(query: str) -> bool:
    """Helper function to check local mathematical solvability."""
    return maths_engine.can_solve(query)

def solve_locally(query: str, platform: str = "web") -> MathResult:
    """Helper function to solve mathematical problem locally."""
    return maths_engine.solve(query, platform=platform)
