import katex from 'katex'
import { cn } from '@/lib/utils'

type TexProps = {
  children: string
  display?: boolean
  className?: string
}

export function Tex({ children, display = false, className }: TexProps) {
  const html = katex.renderToString(children, {
    displayMode: display,
    throwOnError: false,
    strict: false,
  })

  if (display) {
    return <div className={cn('text-foreground', className)} dangerouslySetInnerHTML={{ __html: html }} />
  }
  return <span className={className} dangerouslySetInnerHTML={{ __html: html }} />
}
