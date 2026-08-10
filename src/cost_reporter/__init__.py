"""Week 2 项目：费用统计器 v2 —— 账单报告生成器。

练习知识点（面向对象进阶）：
- class / __init__ / self            → report.py    （C#: 类 / 构造函数 / this）
- @property 计算属性                 → report.py    （C#: get-only 属性）
- 魔术方法 __str__/__repr__/__eq__   → report.py    （C#: ToString / Equals）
- 自定义异常体系                     → errors.py    （C#: 自定义 Exception）
- 继承 + 抽象方法 + 方法重写          → formatters.py（C#: abstract class / override）
"""

from .errors import ConfigValidationError, CostReportError, UnknownModelError
from .report import CostReport

__all__ = [
    "CostReport",
    "CostReportError",
    "ConfigValidationError",
    "UnknownModelError",
]
