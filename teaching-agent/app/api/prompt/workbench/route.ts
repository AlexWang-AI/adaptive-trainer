import {
  createChapter,
  createRun,
  createStage,
  deleteStage,
  getWorkbench,
  moveStage,
  saveVersion,
  updateChapter,
  updateGlobal,
  updateStage,
} from '@/lib/prompt-store'

export const runtime = 'nodejs'
export const maxDuration = 300

export async function GET(request: Request) {
  const url = new URL(request.url)
  try {
    const payload = await getWorkbench({
      stageId: url.searchParams.get('stageId') || undefined,
      chapterId: url.searchParams.get('chapterId') || undefined,
      runId: url.searchParams.get('runId') || undefined,
    })
    return Response.json(payload)
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return Response.json({ error: message }, { status: 500 })
  }
}

type Body = {
  action?: string
  stageId?: string
  chapterId?: string
  runId?: string
  id?: string
  name?: string
  globalPrompt?: string
  globalLocked?: boolean
  systemInstruction?: string
  stagePrompt?: string
  title?: string
  skeleton?: string
  direction?: 'up' | 'down'
  label?: string
  extraContext?: string
}

export async function POST(request: Request) {
  let body: Body
  try {
    body = await request.json()
  } catch {
    return Response.json({ error: '无效请求体' }, { status: 400 })
  }

  if (!body.action) return Response.json({ error: '缺少 action' }, { status: 400 })

  try {
    let stageId = body.stageId
    let chapterId = body.chapterId
    let createdStageId: string | undefined
    let createdChapterId: string | undefined

    switch (body.action) {
      case 'updateGlobal':
        await updateGlobal({
          globalPrompt: body.globalPrompt,
          globalLocked: body.globalLocked,
        })
        break

      case 'createStage': {
        const stage = await createStage(body.name)
        stageId = stage.id
        createdStageId = stage.id
        break
      }

      case 'updateStage': {
        if (!body.id) throw new Error('缺少阶段 ID')
        await updateStage(body.id, {
          name: body.name,
          systemInstruction: body.systemInstruction,
          stagePrompt: body.stagePrompt,
        })
        break
      }

      case 'deleteStage': {
        if (!body.id) throw new Error('缺少阶段 ID')
        await deleteStage(body.id)
        stageId = undefined
        break
      }

      case 'moveStage': {
        if (!body.id) throw new Error('缺少阶段 ID')
        await moveStage(body.id, body.direction ?? 'down')
        break
      }

      case 'createChapter': {
        const chapter = await createChapter({
          title: body.title,
          skeleton: body.skeleton,
        })
        chapterId = chapter.id
        createdChapterId = chapter.id
        break
      }

      case 'updateChapter': {
        if (!body.id) throw new Error('缺少章节 ID')
        await updateChapter(body.id, {
          title: body.title,
          skeleton: body.skeleton,
        })
        break
      }

      case 'saveVersion': {
        if (!body.stageId) throw new Error('缺少阶段 ID')
        const version = await saveVersion(body.stageId, body.label)
        const payload = await getWorkbench({
          stageId: body.stageId,
          chapterId: body.chapterId,
          runId: body.runId,
        })
        return Response.json({ ...payload, createdVersionId: version.id })
      }

      case 'createRun': {
        if (!body.stageId || !body.chapterId) {
          throw new Error('缺少阶段或章节 ID')
        }
        const result = await createRun({
          stageId: body.stageId,
          chapterId: body.chapterId,
          extraContext: body.extraContext,
        })
        return Response.json(result)
      }

      default:
        throw new Error(`未知 action：${body.action}`)
    }

    const payload = await getWorkbench({
      stageId,
      chapterId,
      runId: body.runId,
    })
    return Response.json({ ...payload, createdStageId, createdChapterId })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return Response.json({ error: message }, { status: 400 })
  }
}
