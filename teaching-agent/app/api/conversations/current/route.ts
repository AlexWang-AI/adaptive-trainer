import {
  getDB,
  latestConversation,
  mutate,
  newId,
  now,
  payloadFor,
} from '@/lib/store'

export const runtime = 'nodejs'

export async function GET() {
  const db = await getDB()
  let conversation = latestConversation(db)
  if (!conversation) {
    const created = {
      id: newId(),
      title: '新对话',
      createdAt: now(),
      updatedAt: now(),
    }
    await mutate((data) => {
      data.conversations.push(created)
    })
    conversation = created
  }
  return Response.json(payloadFor(db, conversation))
}
