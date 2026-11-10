import { promises as fs } from 'fs'
import path from 'path'
import { randomUUID } from 'crypto'
import type {
  BranchWithMessages,
  Conversation,
  ConversationPayload,
  Database,
} from './types'

const DATA_DIR = path.join(process.cwd(), '.data')
const DB_FILE = path.join(DATA_DIR, 'db.json')

const emptyDB = (): Database => ({
  conversations: [],
  messages: [],
  branches: [],
  branchMessages: [],
})

type StoreGlobal = {
  db?: Database
  writing?: Promise<void>
}

const root = globalThis as unknown as { __mathneuronStore?: StoreGlobal }
const store = (root.__mathneuronStore ??= {})

export function newId() {
  return randomUUID()
}

export function now() {
  return new Date().toISOString()
}

async function load(): Promise<Database> {
  if (store.db) return store.db
  try {
    const raw = await fs.readFile(DB_FILE, 'utf-8')
    const parsed = JSON.parse(raw) as Partial<Database>
    store.db = {
      conversations: parsed.conversations ?? [],
      messages: parsed.messages ?? [],
      branches: parsed.branches ?? [],
      branchMessages: parsed.branchMessages ?? [],
    }
  } catch {
    store.db = emptyDB()
  }
  return store.db
}

export async function getDB(): Promise<Database> {
  return load()
}

export async function reloadDB(): Promise<Database> {
  if (store.writing) await store.writing
  store.db = undefined
  return load()
}

export async function mutate<T>(fn: (db: Database) => T | Promise<T>): Promise<T> {
  const db = await load()
  const result = await fn(db)
  const previous = store.writing ?? Promise.resolve()
  store.writing = previous
    .then(async () => {
      await fs.mkdir(DATA_DIR, { recursive: true })
      await fs.writeFile(DB_FILE, JSON.stringify(db, null, 2), 'utf-8')
    })
    .catch((error) => {
      console.error('[store] write failed', error)
    })
  await store.writing
  return result
}

const byCreatedAt = (a: { createdAt: string }, b: { createdAt: string }) =>
  a.createdAt.localeCompare(b.createdAt)

export function payloadFor(db: Database, conversation: Conversation): ConversationPayload {
  const messages = db.messages
    .filter((message) => message.conversationId === conversation.id)
    .sort(byCreatedAt)
  const branches: BranchWithMessages[] = db.branches
    .filter((branch) => branch.conversationId === conversation.id)
    .sort(byCreatedAt)
    .map((branch) => ({
      ...branch,
      messages: db.branchMessages
        .filter((message) => message.branchId === branch.id)
        .sort(byCreatedAt),
    }))
  return { conversation, messages, branches }
}

export function latestConversation(db: Database): Conversation | undefined {
  return [...db.conversations].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))[0]
}

export function conversationMessages(db: Database, conversationId: string) {
  return db.messages
    .filter((message) => message.conversationId === conversationId)
    .sort(byCreatedAt)
}

export function branchMessages(db: Database, branchId: string) {
  return db.branchMessages
    .filter((message) => message.branchId === branchId)
    .sort(byCreatedAt)
}
