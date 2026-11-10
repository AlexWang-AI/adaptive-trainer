export type QuizQuestion = {
  kind: 'choice' | 'fill'
  stem: string
  options: string[]
  answer: string
  explanation: string
  tested_points: string[]
  difficulty: 'easy' | 'medium' | 'hard'
  why_this_question?: string
  /** 教材题型名（来自《张宇基础30讲》题型层），没挂上时为空串 */
  type_name?: string
}

export type JudgeResult = {
  correct: boolean
  layer: string
  reason: string
  correct_answer: string
  explanation: string
  elapsed_ms: number
}

export type KpNode = {
  id: string
  name: string
  chapter: string
  block?: string
  block_name?: string
  tier?: string
  tier_label?: string
  exam_weight: number
  prerequisites: string[]
  examples?: number
  mastered: boolean
  mastered_at?: number | null
}

export type BlockNode = {
  id: string
  name: string
  role?: string
  tier?: string
  tier_label?: string
  conclusions?: number
  conclusion_list?: string[]
  kps: KpNode[]
}

export type ChapterNode = {
  id: string
  name: string
  lecture: number
  title?: string
  kps: KpNode[]
  blocks?: BlockNode[]
  mastered_count: number
}

export type KnowledgeTree = {
  student_id: string
  textbook?: string
  curriculum_version?: string
  chapters: ChapterNode[]
  progress: { total: number; mastered: number; ratio: number }
  next_kp: KpNode | null
}

export const DIFFICULTY_LABEL: Record<QuizQuestion['difficulty'], string> = {
  easy: '基础母题',
  medium: '技巧进阶',
  hard: '考研真题',
}

export const DIFFICULTY_TONE: Record<QuizQuestion['difficulty'], string> = {
  easy: 'from-sky-500/15 to-sky-500/5 text-sky-700 border-sky-500/35',
  medium: 'from-amber-500/15 to-amber-500/5 text-amber-700 border-amber-500/35',
  hard: 'from-rose-500/15 to-rose-500/5 text-rose-700 border-rose-500/35',
}
