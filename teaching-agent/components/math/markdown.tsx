'use client'

import { memo, startTransition, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import { cn } from '@/lib/utils'

function normalizeMath(text: string) {
  return text
    .replace(/\\\[([\s\S]*?)\\\]/g, (_, body: string) => `$$${body}$$`)
    .replace(/\\\(([\s\S]*?)\\\)/g, (_, body: string) => `$${body}$`)
}

const components = {
  h1: ({ children }: { children?: React.ReactNode }) => (
    <h1 className="mt-8 mb-4 font-serif text-[23px] leading-tight font-semibold tracking-tight text-foreground">
      {children}
    </h1>
  ),
  h2: ({ children }: { children?: React.ReactNode }) => (
    <h2 className="mt-8 mb-3 font-serif text-[19px] leading-snug font-semibold tracking-tight text-foreground">
      {children}
    </h2>
  ),
  h3: ({ children }: { children?: React.ReactNode }) => (
    <h3 className="mt-6 mb-2 font-serif text-[16.5px] leading-snug font-semibold text-foreground">
      {children}
    </h3>
  ),
  h4: ({ children }: { children?: React.ReactNode }) => (
    <h4 className="mt-5 mb-1.5 text-[14.5px] font-semibold text-foreground">{children}</h4>
  ),
  p: ({ children }: { children?: React.ReactNode }) => (
    <p className="my-2.5 leading-[1.9]">{children}</p>
  ),
  ul: ({ children }: { children?: React.ReactNode }) => (
    <ul className="my-3 list-disc space-y-1.5 pl-5 marker:text-primary/55">{children}</ul>
  ),
  ol: ({ children }: { children?: React.ReactNode }) => (
    <ol className="my-3 list-decimal space-y-1.5 pl-5 marker:font-mono marker:text-[0.85em] marker:text-muted-foreground">
      {children}
    </ol>
  ),
  li: ({ children }: { children?: React.ReactNode }) => (
    <li className="pl-0.5 leading-[1.9]">{children}</li>
  ),
  strong: ({ children }: { children?: React.ReactNode }) => (
    <strong className="font-semibold text-foreground">{children}</strong>
  ),
  em: ({ children }: { children?: React.ReactNode }) => (
    <em className="italic text-foreground/90">{children}</em>
  ),
  blockquote: ({ children }: { children?: React.ReactNode }) => (
    <blockquote className="my-4 rounded-r-xl border-l-2 border-primary/45 bg-muted/30 py-1 pr-3 pl-4 text-foreground/75">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-7 border-border/70" />,
  a: ({ href, children }: { href?: string; children?: React.ReactNode }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="font-medium text-primary underline decoration-primary/30 underline-offset-3 transition-colors hover:decoration-primary"
    >
      {children}
    </a>
  ),
  code: ({ className, children }: { className?: string; children?: React.ReactNode }) =>
    className ? (
      <code className={cn('font-mono text-[0.9em]', className)}>{children}</code>
    ) : (
      <code className="rounded-md border border-border/45 bg-muted/55 px-1.5 py-0.5 font-mono text-[0.85em] text-foreground">
        {children}
      </code>
    ),
  pre: ({ children }: { children?: React.ReactNode }) => (
    <pre className="my-4 overflow-x-auto rounded-xl border border-border/55 bg-muted/40 p-3.5 text-[12px] leading-[1.85]">
      {children}
    </pre>
  ),
  table: ({ children }: { children?: React.ReactNode }) => (
    <div className="my-4 w-full overflow-x-auto rounded-xl border border-border/55">
      <table className="w-full border-collapse text-[12.5px]">{children}</table>
    </div>
  ),
  thead: ({ children }: { children?: React.ReactNode }) => (
    <thead className="bg-muted/55">{children}</thead>
  ),
  th: ({ children }: { children?: React.ReactNode }) => (
    <th className="border-b border-border/55 px-3 py-2 text-left font-semibold">{children}</th>
  ),
  td: ({ children }: { children?: React.ReactNode }) => (
    <td className="border-b border-border/45 px-3 py-2 align-top">{children}</td>
  ),
  img: ({ src, alt }: React.ComponentProps<'img'>) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={typeof src === 'string' ? src : undefined}
      alt={alt ?? ''}
      className="my-4 max-w-full rounded-xl border border-border/55"
    />
  ),
}

function MarkdownMessageInner({
  content,
  className,
}: {
  content: string
  className?: string
}) {
  return (
    <div
      className={cn(
        'markdown-body text-[14.5px] leading-[1.9] text-foreground/90 text-pretty',
        '[&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&_li>p]:my-0',
        className,
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }]]}
        components={components}
      >
        {normalizeMath(content)}
      </ReactMarkdown>
    </div>
  )
}

/**
 * content 不变就不重新解析。
 * 流式时父组件每帧都会渲染，但只有真正变化的那一条需要 rehype-katex 重新跑一遍。
 */
export const MarkdownMessage = memo(
  MarkdownMessageInner,
  (prev, next) => prev.content === next.content && prev.className === next.className,
)


/**
 * 流式渲染：Markdown/KaTeX 每 ~140ms 才重算一次，中间的增量先用纯文本尾巴顶上。
 *
 * 为什么必须这么拆：rehype-katex 对 1~2KB 带公式的文本一次要 10~30ms，
 * 每帧都跑就会把主线程打满（用户体感的「卡、不丝滑」）。
 * 拆开之后，文字每帧都在长（观感连续），解析只按节奏跑。
 */
export function StreamingMarkdown({ content }: { content: string }) {
  return <StreamingMarkdownInner content={content} />
}

function StreamingMarkdownInner({ content }: { content: string }) {
  const [parsed, setParsed] = useState('')
  const lastAt = useRef(0)
  const timer = useRef<number | null>(null)

  useEffect(() => {
    const now = performance.now()
    const lag = content.length - parsed.length
    const flush = () => {
      lastAt.current = performance.now()
      // startTransition：解析是低优先级更新，不能挡住滚动/输入（用户体感「跟手」的关键）
      startTransition(() => setParsed(content))
      if (typeof window !== 'undefined') {
        const w = window as unknown as { __MN_MD_PARSE__?: number }
        w.__MN_MD_PARSE__ = (w.__MN_MD_PARSE__ ?? 0) + 1
      }
    }
    if (!parsed || lag > 320) {
      flush()
      return
    }
    if (timer.current === null) {
      timer.current = window.setTimeout(() => {
        timer.current = null
        flush()
      }, 190)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [content])

  useEffect(
    () => () => {
      if (timer.current !== null) window.clearTimeout(timer.current)
    },
    [],
  )

  // 关键：按「最后一个空行」切成 前缀 + 当前段落。
  // 前缀只在段落完成时变化（memo 命中，不重新解析）；每 160ms 只重解析最后一段。
  const boundary = parsed.lastIndexOf('\n\n')
  const stable = boundary > 0 ? parsed.slice(0, boundary + 2) : ''
  const active = boundary > 0 ? parsed.slice(boundary + 2) : parsed
  const live = content.startsWith(parsed) ? content.slice(parsed.length) : ''

  return (
    <div className="markdown-body text-[14.5px] leading-[1.9] text-foreground/90 text-pretty [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&_li>p]:my-0">
      {stable && <MarkdownMessage content={stable} />}
      {active && <MarkdownMessage content={active} />}
      {live && (
        <span className="whitespace-pre-wrap text-foreground/70">
          {live.replace(/\*\*/g, '').replace(/`/g, '')}
        </span>
      )}
    </div>
  )
}
