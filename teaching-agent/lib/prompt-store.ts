import { promises as fs } from 'fs'
import path from 'path'
import {
  branchMessages,
  conversationMessages,
  getDB as getChatDB,
  mutate as mutateChatDB,
  newId,
  now,
} from './store'
import {
  CHAPTER_NINE_SKELETON,
  CHAPTER_NINE_TITLE,
  DEFAULT_STAGES,
  DEFAULT_SYSTEM_INSTRUCTION,
  GLOBAL_PROMPT,
} from './prompt-defaults'
import { buildDynamicContext, composeFirstPreview } from './prompt-compose'
import type { BranchWithMessages } from './types'
import type {
  PromptChapter,
  PromptDB,
  PromptRun,
  PromptSnapshot,
  PromptStage,
  PromptVersion,
  WorkbenchPayload,
} from './prompt-types'

const DATA_DIR = path.join(process.cwd(), '.data')
const PROMPT_FILE = path.join(DATA_DIR, 'prompts.json')

type PromptGlobal = { db?: PromptDB; writing?: Promise<void> }
const root = globalThis as unknown as { __mathneuronPromptStore?: PromptGlobal }
const store = (root.__mathneuronPromptStore ??= {})

function seed(): PromptDB {
  const timestamp = now()
  const workflow = {
    id: newId(),
    name: '考研数学一 · 提示词流水线',
    globalPrompt: GLOBAL_PROMPT,
    globalLocked: true,
    createdAt: timestamp,
    updatedAt: timestamp,
  }
  const chapters: PromptChapter[] = [
    {
      id: newId(),
      title: CHAPTER_NINE_TITLE,
      skeleton: CHAPTER_NINE_SKELETON,
      order: 0,
      createdAt: timestamp,
      updatedAt: timestamp,
    },
  ]
  const stages: PromptStage[] = DEFAULT_STAGES.map((stage, index) => ({
    id: newId(),
    name: stage.name,
    order: index,
    systemInstruction: stage.systemInstruction,
    stagePrompt: stage.stagePrompt,
    createdAt: timestamp,
    updatedAt: timestamp,
  }))
  return { workflow, chapters, stages, versions: [], runs: [] }
}

async function persist(db: PromptDB) {
  await fs.mkdir(DATA_DIR, { recursive: true })
  await fs.writeFile(PROMPT_FILE, JSON.stringify(db, null, 2), 'utf-8')
}

async function load(): Promise<PromptDB> {
  if (store.db) return store.db
  try {
    const raw = await fs.readFile(PROMPT_FILE, 'utf-8')
    const parsed = JSON.parse(raw) as PromptDB
    if (!parsed.workflow || !Array.isArray(parsed.stages) || parsed.stages.length === 0) {
      throw new Error('invalid prompt store')
    }
    store.db = parsed
  } catch {
    store.db = seed()
    await persist(store.db)
  }
  return store.db
}

export async function getPromptDB() {
  return load()
}

export async function mutatePromptDB<T>(fn: (db: PromptDB) => T | Promise<T>): Promise<T> {
  const db = await load()
  const result = await fn(db)
  const previous = store.writing ?? Promise.resolve()
  store.writing = previous
    .then(() => persist(db))
    .catch((error) => {
      console.error('[prompt-store] write failed', error)
    })
  await store.writing
  return result
}

export function sortedStages(db: PromptDB) {
  return [...db.stages].sort((a, b) => a.order - b.order)
}

export function sortedChapters(db: PromptDB) {
  return [...db.chapters].sort((a, b) => a.order - b.order)
}

function normalizeStageOrder(db: PromptDB) {
  sortedStages(db).forEach((stage, index) => {
    stage.order = index
  })
}

function normalizeChapterOrder(db: PromptDB) {
  sortedChapters(db).forEach((chapter, index) => {
    chapter.order = index
  })
}

export async function updateGlobal(input: {
  globalPrompt?: string
  globalLocked?: boolean
}) {
  return mutatePromptDB((db) => {
    if (typeof input.globalPrompt === 'string') db.workflow.globalPrompt = input.globalPrompt
    if (typeof input.globalLocked === 'boolean') db.workflow.globalLocked = input.globalLocked
    db.workflow.updatedAt = now()
    return db.workflow
  })
}

export async function createStage(name?: string) {
  return mutatePromptDB((db) => {
    const maxOrder = db.stages.reduce((max, stage) => Math.max(max, stage.order), -1)
    const timestamp = now()
    const stage: PromptStage = {
      id: newId(),
      name: name?.trim() || `新阶段 ${db.stages.length + 1}`,
      order: maxOrder + 1,
      systemInstruction: DEFAULT_SYSTEM_INSTRUCTION,
      stagePrompt: '请写下这一阶段的任务提示词。',
      createdAt: timestamp,
      updatedAt: timestamp,
    }
    db.stages.push(stage)
    return stage
  })
}

export async function updateStage(
  id: string,
  patch: { name?: string; systemInstruction?: string; stagePrompt?: string },
) {
  return mutatePromptDB((db) => {
    const stage = db.stages.find((item) => item.id === id)
    if (!stage) throw new Error('阶段不存在')
    if (typeof patch.name === 'string') stage.name = patch.name
    if (typeof patch.systemInstruction === 'string') {
      stage.systemInstruction = patch.systemInstruction
    }
    if (typeof patch.stagePrompt === 'string') stage.stagePrompt = patch.stagePrompt
    stage.updatedAt = now()
    return stage
  })
}

export async function deleteStage(id: string) {
  return mutatePromptDB((db) => {
    if (db.stages.length <= 1) throw new Error('至少保留一个阶段')
    db.stages = db.stages.filter((stage) => stage.id !== id)
    normalizeStageOrder(db)
  })
}

export async function moveStage(id: string, direction: 'up' | 'down') {
  return mutatePromptDB((db) => {
    const stages = sortedStages(db)
    const index = stages.findIndex((stage) => stage.id === id)
    if (index < 0) throw new Error('阶段不存在')
    const target = direction === 'up' ? index - 1 : index + 1
    if (target < 0 || target >= stages.length) return
    const current = stages[index]
    stages[index] = stages[target]
    stages[target] = current
    stages.forEach((stage, order) => {
      const original = db.stages.find((item) => item.id === stage.id)
      if (original) original.order = order
    })
  })
}

export async function createChapter(input: { title?: string; skeleton?: string }) {
  return mutatePromptDB((db) => {
    const maxOrder = db.chapters.reduce((max, chapter) => Math.max(max, chapter.order), -1)
    const timestamp = now()
    const chapter: PromptChapter = {
      id: newId(),
      title: input.title?.trim() || `新章节 ${db.chapters.length + 1}`,
      skeleton: input.skeleton?.trim() || '请粘贴或填写本章的知识骨架。',
      order: maxOrder + 1,
      createdAt: timestamp,
      updatedAt: timestamp,
    }
    db.chapters.push(chapter)
    return chapter
  })
}

export async function updateChapter(
  id: string,
  patch: { title?: string; skeleton?: string },
) {
  return mutatePromptDB((db) => {
    const chapter = db.chapters.find((item) => item.id === id)
    if (!chapter) throw new Error('章节不存在')
    if (typeof patch.title === 'string') chapter.title = patch.title
    if (typeof patch.skeleton === 'string') chapter.skeleton = patch.skeleton
    chapter.updatedAt = now()
    return chapter
  })
}

function snapshotFor(db: PromptDB, stage: PromptStage): PromptSnapshot {
  return {
    globalPrompt: db.workflow.globalPrompt,
    systemInstruction: stage.systemInstruction,
    stagePrompt: stage.stagePrompt,
  }
}

function findMatchingVersion(db: PromptDB, stageId: string, snapshot: PromptSnapshot) {
  return db.versions.find(
    (version) =>
      version.stageId === stageId &&
      version.snapshot.globalPrompt === snapshot.globalPrompt &&
      version.snapshot.systemInstruction === snapshot.systemInstruction &&
      version.snapshot.stagePrompt === snapshot.stagePrompt,
  )
}

export async function saveVersion(stageId: string, label?: string) {
  return mutatePromptDB((db) => {
    const stage = db.stages.find((item) => item.id === stageId)
    if (!stage) throw new Error('阶段不存在')
    const versions = db.versions.filter((version) => version.stageId === stageId)
    const nextNumber =
      versions.reduce((max, version) => Math.max(max, version.version), 0) + 1
    const version: PromptVersion = {
      id: newId(),
      workflowId: db.workflow.id,
      stageId,
      version: nextNumber,
      label: label?.trim() || `v${nextNumber}`,
      snapshot: snapshotFor(db, stage),
      createdAt: now(),
    }
    db.versions.push(version)
    return version
  })
}

function previousStageOutput(
  promptDb: PromptDB,
  chatDb: Awaited<ReturnType<typeof getChatDB>>,
  stage: PromptStage,
  chapterId: string,
) {
  const stages = sortedStages(promptDb)
  const index = stages.findIndex((item) => item.id === stage.id)
  const previousStage = stages[index - 1]
  if (!previousStage) return ''
  const previousRun = promptDb.runs
    .filter((run) => run.stageId === previousStage.id && run.chapterId === chapterId)
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt))[0]
  if (!previousRun) return ''
  const messages = conversationMessages(chatDb, previousRun.conversationId)
  return (
    [...messages].reverse().find((message) => message.role === 'assistant')?.content ?? ''
  )
}

export async function createRun(input: {
  stageId: string
  chapterId: string
  extraContext?: string
}) {
  const promptDb = await getPromptDB()
  const chatDb = await getChatDB()
  const stage = promptDb.stages.find((item) => item.id === input.stageId)
  const chapter = promptDb.chapters.find((item) => item.id === input.chapterId)
  if (!stage) throw new Error('阶段不存在')
  if (!chapter) throw new Error('章节不存在')

  const stages = sortedStages(promptDb)
  const stageIndex = stages.findIndex((item) => item.id === stage.id)
  const dynamicContext = buildDynamicContext({
    chapter,
    stage,
    stageIndex,
    previousOutput: previousStageOutput(promptDb, chatDb, stage, chapter.id),
    extraContext: input.extraContext,
  })
  const snapshot = snapshotFor(promptDb, stage)
  const matchedVersion = findMatchingVersion(promptDb, stage.id, snapshot)
  const preview = composeFirstPreview(snapshot, dynamicContext, matchedVersion?.label)

  const conversationId = newId()
  await mutateChatDB((data) => {
    data.conversations.push({
      id: conversationId,
      title: `${chapter.title} · ${stage.name}`,
      createdAt: now(),
      updatedAt: now(),
    })
  })

  const run: PromptRun = {
    id: newId(),
    workflowId: promptDb.workflow.id,
    stageId: stage.id,
    chapterId: chapter.id,
    conversationId,
    snapshot,
    versionId: matchedVersion?.id,
    versionLabel: matchedVersion?.label,
    promptPreview: preview,
    createdAt: now(),
    updatedAt: now(),
  }

  await mutatePromptDB((db) => {
    db.runs.push(run)
  })

  return { run, preview, conversationId, dynamicContext }
}

export async function getWorkbench(input: {
  stageId?: string
  chapterId?: string
  runId?: string
}): Promise<WorkbenchPayload> {
  const promptDb = await getPromptDB()
  const chatDb = await getChatDB()
  const stages = sortedStages(promptDb)
  const chapters = sortedChapters(promptDb)

  let activeRun: PromptRun | null = null
  if (input.runId) {
    activeRun = promptDb.runs.find((run) => run.id === input.runId) ?? null
  }

  let activeStage =
    stages.find((stage) => stage.id === (activeRun?.stageId ?? input.stageId)) ??
    stages[0]
  let activeChapter =
    chapters.find((chapter) => chapter.id === (activeRun?.chapterId ?? input.chapterId)) ??
    chapters[0]

  if (!activeRun) {
    activeRun =
      promptDb.runs
        .filter(
          (run) =>
            run.stageId === activeStage.id && run.chapterId === activeChapter.id,
        )
        .sort((a, b) => b.createdAt.localeCompare(a.createdAt))[0] ?? null
  }

  const runs = promptDb.runs
    .filter(
      (run) =>
        run.stageId === activeStage.id && run.chapterId === activeChapter.id,
    )
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
  const versions = promptDb.versions
    .filter((version) => version.stageId === activeStage.id)
    .sort((a, b) => b.version - a.version)

  const stageIndex = stages.findIndex((stage) => stage.id === activeStage.id)
  const dynamicContext = buildDynamicContext({
    chapter: activeChapter,
    stage: activeStage,
    stageIndex,
    previousOutput: previousStageOutput(promptDb, chatDb, activeStage, activeChapter.id),
  })

  const stageProgress = chapters.flatMap((chapter) =>
    stages.map((stage) => {
      const stageRuns = promptDb.runs.filter(
        (run) => run.chapterId === chapter.id && run.stageId === stage.id,
      )
      return {
        chapterId: chapter.id,
        stageId: stage.id,
        runCount: stageRuns.length,
        lastRunAt:
          stageRuns
            .map((run) => run.updatedAt || run.createdAt)
            .sort((a, b) => b.localeCompare(a))[0] ?? null,
      }
    }),
  )

  const messages = activeRun
    ? conversationMessages(chatDb, activeRun.conversationId)
    : []
  const branches: BranchWithMessages[] = activeRun
    ? chatDb.branches
        .filter((branch) => branch.conversationId === activeRun!.conversationId)
        .sort((a, b) => a.createdAt.localeCompare(b.createdAt))
        .map((branch) => ({
          ...branch,
          messages: branchMessages(chatDb, branch.id),
        }))
    : []

  return {
    workflow: promptDb.workflow,
    chapters,
    stages,
    activeStageId: activeStage.id,
    activeChapterId: activeChapter.id,
    activeRun,
    versions,
    runs,
    stageProgress,
    messages,
    branches,
    dynamicContext,
  }
}
