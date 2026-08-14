"""金标问答数据集 —— 切片策略对比实验的评判基准。

C# 对照主线：
  本模块 ≈ C# 里的静态数据常量（类似 resources / static class）：
    public static class GoldenQA { public static readonly IReadOnlyList<GoldenQA> All = [...]; }

设计原则：
  1. question 是对源文档内容做语义改写的问题 —— 验证「语义检索」而非关键词匹配
  2. answer 是源文档里**逐字存在的子串** —— 命中判定的基准：
     检索 top-3 的切片里只要有一个包含该子串（空白归一化后）就算命中
  3. 这样保证「问题一定可回答」：fixture 往返不丢字（make_samples 验证）
     → 切片恰好完整包含子串 → 检索把该切片送进 top-3，三环缺一才失败

短语均已 grep 验证逐字存在于源文档（2026-08-14）。
"""

from dataclasses import dataclass  # C#: record


@dataclass
class GoldenQA:
    """一道金标问答。C#: public record GoldenQA(string Question, string Answer, string Source);"""

    question: str  # 面试题（语义改写，不与答案字面重合过多）
    answer: str  # 答案短语：源文档里的逐字子串（命中判定的基准）
    source: str  # 来源文档文件名（"game_interview_guide.md" 或 "game_interview_100_questions.md"）


# fmt: off
GOLDEN_QA: list[GoldenQA] = [
    # Q01 引导语：仿真 vs 游戏 —— guide 中部，11 字含顿号
    GoldenQA("仿真开发和游戏开发的本质区别是什么？",
             "玩起来爽不爽、愿不愿意继续玩", "game_interview_guide.md"),
    # Q02 招聘观 —— guide 开头，9 字含逗号
    GoldenQA("海外休闲游戏公司招人时最看重什么？",
             "游戏是产品，不只是程序", "game_interview_guide.md"),
    # Q03 核心循环 —— 专门测 U+2192 箭头能否穿过 PDF/Word 往返 + 检索
    GoldenQA("休闲游戏的核心循环长什么样？",
             "获得反馈 → 获得奖励 → 继续下一轮", "game_interview_guide.md"),
    # Q04 激励视频广告场景 —— 100 题，11 字
    GoldenQA("激励视频广告应该放在哪些场景？",
             "自愿、收益明确、时机合理", "game_interview_100_questions.md"),
    # Q05 新手引导 —— 21 字长答案含逗号：测 recursive 逗号级切分是否拆碎长答案
    GoldenQA("新手引导的核心目标是什么？",
             "帮助玩家尽快完成第一次有效操作，并获得正反馈", "game_interview_100_questions.md"),
    # Q06 Addressables —— 6 字最短短语：测切片边界敏感性（独立成行，PDF 单行渲染安全）
    GoldenQA("Addressables 在资源更新上有什么优势？",
             "远程资源更新", "game_interview_100_questions.md"),
    # Q07 插屏广告 —— 12 字含逗号
    GoldenQA("插屏广告为什么容易伤害体验？",
             "强打断，容易破坏情绪节奏", "game_interview_100_questions.md"),
    # Q08 幂等 —— 15 字双顿号
    GoldenQA("为什么奖励发放必须做幂等？",
             "广告回调、网络重试、页面重复点击", "game_interview_100_questions.md"),
    # Q09 D1 留存 —— 10 字短短语
    GoldenQA("D1 留存低应该先排查什么？",
             "首个爽点来得是否太慢", "game_interview_100_questions.md"),
    # Q10 协程 —— 19 字中英混排：测混合语言文本
    GoldenQA("协程的本质是什么？",
             "Unity 在主线程上调度的迭代器流程控制", "game_interview_100_questions.md"),
]
# fmt: on

# 备用短语：若某短语在 PDF 往返中受损（提取断行/丢字），替换使用并记录原因
BACKUP_ANSWERS: list[str] = [
    "按固定时间步调用，适合物理运算",  # Q100:13（Update 方法）
    "一个像素被重复绘制多次",  # Q100:183（Overdraw）
    "成熟的工程落地能力",  # Q100:662
]


def normalize(s: str) -> str:
    r"""空白归一化：去掉所有空白字符，用于命中判定。

    C#: Regex.Replace(s, @"\s+", "")
    为什么必须归一化：PDF 提取时每个物理行尾会插入换行，同一短语
    在 PDF 文本里可能被拆成多行 —— 归一化后「逐字子串」判定才可靠。
    """
    return "".join(s.split())  # C#: string.Concat(s.Where(c => !char.IsWhiteSpace(c)))
