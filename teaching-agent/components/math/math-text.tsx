import { Tex } from './tex'

export function MathText({ children }: { children: string }) {
  const parts = children.split(/\$([^$]+)\$/g)
  return (
    <>
      {parts.map((part, i) => (i % 2 === 1 ? <Tex key={i}>{part}</Tex> : <span key={i}>{part}</span>))}
    </>
  )
}
