import type { PromptPreview } from './prompt-types'

export type Role = 'user' | 'assistant'

export type Message = {
  id: string
  conversationId: string
  role: Role
  content: string
  reasoning?: string
  model?: string
  error?: boolean
  seconds?: number
  kind?: 'stage-prompt' | 'chat'
  promptVersionId?: string
  promptVersionLabel?: string
  promptPreview?: PromptPreview
  createdAt: string
}

export type BranchMessage = {
  id: string
  branchId: string
  role: Role
  content: string
  reasoning?: string
  error?: boolean
  seconds?: number
  createdAt: string
}

export type Conversation = {
  id: string
  title: string
  createdAt: string
  updatedAt: string
}

export type Branch = {
  id: string
  conversationId: string
  title: string
  prompt: string
  anchorText: string
  anchorLabel?: string
  createdAt: string
  updatedAt: string
}

export type Database = {
  conversations: Conversation[]
  messages: Message[]
  branches: Branch[]
  branchMessages: BranchMessage[]
}

export type BranchWithMessages = Branch & { messages: BranchMessage[] }

export type ConversationPayload = {
  conversation: Conversation
  messages: Message[]
  branches: BranchWithMessages[]
}
