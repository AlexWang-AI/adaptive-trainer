export type KnowledgeNode = {
  id: string
  label: string
  raw: string
  kind: 'point' | 'note'
  depth: number
  children: KnowledgeNode[]
}

export type KnowledgeSection = {
  id: string
  title: string
  summary: string
  nodes: KnowledgeNode[]
  count: number
}

function displayLabel(value: string) {
  return value
    .replace(/\*\*/g, '')
    .replace(/`/g, '')
    .replace(/^[-*]\s+/, '')
    .trim()
}

function countNodes(nodes: KnowledgeNode[]): number {
  return nodes.reduce((total, node) => total + 1 + countNodes(node.children), 0)
}

export function buildKnowledgeSections(skeleton: string): KnowledgeSection[] {
  const sections: KnowledgeSection[] = []
  let current: KnowledgeSection | null = null
  const stack: KnowledgeNode[] = []

  const ensureSection = (id: string, title: string) => {
    if (current) return current
    current = { id, title, summary: '', nodes: [], count: 0 }
    sections.push(current)
    return current
  }

  skeleton.split(/\r?\n/).forEach((rawLine, lineIndex) => {
    const line = rawLine.trim()
    if (!line) return

    if (/^#\s+/.test(line)) return

    if (/^##\s+/.test(line)) {
      current = {
        id: `section-${lineIndex}`,
        title: line.replace(/^##\s+/, '').trim(),
        summary: '',
        nodes: [],
        count: 0,
      }
      sections.push(current)
      stack.length = 0
      return
    }

    const section = ensureSection(`section-${lineIndex}`, '知识结构')
    const numbered = line.match(/^(\s*)(\d+\.)\s+(.*)$/)
    const bullet = line.match(/^(\s*)[-*+]\s+(.*)$/)

    if (numbered || bullet) {
      const indent = (numbered?.[1] ?? bullet?.[1] ?? '').replace(/\t/g, '  ').length
      const depth = Math.min(4, Math.floor(indent / 2))
      const content = (numbered?.[3] ?? bullet?.[2] ?? '').trim()
      if (!content) return

      const node: KnowledgeNode = {
        id: `node-${lineIndex}`,
        label: numbered ? `${numbered[2]} ${displayLabel(content)}` : displayLabel(content),
        raw: content,
        kind: 'point',
        depth,
        children: [],
      }

      while (stack.length > 0 && stack[stack.length - 1].depth >= depth) {
        stack.pop()
      }
      const parent = stack[stack.length - 1]
      if (parent) {
        node.depth = parent.depth + 1
        parent.children.push(node)
      } else {
        node.depth = 0
        section.nodes.push(node)
      }
      stack.push(node)
      return
    }

    const text = displayLabel(line.replace(/^>\s+/, ''))
    if (!text) return
    section.summary = section.summary ? `${section.summary}\n${text}` : text
  })

  return sections
    .map((section) => ({ ...section, count: countNodes(section.nodes) }))
    .filter((section) => section.nodes.length > 0 || section.summary.trim().length > 0)
}

export function flattenKnowledgeNodes(nodes: KnowledgeNode[]): KnowledgeNode[] {
  return nodes.flatMap((node) => [node, ...flattenKnowledgeNodes(node.children)])
}
