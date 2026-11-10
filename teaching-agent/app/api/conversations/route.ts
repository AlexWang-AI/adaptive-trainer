import { getDB, mutate, newId, now, payloadFor } from '@/lib/store'
import type { Conversation } from '@/lib/types'

export const runtime = 'nodejs'

export async function POST() {
  const db = await getDB()
  const conversation: Conversation = {
    id: newId(),
    title: '新对话',
    createdAt: now(),
    updatedAt: now(),
  }
  await mutate((data) => {
    data.conversations.push(conversation)
  })
  return Response.json(payloadFor(db, conversation))
}
