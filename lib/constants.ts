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
]
