import { ModelDefinition, QuickPrompt } from '@/types/api'

export const CAPABILITY_MODELS: ModelDefinition[] = [
  {
    id: 'brainy-balanced',
    name: 'Brainy Balanced',
    tagline: 'All-round concept learning',
    description: 'Balanced speed and analytical depth for general study topics, doubts, and core concepts.',
    badge: 'Default',
    recommendedFor: 'General study & conceptual clarity',
  },
  {
    id: 'brainy-fast',
    name: 'Brainy Fast',
    tagline: 'Speedrun & flash review',
    description: 'Direct, distilled answers optimized for rapid memorization and quick formula checks.',
    badge: 'Fast',
    recommendedFor: 'Quick definitions & flashcard review',
  },
  {
    id: 'brainy-reasoning',
    name: 'Brainy Reasoning',
    tagline: 'Deep academic derivations',
    description: 'Step-by-step mathematical proofs, multi-stage logic, and rigorous scientific explanations.',
    badge: 'Deep',
    recommendedFor: 'Math, Physics & complex proofs',
  },
  {
    id: 'brainy-coding',
    name: 'Brainy Code',
    tagline: 'Programming & logic',
    description: 'Clean syntax, algorithmic decomposition, memory optimization, and line-by-line debugging.',
    badge: 'Technical',
    recommendedFor: 'Coding, data structures & debugging',
  },
  {
    id: 'brainy-exam',
    name: 'Brainy Exam Prep',
    tagline: 'Exam strategy & marking rubrics',
    description: 'Focuses on high-yield exam traps, marking rubrics, structured answers, and practice questions.',
    badge: 'Exam',
    recommendedFor: 'Revision & high-yield practice',
  },
]

export const ANSWER_LENGTH_OPTIONS = [
  { id: 'short', label: 'Short', desc: 'Direct, bulleted (<250 words)' },
  { id: 'medium', label: 'Medium', desc: 'Balanced explanation (~500 words)' },
  { id: 'long', label: 'In-Depth', desc: 'Comprehensive guide with examples (~1000 words)' },
] as const

export const STUDY_QUICK_PROMPTS: QuickPrompt[] = [
  {
    id: 'explain-concept',
    title: 'Explain a difficult concept',
    description: 'Build intuition with clean mental models and real-world analogies.',
    prompt: 'Explain the core intuition behind [concept] from first principles with a real-world analogy and key misconceptions.',
    category: 'concept',
  },
  {
    id: 'derive-formula',
    title: 'Solve or derive a formula',
    description: 'Step-by-step mathematical derivation with every step justified.',
    prompt: 'Derive the formula for [formula or problem] step-by-step, explaining the mathematical reasoning behind each transition.',
    category: 'problem',
  },
  {
    id: 'debug-code',
    title: 'Debug code & explain logic',
    description: 'Analyze time/space complexity and resolve subtle edge cases.',
    prompt: 'Analyze this code snippet, point out bugs or inefficiencies, and provide the optimal implementation with time & space complexity:',
    category: 'code',
  },
  {
    id: 'exam-quiz',
    title: 'High-yield exam drill',
    description: 'Generate 3 exam-style questions with detailed marking rubrics.',
    prompt: 'Create 3 high-yield exam practice questions on [topic] with step-by-step solutions and common traps students make.',
    category: 'exam',
  },
  {
    id: 'summarize-notes',
    title: 'Summarize chapter & key terms',
    description: 'Distill core principles, formulas, and definitions into high-yield bullets.',
    prompt: 'Summarize the core takeaways, formulas, and definitions for [chapter or topic] into a high-yield study sheet:',
    category: 'concept',
  },
  {
    id: 'study-roadmap',
    title: '7-day exam revision roadmap',
    description: 'Break difficult syllabus into prioritized, actionable milestones.',
    prompt: 'Generate an efficient 7-day study revision plan for [subject / topic] with daily study goals and active-recall checkpoints:',
    category: 'concept',
  },
]

export interface ThemeDefinition {
  id: 'warm-paper' | 'pure-light' | 'midnight' | 'graphite' | 'oled'
  name: string
  tagline: string
  mode: 'light' | 'dark'
  bgPreview: string
  cardPreview: string
  textPreview: string
  borderPreview: string
}

export const THEME_PRESETS: ThemeDefinition[] = [
  {
    id: 'warm-paper',
    name: 'Warm Paper',
    tagline: 'Cream base, warm borders & charcoal typography for relaxed reading',
    mode: 'light',
    bgPreview: '#FAF8F5',
    cardPreview: '#FFFFFF',
    textPreview: '#1C1917',
    borderPreview: '#E7E5E4',
  },
  {
    id: 'pure-light',
    name: 'Pure Light',
    tagline: 'Clean white background with neutral slate surfaces',
    mode: 'light',
    bgPreview: '#FFFFFF',
    cardPreview: '#F8FAFC',
    textPreview: '#0F172A',
    borderPreview: '#E2E8F0',
  },
  {
    id: 'midnight',
    name: 'Midnight',
    tagline: 'Deep navy charcoal background with soft white foreground',
    mode: 'dark',
    bgPreview: '#0B0F19',
    cardPreview: '#111827',
    textPreview: '#F9FAFB',
    borderPreview: '#1F2937',
  },
  {
    id: 'graphite',
    name: 'Graphite',
    tagline: 'Muted dark surfaces with low visual contrast between panels',
    mode: 'dark',
    bgPreview: '#18181B',
    cardPreview: '#27272A',
    textPreview: '#F4F4F5',
    borderPreview: '#3F3F46',
  },
  {
    id: 'oled',
    name: 'OLED Dark',
    tagline: 'True black background with high contrast readable elements',
    mode: 'dark',
    bgPreview: '#000000',
    cardPreview: '#0A0A0A',
    textPreview: '#FFFFFF',
    borderPreview: '#262626',
  },
]

export interface AccentColorPreset {
  id: string
  name: string
  hex: string
  hoverHex: string
  subtleBg: string
}

export const ACCENT_PRESETS: AccentColorPreset[] = [
  {
    id: 'emerald',
    name: 'Botanical Emerald',
    hex: '#059669',
    hoverHex: '#10b981',
    subtleBg: 'rgba(5, 150, 105, 0.12)',
  },
  {
    id: 'sapphire',
    name: 'Academic Sapphire',
    hex: '#2563eb',
    hoverHex: '#3b82f6',
    subtleBg: 'rgba(37, 99, 235, 0.12)',
  },
  {
    id: 'amber',
    name: 'Scholar Amber',
    hex: '#d97706',
    hoverHex: '#f59e0b',
    subtleBg: 'rgba(217, 119, 6, 0.12)',
  },
  {
    id: 'crimson',
    name: 'Focused Crimson',
    hex: '#e11d48',
    hoverHex: '#f43f5e',
    subtleBg: 'rgba(225, 29, 72, 0.12)',
  },
  {
    id: 'slate',
    name: 'Architect Slate',
    hex: '#475569',
    hoverHex: '#64748b',
    subtleBg: 'rgba(71, 85, 105, 0.12)',
  },
]

export interface FontDefinition {
  id: string
  name: string
  category: 'Modern Sans' | 'Crisp UI' | 'Editorial Serif' | 'Code & Math'
  fontFamily: string
  sample: string
}

export const FONT_OPTIONS: FontDefinition[] = [
  {
    id: 'inter',
    name: 'Inter',
    category: 'Modern Sans',
    fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    sample: 'Clean, objective legibility for long study sessions.',
  },
  {
    id: 'geist',
    name: 'Geist',
    category: 'Crisp UI',
    fontFamily: '"Geist", -apple-system, BlinkMacSystemFont, sans-serif',
    sample: 'Engineered for contemporary, precise technical interfaces.',
  },
  {
    id: 'jakarta',
    name: 'Plus Jakarta Sans',
    category: 'Modern Sans',
    fontFamily: '"Plus Jakarta Sans", sans-serif',
    sample: 'Warm geometric typography designed for natural reading flow.',
  },
  {
    id: 'dmsans',
    name: 'DM Sans',
    category: 'Modern Sans',
    fontFamily: '"DM Sans", sans-serif',
    sample: 'Approachable, rounded letterforms that ease cognitive load.',
  },
  {
    id: 'manrope',
    name: 'Manrope',
    category: 'Modern Sans',
    fontFamily: '"Manrope", sans-serif',
    sample: 'Modern semi-condensed grotesque with balanced proportions.',
  },
  {
    id: 'ibm',
    name: 'IBM Plex Sans',
    category: 'Crisp UI',
    fontFamily: '"IBM Plex Sans", sans-serif',
    sample: 'Structured, neutral, and engineered for technical clarity.',
  },
  {
    id: 'lora',
    name: 'Lora',
    category: 'Editorial Serif',
    fontFamily: '"Lora", Georgia, serif',
    sample: 'Contemporary serif with balanced curves suited for essay reading.',
  },
  {
    id: 'sourceserif',
    name: 'Source Serif 4',
    category: 'Editorial Serif',
    fontFamily: '"Source Serif 4", Georgia, serif',
    sample: 'Scholarly book typeface crafted for academic deep work.',
  },
  {
    id: 'optizither',
    name: 'OPTIZither',
    category: 'Editorial Serif',
    fontFamily: '"OPTIZither", "Source Serif 4", Georgia, serif',
    sample: 'Distinctive literary display typeface with timeless editorial character.',
  },
  {
    id: 'jetbrains',
    name: 'JetBrains Mono',
    category: 'Code & Math',
    fontFamily: '"JetBrains Mono", Consolas, monospace',
    sample: 'x = (-b ± √(b² - 4ac)) / (2a) // High-precision monospace',
  },
]

export const DEFAULT_PREFERENCES = {
  theme: 'warm-paper' as const,
  accentColor: 'emerald' as const,
  interfaceFont: 'inter' as const,
  fontSize: 'md' as const,
  lineSpacing: 'comfortable' as const,
  chatWidth: 'standard' as const,
  density: 'comfortable' as const,
  readabilityMode: false,
  defaultModel: 'brainy-balanced',
  defaultLength: 'medium' as const,
  focusTimerMinutes: 25,
}
