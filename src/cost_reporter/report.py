"""CostReport 类 —— 知识点 1/2/3：class + self、@property、魔术方法。

对比 Week 1 的 @dataclass（C#: record）：
- dataclass 是"数据容器" —— 自动生成 __init__/__repr__/__eq__，适合纯数据（Model/CallRecord）
- 本周手写普通 class —— 因为 CostReport 要"加行为"（方法、计算属性、校验）
  C#: 同样的取舍 —— record 适合数据，class 适合业务对象

计算逻辑全部复用 Week 1 的纯函数（calculator.py），
类只做"编排" —— 这是真实工程的常见结构：类封装状态和行为，函数做计算。
"""

from typing import List

try:
    # 场景 1: pytest（tests 从项目根目录导入，src 作为命名空间包）
    from src.ai_cost_calculator import calculator
    from src.ai_cost_calculator.models import CallRecord, CostSummary, Model
except ImportError:
    try:
        # 场景 2: 包已安装到 venv（uv run cost-reporter）—— 从 site-packages 导入
        from ai_cost_calculator import calculator  # type: ignore[no-redef]
        from ai_cost_calculator.models import CallRecord, CostSummary, Model  # type: ignore[no-redef]
    except ImportError:
        # 场景 3: 直接运行本文件（python report.py，无 venv）—— 同目录导入
        import calculator  # type: ignore[no-redef]
        from models import CallRecord, CostSummary, Model  # type: ignore[no-redef]

from .errors import UnknownModelError


class CostReport:
    """封装一份费用报告。C#: public class CostReport"""

    def __init__(self, models: List[Model], calls: List[CallRecord]) -> None:
        """构造函数。C#: public CostReport(List<Model> models, List<CallRecord> calls)

        注意：Python 的 self 必须显式写在参数列表第一位 ——
        C# 里 this 是隐式的，这是 C# 开发者最需要习惯的差异之一。
        """
        self.models = models  # C#: this.models = models;
        self.calls = calls  # C#: this.calls = calls;

    @classmethod
    def from_config(cls, path: str) -> "CostReport":
        """类方法工厂。C#: public static CostReport FromConfig(string path)

        @classmethod 的第一个参数是 cls（类本身）而非 self（实例），
        通过 cls(...) 创建实例 —— C#: 静态工厂方法（比直接用构造函数多一层语义）。
        这里把 Week 1 的 load_config / parse_models / parse_calls 包装成"一行"。
        """
        data = calculator.load_config(path)  # C#: var data = LoadConfig(path);
        models = calculator.parse_models(data["models"])
        calls = calculator.parse_calls(data["calls"])
        return cls(models=models, calls=calls)  # C#: return new CostReport(models, calls);

    def summarize(self) -> List[CostSummary]:
        """按模型汇总 —— 直接复用 Week 1 的纯函数，不重写聚合逻辑。"""
        return calculator.summarize_by_model(self.calls, self.models)

    # ============================================================
    # 知识点 2：@property 计算属性
    # ============================================================
    # C#: public int CallCount => calls.Count;  （get-only 属性）
    # Python 用 @property 把方法"伪装"成属性：
    #   report.call_count  （属性访问，无括号）
    #   而不是 report.call_count()  （方法调用）
    # 好处：调用方代码更干净；后续如果想改成"预计算好的字段"，调用方不用改（封装）

    @property
    def call_count(self) -> int:  # C#: public int CallCount => calls.Count;
        """调用总次数。"""
        return len(self.calls)  # C#: calls.Count

    @property
    def total_cost(self) -> float:  # C#: public double TotalCost => Calculator.TotalCost(...);
        """总费用 —— 复用 Week 1 的 total_cost() 函数。"""
        return calculator.total_cost(self.summarize())

    @property
    def avg_cost_per_call(self) -> float:
        """平均每次调用费用（纯计算属性）。

        注意：没有定义 setter → 属性是只读的。
        赋值会抛 AttributeError —— C# 只读属性赋值是编译错误，Python 是运行时错误。

        进阶提示（本周只了解概念）：如果 summarize() 很贵且被多次访问，
        可以用 functools.cached_property 缓存计算结果 —— 后续课程会用到。
        """
        if self.call_count == 0:  # C#: if (CallCount == 0)
            return 0.0  # 避免 ZeroDivisionError（C#: 除零异常）
        return self.total_cost / self.call_count

    # ============================================================
    # 知识点 3：魔术方法（dunder = double underscore，双下划线）
    # ============================================================
    # Python 在特定时机自动调用这些方法，无需显式调用：
    #   __str__ → str(obj) / print(obj) / f"{obj}"
    #   __repr__ → REPL 调试 / repr(obj)
    #   __eq__ → obj1 == obj2

    def __str__(self) -> str:
        """人类可读的简短摘要。C#: public override string ToString()

        约定：短、可读，用于日志和展示 —— 不追求完整，只给关键信息。
        """
        return (
            f"CostReport(模型数={len(self.models)}, 调用次数={self.call_count}, "
            f"总费用={self.total_cost:.4f}元, 平均={self.avg_cost_per_call:.4f}元/次)"
        )

    def __repr__(self) -> str:
        """无歧义的调试表示。C#: 没有直接对应，约等于调试器里看到的对象内容

        约定：带类名 + 关键字段，尽量能"还原"对象，用于 REPL 和调试。
        如果不定义 __repr__，默认输出 <CostReport object at 0x...> —— 没有信息量。
        !r 表示对值调用 repr()（f-string 格式化语法，C#: $"{{...}}" 无直接对应）。
        """
        return f"CostReport(models={self.models!r}, calls={self.calls!r})"

    def __eq__(self, other: object) -> bool:
        """相等比较。C#: public override bool Equals(object? other)

        用 == 运算符时自动调用。要点：
        - isinstance 守卫：类型不同返回 NotImplemented（C#: if (other is not CostReport) return false;）
        - Model / CallRecord 是 dataclass，自带值相等比较（C#: record 的 ==）
        - 定义 __eq__ 后对象自动"不可哈希"（__hash__ 被置为 None）—— 因为
          哈希约定要求相等的对象哈希值也相等（C#: 覆写 Equals 必须同时覆写 GetHashCode）
        """
        if not isinstance(other, CostReport):  # C#: other is CostReport
            return NotImplemented  # 交给 Python 决定 → 与其它类型比较结果为 False
        return self.models == other.models and self.calls == other.calls

    # ============================================================
    # 校验 —— 自定义异常（知识点 4）的实际调用场景
    # ============================================================

    def validate(self) -> None:
        """校验所有调用都引用了已配置的模型。C#: public void Validate()

        对比 Week 1：summarize_by_model 对未知模型静默算 0 费用；
        这里提供显式校验，把配置错误尽早暴露（fail-fast，C# 中同样的理念）。
        找不到价格 = 配置写错了 = 应该大声报错，而不是默默出 0。
        """
        known = {m.name for m in self.models}  # C#: models.Select(m => m.Name).ToHashSet()
        # 集合差集：调用的模型名 - 已知模型名 = 未知模型
        # C#: calls.Select(c => c.Model).Distinct().Except(known)
        unknown = sorted({c.model for c in self.calls} - known)

        if unknown:  # C#: if (unknown.Any())
            # raise 自定义异常 —— C#: throw new UnknownModelError($"未知模型: ...")
            raise UnknownModelError(
                f"未知模型: {', '.join(unknown)} —— 请在配置文件的 models 中补充价格"
            )
