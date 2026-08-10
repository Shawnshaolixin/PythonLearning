"""pytest 共享配置 & Fixture 模块。

C# 对照概念:
  - conftest.py     →  NUnit 的 [SetUpFixture] / 共享 TestFixture
  - @pytest.fixture →  NUnit 的 [SetUp] + 内联数据 / xUnit 的 Fixture
  - fixture 会被 pytest 自动发现，无需显式 import

本文件中的 fixture 会被同目录及子目录下的所有 test_*.py 自动使用。
"""

import json  # C#: using System.Text.Json;
import tempfile  # C#: System.IO.Path.GetTempFileName()
from pathlib import Path  # C#: System.IO.Path + FileInfo
from typing import Any  # C#: object

import pytest  # C#: using Xunit; / using NUnit.Framework;


# ============================================================
# Lesson 1a: 最简单的 fixture — 提供固定测试数据
# ============================================================

# C# 对比: NUnit 中你会在 [SetUp] 里初始化字段；
#          pytest 用 @pytest.fixture 装饰器声明一个"可注入的工厂方法"
@pytest.fixture  # C#: 等价于标记 [SetUp] 但更灵活——返回值直接注入测试方法参数
def sample_model_data() -> list[dict[str, Any]]:  # C#: List<Dictionary<string, object>>
    """提供一份标准的模型价格数据（dict 列表形式，模拟 JSON 加载后的结构）。"""
    return [
        {
            "name": "gpt-4o",
            "input_price_per_1m": 2.50,
            "output_price_per_1m": 10.00,
        },
        {
            "name": "gpt-4o-mini",
            "input_price_per_1m": 0.15,
            "output_price_per_1m": 0.60,
        },
    ]


@pytest.fixture  # C#: 另一个 [SetUp] 方法，只负责不同的数据类型
def sample_call_data() -> list[dict[str, Any]]:
    """提供一份标准的调用记录数据。"""
    return [
        {"call_id": 1, "model": "gpt-4o", "input_tokens": 1000, "output_tokens": 500},
        {"call_id": 2, "model": "gpt-4o", "input_tokens": 2000, "output_tokens": 300},
        {"call_id": 3, "model": "gpt-4o-mini", "input_tokens": 5000, "output_tokens": 1000},
    ]


# ============================================================
# Lesson 1b: 临时文件 fixture — 测试 load_config 需要模拟文件系统
# ============================================================

@pytest.fixture  # C#: 类似 xUnit 的 IAsyncLifetime 或 NUnit 的 [OneTimeSetUp]
def temp_config_file() -> str:  # C#: string TempConfigFile()
    """创建一个真实存在的临时 JSON 配置文件，并返回其路径。

    yield 之后的部分 = C# 的 try/finally 清理逻辑
    """
    config_data: dict[str, Any] = {  # C#: var configData = new Dictionary<string, object>
        "models": [
            {"name": "test-model", "input_price_per_1m": 1.0, "output_price_per_1m": 4.0}
        ],
        "calls": [
            {"call_id": 1, "model": "test-model", "input_tokens": 100, "output_tokens": 50}
        ],
    }

    # C#: var tmpFile = Path.GetTempFileName();
    #      File.WriteAllText(tmpFile, JsonSerializer.Serialize(configData));
    tmp = Path(tempfile.mkdtemp()) / "test_config.json"  # C#: Path.Combine(tempDir, "test_config.json")
    tmp.write_text(json.dumps(config_data), encoding="utf-8")  # C#: File.WriteAllText(path, json, Encoding.UTF8)

    yield str(tmp)  # C#: return tmpFile;（但 yield 意味着"先给测试用，回来时清理"）

    # --- 清理阶段（yield 之后）--- C#: finally { File.Delete(tmpFile); }
    tmp.unlink(missing_ok=True)  # C#: File.Delete(path);
    tmp.parent.rmdir()  # C#: Directory.Delete(tempDir);


@pytest.fixture
def temp_config_file_missing_keys() -> str:
    """创建一个缺少 'calls' 字段的配置（用于测试校验逻辑）。"""
    tmp = Path(tempfile.mkdtemp()) / "bad_config.json"
    tmp.write_text(
        json.dumps({"models": []}),  # 只有 models，没有 calls
        encoding="utf-8",
    )
    yield str(tmp)
    tmp.unlink(missing_ok=True)
    tmp.parent.rmdir()
