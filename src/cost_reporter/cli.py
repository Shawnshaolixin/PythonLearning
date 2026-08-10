"""命令行入口 —— 沿用 Week 1 cli.py 的结构模式。

本周新增的部分：
- --format 参数 → FORMATTERS 字典（把类当值用）→ 多态调用（知识点 5）
- report.validate() → 自定义异常 → except CostReportError 一次捕获（知识点 4）
- CostReport.from_config() 类方法工厂（知识点 1）
"""

import argparse  # C#: 命令行参数解析（System.CommandLine 或手动解析 args）

try:
    from .errors import CostReportError
    from .formatters import FORMATTERS, ReportFormatter
    from .report import CostReport
except ImportError:
    # 直接运行本文件时（python cli.py），回退到同目录导入 —— 与 Week 1 相同模式
    from errors import CostReportError  # type: ignore[no-redef]
    from formatters import FORMATTERS, ReportFormatter  # type: ignore[no-redef]
    from report import CostReport  # type: ignore[no-redef]


def main() -> None:  # C#: public static void Main(string[] args)
    # 1. 解析命令行参数
    parser = argparse.ArgumentParser(
        description="LLM 调用费用账单报告生成器（Week 2: 面向对象进阶）"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="JSON 配置文件路径（默认: config.json）",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=FORMATTERS.keys(),  # choices 自动校验并生成错误提示（C#: 枚举校验）
        default="text",
        help="输出格式: text / markdown / json（默认: text）",
    )
    args = parser.parse_args()

    # 2. 读取配置 + 校验（用 try/except 捕获可预期的错误，给出友好提示）
    try:
        report = CostReport.from_config(args.config)  # 类方法工厂
        report.validate()  # 未知模型 → UnknownModelError（fail-fast）
    except (CostReportError, FileNotFoundError, ValueError, KeyError) as e:
        # CostReportError 是业务异常树的根 —— 一次捕获所有自定义异常
        # C#: catch (CostReportError ex) { }  +  兜底 catch (Exception ex)
        print(f"错误: {e}")
        print("请检查配置文件路径和格式是否正确。")
        return

    # 3. 格式化输出（多态：formatter 静态类型是抽象基类，实际是某个子类实例）
    # FORMATTERS["text"] 是类 → FORMATTERS["text"]() 创建实例
    # C#: var formatter = _formatters[args.Format]();  // IReportFormatter
    formatter: ReportFormatter = FORMATTERS[args.format]()
    print(formatter.format(report))


# 只有直接运行本文件时才执行 main()；
# 被 import 时不执行 —— 这是 Python 的标准入口约定（C#: Main() 由 CLR 调用）
if __name__ == "__main__":
    main()
