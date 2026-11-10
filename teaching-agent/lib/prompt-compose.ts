import type {
  PromptChapter,
  PromptPreview,
  PromptSegment,
  PromptSnapshot,
  PromptStage,
} from './prompt-types'

const SEP = '\n\n---\n\n'

type Part = {
  key: PromptSegment['key']
  label: string
  text: string
}

function clip(text: string, limit: number) {
  const value = text.trim()
  if (value.length <= limit) return value
  return `${value.slice(0, limit)}\n……（已截断）`
}

function assemble(parts: Part[], role: 'system' | 'user') {
  const filtered = parts.filter((part) => part.text.trim().length > 0)
  const segments: PromptSegment[] = []
  let cursor = 0

  filtered.forEach((part, index) => {
    if (index > 0) cursor += SEP.length
    const start = cursor
    const end = start + part.text.length
    segments.push({
      key: part.key,
      role,
      label: part.label,
      text: part.text,
      start,
      end,
    })
    cursor = end
  })

  return {
    text: filtered.map((part) => part.text).join(SEP),
    segments,
  }
}

export function buildDynamicContext(input: {
  chapter: PromptChapter
  stage: PromptStage
  stageIndex: number
  previousOutput?: string
  extraContext?: string
}) {
  const previous = input.previousOutput?.trim()
    ? clip(input.previousOutput, 8000)
    : '（暂无上一阶段产出）'
  const extra = input.extraContext?.trim()
    ? `\n\n【本次补充要求】\n${input.extraContext.trim()}`
    : ''

  return `【当前章节】
${input.chapter.title}

【本章骨架】
${input.chapter.skeleton}

【当前阶段】
第 ${input.stageIndex + 1} 阶段 / ${input.stage.name}

【上一阶段产出】
${previous}${extra}`
}

export function composeFirstPreview(
  snapshot: PromptSnapshot,
  dynamicContext: string,
  versionLabel?: string,
): PromptPreview {
  const system = assemble(
    [
      { key: 'G', label: 'G · 全局提示词', text: snapshot.globalPrompt },
      { key: 'S', label: 'S · System Instruction', text: snapshot.systemInstruction },
    ],
    'system',
  )
  const user = assemble(
    [
      { key: 'P', label: 'P · 阶段提示词', text: snapshot.stagePrompt },
      { key: 'D', label: 'D · 动态上下文', text: dynamicContext },
    ],
    'user',
  )

  return {
    systemText: system.text,
    userText: user.text,
    systemSegments: system.segments,
    userSegments: user.segments,
    versionLabel,
  }
}

export function composeFollowUpPreview(
  snapshot: PromptSnapshot,
  message: string,
  versionLabel?: string,
): PromptPreview {
  const system = assemble(
    [
      { key: 'G', label: 'G · 全局提示词', text: snapshot.globalPrompt },
      { key: 'S', label: 'S · System Instruction', text: snapshot.systemInstruction },
    ],
    'system',
  )
  const user = assemble(
    [{ key: 'U', label: 'U · 本次追问', text: message }],
    'user',
  )

  return {
    systemText: system.text,
    userText: user.text,
    systemSegments: system.segments,
    userSegments: user.segments,
    versionLabel,
  }
}
