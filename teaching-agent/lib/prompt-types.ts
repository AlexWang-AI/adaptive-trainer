import type { BranchWithMessages, Message } from './types'

export type PromptChapter = {
  id: string
  title: string
  skeleton: string
  order: number
  createdAt: string
  updatedAt: string
}

export type PromptStage = {
  id: string
  name: string
  order: number
  systemInstruction: string
  stagePrompt: string
  createdAt: string
  updatedAt: string
}

export type PromptWorkflow = {
  id: string
  name: string
  globalPrompt: string
  globalLocked: boolean
  createdAt: string
  updatedAt: string
}

export type PromptSnapshot = {
  globalPrompt: string
  systemInstruction: string
  stagePrompt: string
}

export type PromptSegmentKey = 'G' | 'S' | 'P' | 'D' | 'U'

export type PromptSegment = {
  key: PromptSegmentKey
  role: 'system' | 'user'
  label: string
  text: string
  start: number
  end: number
}

export type PromptPreview = {
  systemText: string
  userText: string
  systemSegments: PromptSegment[]
  userSegments: PromptSegment[]
  versionLabel?: string
}

export type PromptVersion = {
  id: string
  workflowId: string
  stageId: string
  version: number
  label: string
  snapshot: PromptSnapshot
  createdAt: string
}

export type PromptRun = {
  id: string
  workflowId: string
  stageId: string
  chapterId: string
  conversationId: string
  snapshot: PromptSnapshot
  versionId?: string
  versionLabel?: string
  promptPreview: PromptPreview
  createdAt: string
  updatedAt: string
}

export type PromptDB = {
  workflow: PromptWorkflow
  chapters: PromptChapter[]
  stages: PromptStage[]
  versions: PromptVersion[]
  runs: PromptRun[]
}

export type StageProgress = {
  chapterId: string
  stageId: string
  runCount: number
  lastRunAt: string | null
}

export type WorkbenchPayload = {
  workflow: PromptWorkflow
  chapters: PromptChapter[]
  stages: PromptStage[]
  activeStageId: string
  activeChapterId: string
  activeRun: PromptRun | null
  versions: PromptVersion[]
  runs: PromptRun[]
  stageProgress: StageProgress[]
  messages: Message[]
  branches: BranchWithMessages[]
  dynamicContext: string
}
