"""test_formatters.py —— 格式化器继承体系测试（知识点 5）。

重点：多态 —— 所有格式化器实现同一个 format(report) 接口。
C# 对照：
    var formatters = new List<IReportFormatter> { new TextFormatter(), ... };
    foreach (var f in formatters) Console.WriteLine(f.Format(report));
"""

import json  # C#: using System.Text.Json;

import pytest

from src.ai_cost_calculator.models import CallRecord, Model
from src.cost_reporter.formatters import (
    FORMATTERS,
    JsonFormatter,
    MarkdownFormatter,
    ReportFormatter,
    TextFormatter,
)
from src.cost_reporter.report import CostReport


@pytest.fixture
def sample_report() -> CostReport:
    """构造一份固定数据的报告（C#: [SetUp] 里初始化被测对象）。

    数据：gpt-4o 输入 2.5 / 输出 10.0 每百万 token；1 次调用 (1M in, 500k out)
    费用 = 1.0*2.5 + 0.5*10.0 = 2.5 + 5.0 = 7.5
    """
    models = [Model(name="gpt-4o", input_price_per_1m=2.5, output_price_per_1m=10.0)]
    calls = [
        CallRecord(call_id=1, model="gpt-4o", input_tokens=1_000_000, output_tokens=500_000)
    ]
    return CostReport(models=models, calls=calls)


# =====================================================================
# 抽象基类（C#: abstract class）的约束
# =====================================================================


class TestAbstractBase:
    """ReportFormatter 是抽象类 —— 不能实例化。"""

    def test_abstract_class_cannot_instantiate(self):
        """直接创建抽象基类实例 → TypeError。

        C#: new ReportFormatter(); // 编译错误 CS0144（抽象类不能实例化）
        Python: 运行时才报错 —— ABC 机制检查 @abstractmethod 是否全部实现。
        """
        with pytest.raises(TypeError):
            ReportFormatter()  # type: ignore[abstract]


# =====================================================================
# 各格式化器的输出内容
# =====================================================================


class TestTextFormatter:
    """文本表格格式。"""

    def test_contains_header_and_total(self, sample_report):
        out = TextFormatter().format(sample_report)

        assert "模型" in out  # 表头
        assert "合计" in out  # 合计行
        assert "7.5000" in out  # 总费用（.4f 格式）
        assert "gpt-4o" in out  # 模型名


class TestMarkdownFormatter:
    """Markdown 表格格式。"""

    def test_contains_table_markers(self, sample_report):
        out = MarkdownFormatter().format(sample_report)

        assert "|" in out  # 表格分隔符
        assert "**合计**" in out  # markdown 加粗的合计行
        assert "7.5000" in out


class TestJsonFormatter:
    """JSON 格式。"""

    def test_output_is_valid_json(self, sample_report):
        out = JsonFormatter().format(sample_report)

        # json.loads 解析成功 → 说明是合法 JSON（C#: JsonSerializer.Deserialize）
        parsed = json.loads(out)

        assert parsed["total_cost"] == 7.5  # round(7.5, 4) 可精确比较
        assert parsed["models"][0]["model"] == "gpt-4o"
        assert parsed["models"][0]["call_count"] == 1
        assert parsed["models"][0]["cost"] == 7.5

    def test_keeps_chinese_characters(self, sample_report):
        """ensure_ascii=False → 中文以 UTF-8 直接输出（不转义成 \\uXXXX 序列）。"""
        out = JsonFormatter().format(sample_report)

        assert "\\u4e2d" not in out  # 若被转义，会看到 \\uXXXX 形式的序列
        assert '"model": "gpt-4o"' in out  # 结构字段名正常输出


# =====================================================================
# 多态：同一个接口，不同实现
# =====================================================================


class TestPolymorphism:
    """多态测试 —— 不关心具体子类，只调用抽象接口 format()。

    C#: foreach (var f in new IReportFormatter[] { ... }) f.Format(report);
    """

    @pytest.mark.parametrize(  # C#: [TestCase(typeof(TextFormatter))] 等 —— 复习 Week 1
        "formatter_cls",
        [TextFormatter, MarkdownFormatter, JsonFormatter],
        ids=["text", "markdown", "json"],  # 给每组数据起可读的名字
    )
    def test_every_formatter_produces_output(self, formatter_cls, sample_report):
        """每个格式化器都能对同一份报告产出非空字符串。"""
        formatter = formatter_cls()  # 传入的是类，() 创建实例

        out = formatter.format(sample_report)

        assert isinstance(out, str)
        assert len(out) > 0

    def test_all_formatters_are_subclasses(self):
        """所有格式化器都继承自 ReportFormatter。

        C#: typeof(TextFormatter).IsSubclassOf(typeof(ReportFormatter))
        这是多态的前提：可以统一当抽象基类用。
        """
        for cls in (TextFormatter, MarkdownFormatter, JsonFormatter):
            assert issubclass(cls, ReportFormatter)


class TestFormattersRegistry:
    """FORMATTERS 注册表 —— 格式名 → 类（知识点 5 的 Bonus）。"""

    def test_registry_has_all_three(self):
        assert set(FORMATTERS.keys()) == {"text", "markdown", "json"}

    def test_registry_values_are_formatter_classes(self):
        """注册表里存的是"类"，且都是 ReportFormatter 的子类。"""
        for name, cls in FORMATTERS.items():
            assert isinstance(cls, type)  # 值是类（type 的实例）
            assert issubclass(cls, ReportFormatter)
