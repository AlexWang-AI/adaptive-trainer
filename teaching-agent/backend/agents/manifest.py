"""Agent 注册表：给 UI、给评测、给组员对齐用。

新增 agent 时在这里加一条，字段含义见 contracts.AgentSpec。
"""

from __future__ import annotations

from contracts import AgentManifest, AgentSpec

MANIFEST = AgentManifest(
    agents=[
        AgentSpec(
            id="planner",
            name="路线规划",
            role="总指挥 / 锚点：把目标拆成可执行、可验收、可量化的单元序列",
            owner="队长",
            version="1.0.0",
            input_model="agents.planner.schema.PlannerRequest",
            output_model="agents.planner.schema.StudyPlan",
            memory="long_term",
            deterministic=False,
            notes="线上入口 run_auto()=V3R；6/6 通过，1 次调用，约 4.2k tokens",
        ),
        AgentSpec(
            id="teach",
            name="主讲",
            role="在当前单元内讲明白，不越界、不跳章",
            owner="待认领",
            version="0.9.0",
            input_model="schema.TeachingRequest",
            output_model="schema.TeachingTurn",
            memory="session",
            notes="现为 variant B（四版对照胜出）；只读近 3 轮 + 画像摘要",
        ),
        AgentSpec(
            id="quiz",
            name="出题",
            role="基于本轮教学正文出一道题或一道同构变式",
            owner="待认领",
            version="0.9.0",
            input_model="agents.quiz.schema.QuizRequest",
            output_model="agents.quiz.schema.QuizOut",
            memory="none",
            notes="history=[]，纯函数；待升级为「原题 / 变式」双模式",
        ),
        AgentSpec(
            id="sideqa",
            name="负分支提问",
            role="主干对话中的小疑问，开副分支讲透并自动归档错题本",
            owner="待认领",
            version="0.0.0",
            input_model="agents.sideqa.schema.SideQuestion",
            output_model="agents.sideqa.schema.SideAnswer",
            memory="none",
            notes="未开工；要求与主干上下文完全隔离",
        ),
        AgentSpec(
            id="exam",
            name="综合题",
            role="单元收尾时出跨知识点综合卷，对标考研难度，给踩分点",
            owner="待认领",
            version="0.0.0",
            input_model="agents.exam.schema.ExamRequest",
            output_model="agents.exam.schema.ExamPaper",
            memory="none",
            notes="未开工；依赖教材题目库",
        ),
        AgentSpec(
            id="judge",
            name="判分",
            role="客观题比对 + 数学等价判断 + 归因写错题本",
            owner="待认领",
            version="0.9.0",
            input_model="agents.judge.schema.JudgeRequest",
            output_model="contracts.MistakeEntry",
            memory="none",
            deterministic=True,
            notes="不调 LLM 出文本；待上 sympy 做等价判断",
        ),
    ]
)


def get_agent(agent_id: str) -> AgentSpec | None:
    return next((a for a in MANIFEST.agents if a.id == agent_id), None)


if __name__ == "__main__":
    for agent in MANIFEST.agents:
        print(f"{agent.id:10s} v{agent.version:6s} {agent.name:8s} memory={agent.memory:10s} {agent.notes}")
