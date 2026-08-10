"""格式化器模块 —— 知识点 5：继承 + 抽象方法 + 方法重写（多态）。

C# 对照：
    public abstract class ReportFormatter
    {
        public abstract string Format(CostReport report);
    }
    public class TextFormatter : ReportFormatter
    {
        public override string Format(CostReport report) { ... }
    }

设计意图：同一个 format(report) 接口，多种输出格式 —— 多态（polymorphism）。
调用方（cli.py）只面向抽象基类编程，不需要知道具体是哪种格式化器。

Bonus：FORMATTERS 字典把"格式名 → 类"存起来（类也是"对象"），
CLI 加新格式只需在这里加一行，不用改 if/elif 链。
C#: 类似 Dictionary<string, Func<...>> 或简单工厂方法。
"""

import json  # C#: using System.Text.Json;

from abc import ABC, abstractmethod  # C#: abstract class 关键字

try:
    from .report import CostReport
except ImportError:
    from report import CostReport  # type: ignore[no-redef]  # 直接运行模块场景


class ReportFormatter(ABC):  # C#: public abstract class ReportFormatter
    """格式化器的抽象基类 —— 声明接口，不提供实现。

    ABC = Abstract Base Class。继承它的子类必须实现所有 @abstractmethod，
    否则子类也无法实例化（C#: 抽象类不能 new，派生类不实现抽象方法就编译不过）。
    """

    @abstractmethod  # C#: public abstract string Format(CostReport report);
    def format(self, report: CostReport) -> str:
        """把报告格式化成字符串。子类必须实现（C#: override）—— 子类会重写本方法体。"""
        # 抽象方法体不会被调用（无法实例化），docstring 即"接口文档"
        raise NotImplementedError  # 防御性兜底（C#: throw new NotImplementedException()）


class TextFormatter(ReportFormatter):  # C#: public class TextFormatter : ReportFormatter
    """文本表格格式 —— 改造 Week 1 cli.py 的 format_table()。"""

    def format(self, report: CostReport) -> str:  # C#: public override string Format(...)
        summaries = report.summarize()
        lines = [
            f"{'模型':<24}{'次数':>6}{'输入token':>14}{'输出token':>14}{'费用(元)':>12}"
        ]
        lines.append("-" * 70)
        for s in summaries:  # C#: foreach (var s in summaries)
            lines.append(
                f"{s.model:<24}{s.call_count:>6}{s.total_input_tokens:>14}"
                f"{s.total_output_tokens:>14}{s.total_cost:>12.4f}"
            )
        lines.append("-" * 70)
        lines.append(
            f"{'合计':<24}{'':>6}{'':>14}{'':>14}{report.total_cost:>12.4f}"
        )
        return "\n".join(lines)  # C#: string.Join("\n", lines)


class MarkdownFormatter(ReportFormatter):
    """Markdown 表格格式 —— 同样的数据，不同的输出样式。"""

    def format(self, report: CostReport) -> str:
        summaries = report.summarize()
        lines = [
            "| 模型 | 次数 | 输入token | 输出token | 费用(元) |",
            "|------|-----:|----------:|----------:|---------:|",
        ]
        for s in summaries:
            lines.append(
                f"| {s.model} | {s.call_count} | {s.total_input_tokens} | "
                f"{s.total_output_tokens} | {s.total_cost:.4f} |"
            )
        lines.append(f"| **合计** |  |  |  | **{report.total_cost:.4f}** |")
        return "\n".join(lines)


class JsonFormatter(ReportFormatter):
    """JSON 格式 —— 复用 Week 1 to_json_dict() 的思路。"""

    def format(self, report: CostReport) -> str:
        # 列表推导式生成 dict 列表（C#: summaries.Select(s => new { ... }).ToList()）
        payload = {
            "total_cost": round(report.total_cost, 4),  # C#: Math.Round(..., 4)
            "models": [
                {
                    "model": s.model,
                    "call_count": s.call_count,
                    "input_tokens": s.total_input_tokens,
                    "output_tokens": s.total_output_tokens,
                    "cost": round(s.total_cost, 4),
                }
                for s in report.summarize()
            ],
        }
        # ensure_ascii=False 保留中文（否则 \uXXXX 转义）；
        # indent=2 美化输出 —— C#: JsonSerializerOptions { WriteIndented = true }
        return json.dumps(payload, ensure_ascii=False, indent=2)


# 格式化器注册表：格式名 → 类（注意存的是类，不是实例）
# 好处：cli.py 用 choices=FORMATTERS.keys() 校验参数，再 FORMATTERS[名字]() 取实例
# C#: Dictionary<string, Func<IReportFormatter>> + 工厂
FORMATTERS = {
    "text": TextFormatter,
    "markdown": MarkdownFormatter,
    "json": JsonFormatter,
}
