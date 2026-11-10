import type { Metadata, Viewport } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
import 'katex/dist/katex.min.css'
// 预编译产物（scripts/build_css.mjs 生成）：绕开 Next 的 PostCSS 子进程，本机 Tailwind 单次编译约 6 分钟
import './prebuilt.css'

const geistSans = Geist({ subsets: ['latin'], variable: '--font-geist-sans' })
const geistMono = Geist_Mono({ subsets: ['latin'], variable: '--font-geist-mono' })

export const metadata: Metadata = {
  title: 'MathNeuron · 考研高数 AI 学习工作台',
  description: '基于 DeepSeek V4.1 Flash 的考研数学 AI 学习工作台，支持知识树、阶段式讲义生成、荧光画笔圈选与分支拆解。',
  icons: {
    icon: [
      {
        url: '/icon-light-32x32.png',
        media: '(prefers-color-scheme: light)',
      },
      {
        url: '/icon-dark-32x32.png',
        media: '(prefers-color-scheme: dark)',
      },
      {
        url: '/icon.svg',
        type: 'image/svg+xml',
      },
    ],
    apple: '/apple-icon.png',
  },
}

export const viewport: Viewport = {
  colorScheme: 'light dark',
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#f6f2e9' },
    { media: '(prefers-color-scheme: dark)', color: '#1b1a16' },
  ],
  width: 'device-width',
  initialScale: 1,
}

const themeScript = `(function(){try{var t=localStorage.getItem('mathneuron-theme');if(t==='dark'){document.documentElement.classList.add('dark')}}catch(e){}})()`

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="zh-CN"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable}`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="antialiased">{children}</body>
    </html>
  )
}
