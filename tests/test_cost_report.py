"""test_cost_report.py —— CostReport 类测试（知识点 1/2/3/4）。

C# 对照：
- class 分组测试 ≈ 多个 [TestFixture] 类
- 复用 Week 1 conftest.py 的 fixture：sample_model_data / sample_call_data / temp_config_file
- 本次新增概念：pytest.approx（C#: Assert.AreEqual 带 tolerance —— 浮点不能直接 ==）
"""

import pytest  # C#: using Xunit; / using NUnit.Framework;

# C#: using MyProject.CostReport;（导入被测模块）
from src.ai_cost_calculator.models import CallRecord, Model
from src.cost_reporter.errors import ConfigValidationError, CostReportError, UnknownModelError
from src.cost_reporter.report import CostReport


def make_report() -> CostReport:
    """测试辅助函数：用固定数据构造报告（C#: private static CostReport CreateReport()）。

    数据：模型 a 输入 2.0 / 输出 8.0 每百万 token
    call1: 1M 输入 + 1M 输出 → 2.0 + 8.0 = 10.0
    call2: 500k 输入 + 0 输出 → 0.5 * 2.0 = 1.0
    总计: 11.0，平均: 5.5
    """
    models = [Model(name="a", input_price_per_1m=2.0, output_price_per_1m=8.0)]
    calls = [
        CallRecord(call_id=1, model="a", input_tokens=1_000_000, output_tokens=1_000_000),
        CallRecord(call_id=2, model="a", input_tokens=500_000, output_tokens=0),
    ]
    return CostReport(models=models, calls=calls)


# =====================================================================
# 知识点 1：类方法工厂 from_config —— 复用 Week 1 的 temp_config_file fixture
# =====================================================================


class TestFromConfig:
    """from_config() 类方法工厂（C#: 静态工厂方法）。"""

    def test_from_config(self, temp_config_file):
        """读取真实临时配置文件，应正确构造报告。

        temp_config_file 内容：test-model 输入 1.0 / 输出 4.0；1 次调用 (100 in, 50 out)
        """
        report = CostReport.from_config(temp_config_file)  # C#: CostReport.FromConfig(path)

        assert report.call_count == 1  # C#: Assert.Equal(1, report.CallCount);
        assert report.models[0].name == "test-model"
        # 100/1e6*1.0 + 50/1e6*4.0 = 0.0001 + 0.0002 = 0.0003
        # 浮点误差：1e-4 + 2e-4 在二进制里不是精确值 → 用 pytest.approx
        # C#: Assert.AreEqual(0.0003, report.TotalCost, 1e-9);  // 需要 tolerance
        assert report.total_cost == pytest.approx(0.0003)


# =====================================================================
# 知识点 2：@property 计算属性
# =====================================================================


class TestProperties:
    """计算属性（C#: get-only 属性）—— 访问时不带括号，调用方无需知道是字段还是计算。"""

    def test_call_count(self):
        """调用总次数。"""
        assert make_report().call_count == 2  # C#: Assert.Equal(2, report.CallCount);

    def test_total_cost(self):
        """总费用 = 10.0 + 1.0 = 11.0（整数运算，可精确比较）。"""
        assert make_report().total_cost == 11.0

    def test_avg_cost_per_call(self):
        """平均每次费用 = 11.0 / 2 = 5.5。"""
        assert make_report().avg_cost_per_call == 5.5

    def test_empty_report_avg_is_zero(self):
        """空报告（0 次调用）平均费用应为 0.0 —— 而不是除零崩溃。"""
        empty = CostReport(models=[], calls=[])  # C#: new CostReport([], [])

        assert empty.call_count == 0
        assert empty.total_cost == 0.0
        assert empty.avg_cost_per_call == 0.0

    def test_property_is_readonly(self):
        """只读属性赋值应抛 AttributeError。

        C#: 只读属性赋值 → 编译错误（写不了这段代码）；
        Python: 动态语言，运行时才报错 —— 用 pytest.raises 验证。
        """
        report = make_report()

        # C#: report.AvgCostPerCall = 5.0; // 编译错误 CS0200
        with pytest.raises(AttributeError):
            report.avg_cost_per_call = 5.0  # type: ignore[misc]


# =====================================================================
# 知识点 3：魔术方法 __str__ / __repr__ / __eq__
# =====================================================================


class TestStrRepr:
    """__str__ / __repr__（C#: ToString()）。"""

    def test_str_contains_key_info(self):
        """str() 应包含关键统计信息（用于日志/展示）。"""
        text = str(make_report())  # C#: report.ToString()

        assert "CostReport" in text
        assert "总费用" in text
        assert "11.0000" in text  # f-string 格式化后的值

    def test_print_uses_str(self):
        """print(obj) 自动调用 __str__ —— 验证"魔术方法自动触发"机制。"""
        # C#: Console.WriteLine(report); // 也调用 ToString()
        import io  # C#: using System.IO;

        buffer = io.StringIO()  # 捕获 print 输出（C#: StringWriter）
        print(make_report(), file=buffer)  # 把打印目标换成内存缓冲区

        assert "CostReport" in buffer.getvalue()

    def test_repr_contains_class_name_and_fields(self):
        """repr() 应包含类名和关键字段（调试表示）。"""
        text = repr(make_report())

        assert text.startswith("CostReport(")
        assert "models=" in text
        assert "calls=" in text


class TestEq:
    """__eq__ 相等比较（C#: Equals / ==）。"""

    def test_same_data_are_equal(self):
        """相同数据的两个报告应相等（值相等，不是引用相等）。"""
        r1 = make_report()
        r2 = make_report()

        # C#: 引用相等 vs 值相等 —— record/值类型是值相等，class 默认是引用相等
        assert r1 == r2

    def test_different_calls_are_not_equal(self):
        """调用数据不同则报告不相等。"""
        r1 = make_report()
        r2 = make_report()
        r2.calls.append(  # 加一条调用（C#: r2.Calls.Add(...)）
            CallRecord(call_id=3, model="a", input_tokens=100, output_tokens=100)
        )

        assert r1 != r2

    def test_compare_with_other_type_returns_false(self):
        """与其它类型比较返回 False（而不是抛异常）。"""
        report = make_report()

        assert (report == 1) is False  # C#: report.Equals(1) → false
        assert (report == "CostReport") is False


# =====================================================================
# 知识点 4：自定义异常 + validate()
# =====================================================================


class TestValidate:
    """validate() 校验 —— 自定义异常的调用场景。"""

    def test_valid_report_passes(self):
        """所有模型都有价格时，validate() 不抛异常。"""
        report = make_report()

        assert report.validate() is None  # 正常返回

    def test_unknown_model_raises(self):
        """调用了未配置价格的模型 → 抛 UnknownModelError。"""
        models = [Model(name="known", input_price_per_1m=1.0, output_price_per_1m=1.0)]
        calls = [
            CallRecord(call_id=1, model="known", input_tokens=100, output_tokens=50),
            CallRecord(call_id=2, model="ghost", input_tokens=100, output_tokens=50),
        ]
        report = CostReport(models=models, calls=calls)

        # C#: Assert.Throws<UnknownModelError>(() => report.Validate());
        with pytest.raises(UnknownModelError) as exc_info:
            report.validate()

        # 异常消息应包含未知模型名 —— C#: StringAssert.Contains("ghost", ex.Message)
        assert "ghost" in str(exc_info.value)

    def test_exception_hierarchy(self):
        """异常继承体系：具体异常都是 CostReportError 的子类。

        C#: typeof(UnknownModelError).IsSubclassOf(typeof(CostReportError))
        意义：CLI 里 except CostReportError 一次捕获所有业务异常。
        """
        assert issubclass(UnknownModelError, CostReportError)
        assert issubclass(ConfigValidationError, CostReportError)
        assert issubclass(CostReportError, Exception)  # 根是内置 Exception
