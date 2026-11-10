export type NeuronStatus = 'critical' | 'warning' | 'solved'

export type Neuron = {
  id: string
  label: string
  pendingTag: string
  status: NeuronStatus
  originStatus: Exclude<NeuronStatus, 'solved'> | 'solved'
  chapter: string
  frequency: string
  recordedAt: string
  x: number
  y: number
  source: string
  question: string
  formula: string
  transcript: string
  purified: string
  level: string
  variant: { question: string; answer: string }
}

export const CHAPTERS = ['全部章节', '多元函数微分学', '多元极值与最值', '二重积分'] as const

export const STATUS_META: Record<NeuronStatus, { color: string; label: string }> = {
  critical: { color: 'oklch(0.67 0.1 12)', label: '致命认知断点' },
  warning: { color: 'oklch(0.79 0.1 75)', label: '综合变式陷阱' },
  solved: { color: 'oklch(0.75 0.08 165)', label: '已攻克' },
}

export const SOLVED_TAG = '已彻底攻克 · 稳定得分点'

export function neuronTag(n: Neuron) {
  return n.status === 'solved' ? SOLVED_TAG : n.pendingTag
}

const Q2004 = String.raw`设 $z=z(x,y)$ 是由 $x^2-6xy+10y^2-2yz-z^2+18=0$ 确定的函数，求 $z=z(x,y)$ 的极值点和极值。`

export const initialNeurons: Neuron[] = [
  {
    id: 'n-implicit',
    label: '隐函数: 自变量依赖遗忘',
    pendingTag: '高危卡点 · 错误率 68%',
    status: 'critical',
    originStatus: 'critical',
    chapter: '多元函数微分学',
    frequency: '近 10 年真题 7 次',
    recordedAt: '2026-10-12 21:08',
    x: -300,
    y: -150,
    source: '2004 年全国硕士研究生招生考试 · 数学一 · 第 18 题',
    question: Q2004,
    formula: String.raw`2x-6y-2y\,\frac{\partial z}{\partial x}-2z\,\frac{\partial z}{\partial x}=0`,
    transcript:
      '老师，我看到第三步拉格朗日方程时，直接把 z 当成普通独立常数对 x 偏导了，完全忘了原方程里 z 本身还依赖 x 和 y……然后 -2yz 那一项就只剩个 0，算到后面驻点怎么也对不上。',
    purified: String.raw`用户潜在假设：将三元隐函数方程 $F(x,y,z)=0$ 错误降维，割裂了因变量 $z$ 对自变量的链式导数依赖。`,
    level: '基础偏导计算扎实（前 25%），隐式依赖识别存在机械套公式定势。',
    variant: {
      question: String.raw`由 $x+z=e^{z}$ 确定 $z=z(x)$，口算 $\dfrac{dz}{dx}$。`,
      answer: String.raw`两边对 $x$ 求导：$1+z'=e^{z}z'$，故 $z'=\dfrac{1}{e^{z}-1}$。`,
    },
  },
  {
    id: 'n-hessian',
    label: '极值判定: 黑塞矩阵正定性混淆',
    pendingTag: '进阶盲区 · 概念未解耦',
    status: 'warning',
    originStatus: 'warning',
    chapter: '多元极值与最值',
    frequency: '近 10 年真题 5 次',
    recordedAt: '2026-10-09 19:42',
    x: 300,
    y: -170,
    source: '2004 年全国硕士研究生招生考试 · 数学一 · 第 18 题（第三步）',
    question: Q2004,
    formula: String.raw`AC-B^2=\frac{1}{(y+z)^2}>0,\quad A>0\Rightarrow\text{极小值}`,
    transcript: '我记得 AC 减 B 方大于零就是极值，但到底 A 大于零是极大还是极小，我每次都要猜一下，考场上就蒙了个极大。',
    purified: String.raw`用户把「$AC-B^2>0$ 判定存在性」与「$A$ 的符号判定类型」混为一步，未与二次型正定性建立对应。`,
    level: '公式记忆完整，但缺少「黑塞矩阵正定 ⇔ 极小」的几何锚点。',
    variant: {
      question: String.raw`$f=x^2+xy+y^2$ 在原点处，$A=2,B=1,C=2$，是极大还是极小？`,
      answer: String.raw`$AC-B^2=3>0$ 且 $A>0$，黑塞矩阵正定，故为极小值。`,
    },
  },
  {
    id: 'n-diff',
    label: '全微分: 可微与偏导存在混淆',
    pendingTag: '进阶盲区 · 定义链未打通',
    status: 'warning',
    originStatus: 'warning',
    chapter: '多元函数微分学',
    frequency: '近 10 年真题 6 次',
    recordedAt: '2026-10-05 22:15',
    x: -330,
    y: 175,
    source: '2012 年全国硕士研究生招生考试 · 数学一 · 第 2 题',
    question: String.raw`判断 $f(x,y)=\sqrt{|xy|}$ 在点 $(0,0)$ 处偏导数是否存在、是否可微。`,
    formula: String.raw`\lim_{\rho\to0}\frac{\Delta z-f_x\Delta x-f_y\Delta y}{\rho}=0`,
    transcript: '两个偏导数都算出来是 0，我就直接写了可微，后来才知道偏导存在推不出可微……',
    purified: String.raw`用户把「偏导存在」当作「可微」的充分条件，忽略了可微定义中的高阶无穷小余项检验。`,
    level: '计算准确，概念蕴含关系链需重建。',
    variant: {
      question: String.raw`偏导数连续 → 可微 → 偏导存在，哪一个箭头不可逆？`,
      answer: '两个箭头都不可逆：可微不推偏导连续，偏导存在也不推可微。',
    },
  },
  {
    id: 'n-lagrange',
    label: '拉格朗日: 辅助函数构造法',
    pendingTag: '进阶盲区 · 约束遗漏',
    status: 'solved',
    originStatus: 'warning',
    chapter: '多元极值与最值',
    frequency: '近 10 年真题 8 次',
    recordedAt: '2026-09-28 20:30',
    x: 310,
    y: 155,
    source: '2004 年全国硕士研究生招生考试 · 数学一 · 第 18 题',
    question: Q2004,
    formula: String.raw`L(x,y,z,\lambda)=z+\lambda\left(x^2-6xy+10y^2-2yz-z^2+18\right)`,
    transcript: '之前总是忘了对 λ 求偏导，导致约束条件没用上，现在已经形成固定四步了。',
    purified: '用户已建立「目标 + λ·约束 → 全变量偏导 → 联立约束」的完整构造流程。',
    level: '稳定得分点，可作为隐函数极值题的交叉校验工具。',
    variant: {
      question: String.raw`求 $xy$ 在 $x+y=2$ 下的最大值。`,
      answer: String.raw`$L=xy+\lambda(x+y-2)$，得 $x=y=1$，最大值为 $1$。`,
    },
  },
  {
    id: 'n-gradient',
    label: '方向导数: 梯度最速方向',
    pendingTag: '进阶盲区 · 几何直觉弱',
    status: 'solved',
    originStatus: 'warning',
    chapter: '多元函数微分学',
    frequency: '近 10 年真题 4 次',
    recordedAt: '2026-09-20 18:06',
    x: 10,
    y: -285,
    source: '2017 年全国硕士研究生招生考试 · 数学一 · 第 3 题',
    question: String.raw`求 $f=x^2y+z^2$ 在点 $(1,2,0)$ 处沿 $\boldsymbol{u}=(1,2,2)$ 的方向导数。`,
    formula: String.raw`\frac{\partial f}{\partial \boldsymbol{l}}=\nabla f\cdot \boldsymbol{e}_l`,
    transcript: '以前总忘记把方向向量单位化，现在先除模长已经成习惯了。',
    purified: '用户已掌握方向导数 = 梯度点乘单位方向向量的计算范式。',
    level: '稳定得分点。',
    variant: {
      question: String.raw`$\nabla f=(3,4)$，沿哪个方向方向导数最大？最大值是多少？`,
      answer: String.raw`沿梯度方向 $(3,4)/5$，最大值为 $|\nabla f|=5$。`,
    },
  },
  {
    id: 'n-polar',
    label: '二重积分: 极坐标换限',
    pendingTag: '进阶盲区 · 区域刻画',
    status: 'solved',
    originStatus: 'warning',
    chapter: '二重积分',
    frequency: '近 10 年真题 9 次',
    recordedAt: '2026-09-14 21:50',
    x: 40,
    y: 290,
    source: '2015 年全国硕士研究生招生考试 · 数学一 · 第 15 题',
    question: String.raw`计算 $\iint_D (x+y)\,d\sigma$，其中 $D:\ x^2+y^2\le 2x$。`,
    formula: String.raw`D:\ -\tfrac{\pi}{2}\le\theta\le\tfrac{\pi}{2},\ 0\le r\le 2\cos\theta`,
    transcript: '圆心不在原点的圆，我以前 r 的上限老写成常数，现在会先把边界方程代成极坐标。',
    purified: '用户已掌握「边界方程极坐标化 → 确定 θ 范围 → r 上限为函数」的换限流程。',
    level: '稳定得分点。',
    variant: {
      question: String.raw`$x^2+y^2\le 2y$ 在极坐标下 $r$ 的上限是？`,
      answer: String.raw`$r\le 2\sin\theta$，$0\le\theta\le\pi$。`,
    },
  },
]

export const diagnosedNeuron: Neuron = {
  id: 'n-constraint',
  label: '约束建模: 机械套公式定势',
  pendingTag: '高危卡点 · 刚刚入库',
  status: 'critical',
  originStatus: 'critical',
  chapter: '多元极值与最值',
  frequency: '近 10 年真题 6 次',
  recordedAt: '刚刚 · 语音诊断',
  x: -480,
  y: 5,
  source: '2004 年全国硕士研究生招生考试 · 数学一 · 第 18 题（第三步）',
  question: Q2004,
  formula: String.raw`L_x=2\lambda(x-3y)=0,\quad L_y=\lambda(-6x+20y-2z)=0`,
  transcript:
    '老师，我看到第三步拉格朗日方程时，直接把 z 当成普通独立常数对 x 偏导了，完全忘了原方程里 z 本身还依赖 x 和 y……算到后面怎么也对不上。',
  purified: String.raw`用户在高阶隐式多元约束建模中，先套用 $L_x=0$ 模板而非先厘清 $z=z(x,y)$ 的依赖结构。`,
  level: '基础导数与偏导计算扎实（前 25% 水平），高阶隐式约束建模存在机械式套公式的思维定势。',
  variant: {
    question: String.raw`$F(x,y,z)=0$ 确定 $z=z(x,y)$，口述 $z_x$ 的公式。`,
    answer: String.raw`$z_x=-\dfrac{F_x}{F_z}$（要求 $F_z\neq0$）。`,
  },
}
