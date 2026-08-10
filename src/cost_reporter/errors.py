"""自定义异常模块 —— 知识点 4：Python 自定义异常体系。

C# 对照：
    public class CostReportError : Exception { }
    public class UnknownModelError : CostReportError { }

为什么要自定义异常？
- 比内置异常表达力更强 —— C# 中你不会在业务层抛 Exception，而是抛业务异常
- CLI 里 `except CostReportError` 一次捕获整棵业务异常树（C#: catch (CostReportError)）
- 测试里 `pytest.raises(UnknownModelError)` 精确断言（C#: Assert.Throws<UnknownModelError>）

设计惯例（C# / Python 相同）：
- 异常类名以 Error / Exception 结尾
- 派生一个"业务异常基类"，具体异常继承它 —— 调用方只捕获基类即可覆盖全部业务错误
"""


class CostReportError(Exception):
    """费用报告业务异常的基类。C#: public class CostReportError : Exception

    不需要写 __init__ —— Exception 基类自带 (message) 构造函数，
    直接 raise CostReportError("...") 传消息即可。
    C#: 同理，自定义异常通常只继承，不重写构造函数（除非要加额外字段）。
    """

    pass  # pass = 空类体占位（C#: {}），继承 + docstring 已经足够


class ConfigValidationError(CostReportError):
    """配置文件结构错误（缺少字段、格式不对等）。C#: : CostReportError"""

    pass


class UnknownModelError(CostReportError):
    """调用了未配置价格的模型。C#: public class UnknownModelError : CostReportError

    对比 Week 1：summarize_by_model 对未知模型静默计 0 费用；
    Week 2 用 validate() 显式抛出 —— 把"配置错误"尽早暴露（fail-fast）。
    C#: 同样的取舍 —— 静默容忍 vs 快速失败。
    """

    pass
