"""test_calculator.py —— Week 2 Lesson 1: pytest 入门测试。

====================================================================
C# 开发者必读：pytest  vs  NUnit/xUnit 核心差异
====================================================================

| 概念                | C# (NUnit/xUnit)              | Python (pytest)                    |
|---------------------|-------------------------------|------------------------------------|
| 测试类              | [TestFixture] + public class  | 不需要类！函数即测试               |
| 测试方法            | [Test] + public void          | def test_xxx():                    |
| 断言                | Assert.AreEqual(a, b)         | assert a == b                      |
| 异常断言            | Assert.Throws<X>(() => ...)   | with pytest.raises(X):             |
| Setup/Teardown      | [SetUp] / [TearDown]          | @pytest.fixture + yield             |
| 参数化              | [TestCase(1,2,3)]             | @pytest.mark.parametrize(...)      |
| 测试发现            | 编译时（属性反射）            | 运行时（函数名约定 test_*）        |
| 运行方式            | dotnet test                   | pytest                             |

pytest 核心哲学: "No boilerplate" — 不需要类、不需要 [Test] 属性、不需要 Assert.XXX
"""

# C#: using Xunit; / using NUnit.Framework;
# C#: using FluentAssertions;（Python 的 assert 自带丰富错误信息，无需第三方库）
import pytest

# C#: using static MyProject.Calculator;（导入被测试模块的函数）
from src.ai_cost_calculator.calculator import (
    calc_call_cost,
    load_config,
    parse_calls,
    parse_models,
    summarize_by_model,
    total_cost,
)
from src.ai_cost_calculator.models import CallRecord, CostSummary, Model


# =====================================================================
# Lesson 1a: 最简单的测试 —— assert 关键字
# =====================================================================
# Python 的 assert 相当于 C# 的 Assert.IsTrue() / Assert.AreEqual()
# 区别：pytest 用原生 assert + 运算符，pytest 会自动改写字节码
#       生成详细的失败信息（类似 FluentAssertions 的效果）
# =====================================================================


class TestCalcCallCost:  # C#: public class CalcCallCostTests（类不是必须的，但可以按模块分组）
    """测试 calc_call_cost() 函数 —— 最简单的纯函数，无副作用。"""

    def test_basic_calculation(self):
        """最基本的费用计算。"""
        # Arrange —— C#: var model = new Model("test", 2.0, 8.0);
        #                        var call  = new CallRecord(1, "test", 1000, 500);
        model = Model(name="test", input_price_per_1m=2.0, output_price_per_1m=8.0)
        call = CallRecord(call_id=1, model="test", input_tokens=1_000_000, output_tokens=1_000_000)

        # Act —— C#: double cost = Calculator.CalcCallCost(call, model);
        cost = calc_call_cost(call, model)

        # Assert —— C#: Assert.AreEqual(10.0, cost);
        assert cost == 10.0  # 2.0 + 8.0 = 10.0

    def test_zero_tokens(self):
        """输入输出 token 都为 0 时，费用应为 0。"""
        model = Model(name="free", input_price_per_1m=100.0, output_price_per_1m=200.0)
        call = CallRecord(call_id=1, model="free", input_tokens=0, output_tokens=0)

        cost = calc_call_cost(call, model)

        assert cost == 0.0  # C#: Assert.Equal(0.0, cost);

    def test_only_input_tokens(self):
        """只有输入 token，没有输出 token 的调用。"""
        model = Model(name="input-only", input_price_per_1m=5.0, output_price_per_1m=10.0)
        call = CallRecord(call_id=1, model="input-only", input_tokens=500_000, output_tokens=0)

        cost = calc_call_cost(call, model)

        # 500000 / 1,000,000 * 5.0 = 2.5
        assert cost == 2.5

    # Lesson 2 预告：@pytest.mark.parametrize 可以消除这种"copy-paste 测试法"
    def test_floating_point_precision(self):
        """测试浮点数精度 —— pytest 对 assert 的浮点比较有特殊处理。"""
        model = Model(name="cheap", input_price_per_1m=0.001, output_price_per_1m=0.001)
        call = CallRecord(call_id=1, model="cheap", input_tokens=3, output_tokens=7)

        cost = calc_call_cost(call, model)

        # C#: Assert.AreEqual(1e-8, cost, 1e-12); // 需要指定 tolerance
        # Python: 直接用 ==，但如果需要浮点容差用 pytest.approx
        expected = (3 / 1_000_000 * 0.001) + (7 / 1_000_000 * 0.001)  # = 1e-8
        assert cost == expected


# =====================================================================
# Lesson 2a: 参数化测试 —— @pytest.mark.parametrize
# =====================================================================
# 上面 4 个重复的 test_xxx 方法，现在压缩成 1 个参数化方法。
# 每一组参数 = 一次独立的测试执行，就像 C# 的多个 [TestCase]
# =====================================================================


class TestCalcCallCostParametrized:
    """参数化版 —— 一行 @pytest.mark.parametrize 替代 4 个重复方法。

    C# 对照:
        [TestCase(2.0,   8.0,   1000000, 1000000, 10.0)]   // 基本计算
        [TestCase(100.0, 200.0, 0,       0,       0.0)]    // 零 token
        [TestCase(5.0,   10.0,  500000,  0,       2.5)]    // 只有输入
        [TestCase(0.001, 0.001, 3,       7,       1e-8)]   // 浮点精度
        public void CalcCost_ReturnsExpected(
            double inPrice, double outPrice, int inTokens, int outTokens, double expected)
    """

    @pytest.mark.parametrize(
        # 第一个参数：逗号分隔的参数名（对应下面方法的 5 个参数）
        "in_price, out_price, in_tokens, out_tokens, expected",
        # 第二个参数：测试数据列表，每组是一个元组（等价一个 [TestCase]）
        [
            (2.0,   8.0,   1_000_000, 1_000_000, 10.0),   # 基本计算: 2.0 + 8.0
            (100.0, 200.0, 0,         0,         0.0),    # 零 token → 0
            (5.0,   10.0,  500_000,   0,         2.5),    # 只有输入: 0.5 * 5.0
            (0.001, 0.001, 3,         7,         1e-8),   # 浮点精度
        ],
    )
    def test_calc_cost(self, in_price, out_price, in_tokens, out_tokens, expected):
        """同一份测试逻辑，跑 4 组数据。"""
        # Arrange —— 用参数构造被测对象（不再手写 4 遍）
        model = Model(name="param", input_price_per_1m=in_price, output_price_per_1m=out_price)
        call = CallRecord(call_id=1, model="param", input_tokens=in_tokens, output_tokens=out_tokens)

        # Act
        cost = calc_call_cost(call, model)

        # Assert
        assert cost == expected  # C#: Assert.AreEqual(expected, cost);


class TestTotalCost:
    """测试 total_cost() 函数 —— sum() + 生成器表达式。"""

    def test_empty_list(self):
        """空列表的总费用为 0。"""
        # C#: var empty = new List<CostSummary>();
        # C#: Assert.Equal(0.0, Calculator.TotalCost(empty));
        assert total_cost([]) == 0.0  # C#: [] → new List<T>()

    def test_single_model(self):
        """单个模型的汇总。"""
        summaries: list[CostSummary] = [  # C#: List<CostSummary>
            CostSummary(
                model="gpt-4o",
                call_count=5,
                total_input_tokens=10000,
                total_output_tokens=5000,
                total_cost=12.5,
            )
        ]
        assert total_cost(summaries) == 12.5

    def test_multiple_models(self):
        """多个模型的汇总 —— 考验加法是否正确。"""
        summaries: list[CostSummary] = [
            CostSummary(model="a", call_count=2, total_input_tokens=100, total_output_tokens=50, total_cost=3.0),
            CostSummary(model="b", call_count=3, total_input_tokens=200, total_output_tokens=100, total_cost=7.0),
        ]
        assert total_cost(summaries) == 10.0  # C#: Assert.Equal(10.0, result);


# =====================================================================
# Lesson 2b: 参数化的进阶用法
# =====================================================================
# ① ids —— 自定义测试名（NUnit 的 TestName 属性类似）
# ② 参数可以传任何对象（不限于简单类型），测试逻辑不变
# =====================================================================


class TestTotalCostParametrized:
    """参数化版 total_cost —— 用 ids 给每组数据起名字。"""

    @pytest.mark.parametrize(
        "summaries, expected",
        [
            # 空列表 —— C#: new List<CostSummary>() { }
            ([], 0.0),
            # 单个模型
            (
                [CostSummary(model="single", call_count=5, total_input_tokens=10000, total_output_tokens=5000, total_cost=12.5)],
                12.5,
            ),
            # 多个模型
            (
                [
                    CostSummary(model="a", call_count=2, total_input_tokens=100, total_output_tokens=50, total_cost=3.0),
                    CostSummary(model="b", call_count=3, total_input_tokens=200, total_output_tokens=100, total_cost=7.0),
                ],
                10.0,
            ),
        ],
        # ids: 给每组数据起可读的名字，否则 pytest 自动生成 [0]/[1]/[2]
        # C#: NUnit 的 [TestCase(...)] 会自动用参数生成名字，或用 TestName 指定
        ids=["空列表", "单个模型", "多个模型"],
    )
    def test_total_cost(self, summaries, expected):
        """同一段逻辑，跑 3 组不同的 CostSummary 列表。"""
        assert total_cost(summaries) == expected  # C#: Assert.Equal(expected, totalCost);


# =====================================================================
# Lesson 2c: fixture 参数化 —— 同一个测试跑多组 fixture 数据
# =====================================================================
# C# 对照: NUnit 的 [TestCaseSource] 或 xUnit 的 MemberData
# 区别: fixture 参数化会把"准备数据"和"测试逻辑"分开
# =====================================================================


@pytest.fixture(params=[1.0, 10.0, 100.0])  # C#: 相当于参数化 fixture（xUnit 的 Theory 数据源）
def any_price(request) -> float:  # C#: 参数 request 是 pytest 的上下文对象
    """参数化的 fixture —— 每次调用会依次返回 1.0 / 10.0 / 100.0。

    request.param 是 pytest 注入的当前参数值。
    C# 没有直接等价物，最接近的是 [TestCaseSource] 提供数据。
    """
    return request.param


class TestFixturized:
    """演示 fixture 参数化 —— 一个测试自动跑 3 遍。"""

    def test_price_is_positive(self, any_price):
        """无论参数是多少，价格都必须是正数。"""
        assert any_price > 0  # C#: Assert.Greater(anyPrice, 0);


# =====================================================================
# Lesson 1b: 异常测试 —— pytest.raises 对照 C# 的 Assert.Throws<T>
# =====================================================================

class TestLoadConfigErrors:
    """测试 load_config() 的错误处理路径。

    C# 对比:
        Assert.Throws<FileNotFoundException>(() => Calculator.LoadConfig("nope.json"));

    Python:
        with pytest.raises(FileNotFoundError):
            load_config("nope.json")
    """

    def test_file_not_found(self):
        """配置文件不存在时，应抛出 FileNotFoundError。"""
        # C#: Assert.Throws<FileNotFoundException>(() => ...);
        # Python 用 with 上下文管理器包装被测调用
        with pytest.raises(FileNotFoundError) as exc_info:  # C#: using var exc = Assert.Throws<...>
            load_config("this_file_does_not_exist.json")

        # C#: StringAssert.Contains(exc.Message, "配置文件不存在");
        # exc_info.value 是被捕异常对象，类型是 FileNotFoundError
        assert "配置文件不存在" in str(exc_info.value)  # C#: exc_info.value → exc.Message

    def test_json_decode_error(self, tmp_path):
        """配置文件内容不是合法 JSON 时应抛出异常。

        tmp_path 是 pytest 内置 fixture（无需定义），提供临时目录。
        C#: Path.GetTempPath() + 自动清理
        """
        # Arrange —— 创建一个"格式错误"的 JSON 文件
        bad_json: str = str(tmp_path / "bad.json")  # C#: Path.Combine(tmpPath, "bad.json")
        with open(bad_json, "w", encoding="utf-8") as f:
            f.write("这不是合法的 JSON {{{")  # 故意写乱码

        # Act & Assert —— C#: Assert.Throws<JsonException>(...)
        with pytest.raises(ValueError):  # load_config 把 JSON 错误包装成 ValueError
            load_config(bad_json)

    def test_missing_required_keys(self, temp_config_file_missing_keys):
        """配置文件缺少 'calls' 字段时应抛出 ValueError。

        这里使用了 conftest.py 中自定义的 fixture ——
        C# 中你需要一个 helper 方法创建临时文件，pytest 直接注入。
        """
        with pytest.raises(ValueError) as exc_info:
            load_config(temp_config_file_missing_keys)

        assert "缺少" in str(exc_info.value)  # C#: Assert.Contains("缺少", exc.Message);


# =====================================================================
# Lesson 1c: 数据类测试 —— parse_models / parse_calls（**kwargs 展开）
# =====================================================================

class TestParseModels:
    """测试 parse_models() —— 列表推导式 + **dict 展开。

    C# 对比:
        rawModels.Select(m => new Model { Name = m["name"], ... }).ToList();

    Python 的 Model(**m) 等价于:
        Model(name=m["name"], input_price_per_1m=m["input_price_per_1m"], ...)
        ** 把 dict 的 key-value 展开成函数的关键字参数 —— C# 没有直接等价物。
    """

    def test_empty_list(self):
        """空列表 → 空列表。"""
        # C#: var result = ParseModels(new List<Dict>());
        # C#: Assert.IsEmpty(result);
        assert parse_models([]) == []  # C#: [] → new List<T>()

    def test_single_dict(self, sample_model_data):
        """单个 dict → 单个 Model 对象。"""
        # C#: sample_model_data[0] → sample_model_data.First()
        single: list[dict] = [sample_model_data[0]]  # C#: 切片 single[0] → single[0] 不，是取第一个元素

        models: list[Model] = parse_models(single)  # C#: List<Model>

        # 断言列表长度
        assert len(models) == 1  # C#: Assert.Single(models); / Assert.Equal(1, models.Count);
        # 按属性断言
        assert models[0].name == "gpt-4o"  # C#: Assert.Equal("gpt-4o", models[0].Name);
        assert models[0].input_price_per_1m == 2.50
        assert models[0].output_price_per_1m == 10.00

    def test_multiple_dicts(self, sample_model_data):
        """多个 dict → 多个 Model 对象。"""
        models: list[Model] = parse_models(sample_model_data)

        assert len(models) == 2  # C#: Assert.Equal(2, models.Count);
        # C#: models.Select(m => m.Name).ToList();
        assert [m.name for m in models] == ["gpt-4o", "gpt-4o-mini"]  # C#: 列表推导式 = LINQ Select + ToList


class TestParseCalls:
    """测试 parse_calls() —— 与 parse_models 同样的模式。

    用来演示：一旦理解了 ** 展开，所有 parse_xxx 函数都长一样。
    """

    def test_parse_calls(self, sample_call_data):
        """基本解析测试。"""
        calls: list[CallRecord] = parse_calls(sample_call_data)

        assert len(calls) == 3
        # C#: calls.All(c => c is CallRecord)
        # Python: all 函数 + 生成器表达式（类似 LINQ All）
        assert all(isinstance(c, CallRecord) for c in calls)  # C#: isinstance = is 关键字


# =====================================================================
# Lesson 1d: 汇总逻辑 —— summarize_by_model（集成多个概念）
# =====================================================================

class TestSummarizeByModel:
    """测试 summarize_by_model() —— 聚合、排序、费用计算的综合测试。"""

    def test_summarize_with_fixtures(self, sample_model_data, sample_call_data):
        """使用 conftest.py 中的两个 fixture 做完整汇总测试。

        这个测试覆盖: Model(**m), CallRecord(**c), 字典聚合, 费用计算, 排序
        """
        # 复用 parse_xxx 函数（已经被我们单独测试过了，这里作为可信赖的组件）
        models: list[Model] = parse_models(sample_model_data)  # C#: List<Model>
        calls: list[CallRecord] = parse_calls(sample_call_data)  # C#: List<CallRecord>

        summaries: list[CostSummary] = summarize_by_model(calls, models)  # C#: List<CostSummary>

        # 断言：应该有 2 个模型的汇总（gpt-4o 和 gpt-4o-mini）
        assert len(summaries) == 2

        # 按调用次数降序排列，gpt-4o 有 2 条调用，排第一
        assert summaries[0].model == "gpt-4o"  # C#: Assert.Equal("gpt-4o", summaries[0].Model);
        assert summaries[0].call_count == 2  # C#: Assert.Equal(2, summaries[0].CallCount);

        # gpt-4o 的 token 统计
        # call_id=1: in=1000, out=500
        # call_id=2: in=2000, out=300
        # 合计: in=3000, out=800
        assert summaries[0].total_input_tokens == 3000
        assert summaries[0].total_output_tokens == 800

        # gpt-4o-mini 有 1 条调用
        assert summaries[1].model == "gpt-4o-mini"
        assert summaries[1].call_count == 1

    def test_single_call(self):
        """只有一条调用记录时也能正常汇总。"""
        model: list[Model] = [Model(name="solo", input_price_per_1m=1.0, output_price_per_1m=2.0)]
        call: list[CallRecord] = [CallRecord(call_id=1, model="solo", input_tokens=1_000_000, output_tokens=1_000_000)]

        summaries: list[CostSummary] = summarize_by_model(call, model)

        assert len(summaries) == 1
        assert summaries[0].total_cost == 3.0  # 1.0 + 2.0

    def test_unknown_model_no_price(self):
        """调用了一个没在 models 列表中的模型 —— 费用应为 0，但不崩溃。"""
        models: list[Model] = [Model(name="known", input_price_per_1m=1.0, output_price_per_1m=1.0)]
        calls: list[CallRecord] = [CallRecord(call_id=1, model="unknown_model", input_tokens=1000, output_tokens=500)]

        summaries: list[CostSummary] = summarize_by_model(calls, models)

        assert len(summaries) == 1
        assert summaries[0].total_cost == 0.0  # 找不到价格，跳过费用计算


# =====================================================================
# 补充：测试 load_config 成功路径（需要一个真实文件）
# =====================================================================

class TestLoadConfigSuccess:
    """测试 load_config() 的正常路径。"""

    def test_load_valid_config(self, temp_config_file):
        """使用 conftest.py 的 temp_config_file fixture。

        temp_config_file 是一个 yield fixture —— 测试结束后自动删除临时文件。
        类似 C# 中 using var tmp = new TempFile(); ...; // Dispose 清理
        """
        data: dict = load_config(temp_config_file)  # C#: var data = LoadConfig(path);

        # C#: Assert.Contains("models", data.Keys);
        assert "models" in data  # C#: data.Keys.Contains("models")
        assert "calls" in data
        assert len(data["models"]) == 1  # C#: Assert.Single(data["models"]);
        assert data["models"][0]["name"] == "test-model"  # C#: data["Models"][0]["Name"]
