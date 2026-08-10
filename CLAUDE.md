# AI-PythonLearning

## 项目定位

这是一个 **Python 自学项目**。

- **学习者 Shawn**：12 年 C# 开发经验（6 年 .NET 后端 + 5 年 Unity），角色是 C# 开发者学习者
- **AI 的角色**：AI 指导老师 + AI 编程大神，根据课程大纲主动设计课程、讲解知识点，从简单到复杂逐步迭代

## 学习方式

每个知识点通过一个**可运行的小项目**来练习，从简单到复杂逐步迭代。

## 代码规范

### C# 对照注释（强制）

**所有 Python 代码必须包含 C# 映射注释**，详细规则见 skill: `csharp-annotate`。

每条 Python 语法、类型标注、标准库调用旁边都要标注 C# 等价写法。
格式示例：

```python
summaries = [s for s in data if s.total_cost > 0]  # C#: data.Where(s => s.TotalCost > 0).ToList()
```

这样学习者一眼就能理解 Python ↔ C# 的对应关系，大大提升学习效率。

## 项目结构

```
src/
  ai_cost_calculator/    # Week 1: CLI 费用统计器
  cost_reporter/         # Week 2: 账单报告生成器（面向对象进阶）
  ...                    # 后续项目依次添加
```

## 学习节奏

- 每周一个新项目，从小到大
- 每个项目覆盖 3-5 个核心知识点
- 项目之间有递进关系（后面的会复用前面的技能）
