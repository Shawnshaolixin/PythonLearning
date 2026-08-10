---
name: csharp-annotate
description: >
  写 Python 代码时，对每一个语法点和关键库函数添加 C# 映射注释。
  触发条件：用户要求学 Python、要求写代码示例、或明确说"标注 C#" 时。
---

# Python ↔ C# 对照注释规范

你是一位熟悉 **C# (.NET / Unity)** 的开发者，正在学习 Python。
每次编写 Python 代码（新文件、新函数、代码示例），都必须遵守以下注释规范。

## 核心原则

> **每一个 Python 语法点，旁边都要有「等价 C# 写法」的注释。**
>
> 初学者能通过注释直接理解 Python ↔ C# 的对应关系，无需查文档。

## 注释分类

### 1. 语法对照（必须）

Python 特有语法必须标注 C# 等价物：

| Python | 注释模板 |
|--------|---------|
| 列表推导式 `[x for x in xs if cond]` | `# C#: xs.Where(x => cond).Select(x => x).ToList()` |
| 字典推导式 `{k: v for k,v in d.items()}` | `# C#: d.ToDictionary(kvp => kvp.Key, kvp => kvp.Value)` |
| `with open(...) as f:` | `# C#: using var f = File.OpenRead(...)` |
| `lambda x: x * 2` | `# C#: x => x * 2` |
| `def func(x: int) -> str:` | `# C#: string Func(int x)` |
| `@dataclass` | `# C#: record` |
| `@property` | `# C#: public string Name { get; }` |
| `try/except X as e:` | `# C#: try/catch(X ex)` |
| `if __name__ == "__main__":` | `# C#: Main() 入口方法` |
| `self` | `# C#: this` |
| `__init__` | `# C#: 构造函数 ClassName(...)` |
| `__str__` / `__repr__` | `# C#: ToString()` |
| `isinstance(x, T)` | `# C#: x is T` |
| `enumerate(xs)` | `# C#: xs.Select((item, index) => ...)` |
| `zip(a, b)` | `# C#: a.Zip(b, (x, y) => ...)` |
| `f"{x=}, {y=}"` | `# C#: $"x={x}, y={y}"` |
| `*args` / `**kwargs` | `# C#: params T[] args / 字典传参（C# 无直接等价物）` |
| `@staticmethod` / `@classmethod` | `# C#: static 方法` |
| `None` | `# C#: null` |
| `not x` | `# C#: !x` |
| `x is None` | `# C#: x == null` |
| `x is not None` | `# C#: x != null` |
| `and` / `or` | `# C#: && / \|\|` |
| `True` / `False` | `# C#: true / false` |
| `def foo(x=10):` | `# C#: void Foo(int x = 10)` |

### 2. 类型对照（必须）

Python 类型标注旁边必须标注 C# 等价类型：

| Python 类型 | C# 等价 |
|-------------|---------|
| `int` | `int` / `long`（Python int 无限大） |
| `float` | `double` |
| `str` | `string` |
| `bool` | `bool` |
| `list[T]` | `List<T>` |
| `dict[K,V]` | `Dictionary<K,V>` |
| `tuple[X,Y]` | `(X, Y)` / `Tuple<X,Y>` |
| `set[T]` | `HashSet<T>` |
| `Optional[T]` / `T \| None` | `T?` |
| `Callable[[A,B], R]` | `Func<A, B, R>` |
| `Iterable[T]` | `IEnumerable<T>` |
| `Generator[T,None,None]` | `IEnumerator<T>` + `yield return` |

### 3. 标准库对照（按需）

Python 标准库函数标注 C# 等价物：

| Python | C# 等价 |
|--------|---------|
| `len(xs)` | `xs.Count` / `xs.Length` |
| `sorted(xs)` | `xs.OrderBy(x => x).ToList()` |
| `enumerate(xs)` | `xs.Select((x,i) => (x,i))` |
| `map(f, xs)` | `xs.Select(x => f(x))` |
| `filter(f, xs)` | `xs.Where(x => f(x))` |
| `sum(xs)` | `xs.Sum()` |
| `any(cond(x) for x in xs)` | `xs.Any(x => cond(x))` |
| `all(cond(x) for x in xs)` | `xs.All(x => cond(x))` |
| `min(xs)` / `max(xs)` | `xs.Min()` / `xs.Max()` |
| `range(n)` | `Enumerable.Range(0, n)` |
| `reversed(xs)` | `xs.Reverse()` |
| `str.split(s)` | `s.Split(...)` |
| `str.join(seq)` | `string.Join(sep, seq)` |
| `str.strip()` | `s.Trim()` |
| `str.lower()` / `str.upper()` | `s.ToLower()` / `s.ToUpper()` |
| `str.startswith(p)` | `s.StartsWith(p)` |
| `os.path.join(a, b)` | `Path.Combine(a, b)` |
| `Path(path)` | `new DirectoryInfo(path)` + `FileInfo` |

### 4. 注释位置

```python
# ✅ 正确 — 注释在代码同一行或紧邻上方
models = [Model(**m) for m in raw_models]  # C#: raw_models.Select(m => new Model(m)).ToList()

# ✅ 正确 — 复杂逻辑注释在上方
# C#: Dictionary<string, Model> modelMap = models.ToDictionary(m => m.Name);
model_map: dict = {m.name: m for m in models}

# ❌ 错误 — 不要只在文件头写一段总结，每行都要有对照
```

### 5. 不需要对照注释的情况

以下情况可以不标注 C# 等价物：
- `import` 语句本身（但导入的模块用法要标注）
- `pass` 语句
- 装饰器本身（但装饰器的效果要标注）
- 纯数学/业务逻辑表达式

## 示例输出

```python
"""计算模块 — 练习 Python 计算与集合操作。"""

# C#: using System.Text.Json;
import json
from pathlib import Path
from typing import List

# C#: using System.Collections.Generic;
# C#: public record Model(string Name, double InputPrice, double OutputPrice);
from dataclasses import dataclass


def load_config(path: str) -> dict:
    """读取 JSON 配置文件。"""
    # C#: if (!File.Exists(path)) throw new FileNotFoundException(...);
    if not Path(path).exists():  # C#: Path → new FileInfo(path)
        raise FileNotFoundError(f"配置文件不存在: {path}")

    # C#: using var stream = File.OpenRead(path);
    # C#: var data = JsonSerializer.Deserialize<Dictionary<string, object>>(stream);
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
```

## 两条铁律

1. **宁可多标注，不要漏标注** — 初学者不知道哪些是"重要的"对照，全部标出来
2. **注释用中文写 C# 对比** — 因为学习者母语是中文，C# 代码片段是英文
