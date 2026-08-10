"""流式管道 —— 大日志文件费用分析（Week 3 实战项目）。

场景：生产环境每天产生几十万行 LLM 调用日志（JSONL 格式，一行一条），
内存无法一次性装下。用生成器搭一条"水管"：
  读行 → 解析 → 过滤 → 算费用 → 聚合
每一段都是惰性的：数据流过去就释放，内存占用 O(1)（与文件大小无关）。

C# 对照主线：
  这段代码 ≈ 用 IEnumerable<T> + yield return + LINQ 写同样功能：
    File.ReadLines(path)                       // 流式读行（.NET 自带惰性）
      .Select(JsonSerializer.Deserialize<CallRecord>)
      .Where(c => c.Model == model)
      .Select(c => (c, CalcCost(c, modelMap[c.Model])))
      .GroupBy(...).Select(...).OrderByDescending(...).Take(k)

与 Week 1/2 的关系：
  - 复用 Week 1 的 calculator（读配置、算单价）—— 类/管道做编排，纯函数做计算
  - 对比 Week 1：parse_calls 把全部记录装进 List；本周一次只处理一行
"""

import json  # C#: using System.Text.Json;
from itertools import islice, takewhile  # C#: Enumerable.Take / TakeWhile
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

try:
    # 场景 1: pytest（tests 从项目根目录导入，src 作为命名空间包）
    from src.ai_cost_calculator import calculator  # type: ignore
    from src.ai_cost_calculator.models import CallRecord, Model  # type: ignore
except ImportError:
    try:
        # 场景 2: 包已安装到 venv（uv run call-streamer）—— 从 site-packages 导入
        from ai_cost_calculator import calculator  # type: ignore[no-redef]
        from ai_cost_calculator.models import CallRecord, Model  # type: ignore[no-redef]
    except ImportError:
        raise RuntimeError(
            "call_streamer 依赖 Week 1 的 ai_cost_calculator，请通过 "
            "`uv run call-streamer ...` 或 pytest 运行"
        )

# 一条"带费用的调用记录"：原始记录 + 计算好的费用
# C#: (CallRecord Call, double Cost)  —— 用元组类型（.NET 7+ 的元组语法）
CostedCall = Tuple[CallRecord, float]

# 聚合结果：模型名 -> (调用次数, 总费用) —— C#: record ModelTotal(string Model, int Count, double Cost)
ModelTotal = Tuple[str, int, float]


# ============================================================
# 管道第 1 段：逐行读文件（惰性）
# ============================================================

def iter_lines(path: str) -> Iterator[str]:
    """逐行 yield 文件内容，不把整个文件读进内存。

    C#: File.ReadLines(path)  —— 注意是 ReadLines（惰性）不是 ReadAllLines（一次性）。
    with 语句保证读完后自动关闭文件 —— C#: using var reader = ...;
    与 Week 1 的 open(...).read() 对比：read() 会把整个文件装进内存。

    教学点：文件对象本身也是迭代器 —— for line in f 会逐行读取，
    这正是 Python 文件处理的惯用写法。
    """
    with open(path, "r", encoding="utf-8") as f:  # C#: using var reader = File.OpenText(path);
        for line in f:  # C#: while ((line = reader.ReadLine()) != null)
            yield line  # C#: yield return line;
    # 注意：with 结束时文件才真正关闭 —— 生成器被 for 循环消费完才走到这里。


# ============================================================
# 管道第 2 段：JSONL 行 → CallRecord 对象（逐行解析 + 容错）
# ============================================================

def parse_records(lines: Iterable[str]) -> Iterator[CallRecord]:
    """把文本行流解析成 CallRecord 对象流。

    坏行（JSON 解析失败）直接跳过 —— 生产环境日志里偶尔有脏数据，
    不能因为一行坏数据让整个统计挂掉。
    C#: lines.Select(line => JsonSerializer.Deserialize<CallRecord>(line))
            .Where(r => r != null)   // 反序列化失败返回 null，过滤掉
    """
    for line in lines:  # C#: foreach (var line in lines)
        try:
            data = json.loads(line)  # C#: JsonSerializer.Deserialize<Dictionary<string, object>>(line)
            # 字典解包构造 dataclass —— C#: new CallRecord { CallId = data["call_id"], ... }
            # 对比 Week 1 的 CallRecord(**c)：那时是"整个 dict 列表一起解析"，
            # 这里逐行解析 —— 数据流式经过，不堆积。
            yield CallRecord(**data)  # C#: yield return record;
        except (json.JSONDecodeError, TypeError, ValueError):
            # 坏行跳过 —— C#: 反序列化失败会抛 JsonException，catch 后 continue
            continue


# ============================================================
# 管道第 3 段：过滤（LINQ Where 的生成器版）
# ============================================================

def filter_by_model(
    records: Iterable[CallRecord], model: Optional[str]
) -> Iterator[CallRecord]:
    """按模型名过滤。model 为 None 时不过滤（全部通过）。

    C#: records.Where(c => c.Model == model)
    自己实现的原因：展示"LINQ Where 内部就是一个生成器" ——
    标准库的 filter() / 推导式也能做，但为了教学这里显式写一遍。
    """
    if model is None:  # C#: if (model == null)
        yield from records  # 不过滤 —— C#: foreach (var r in records) yield return r;
        return
    for record in records:  # C#: foreach (var record in records)
        if record.model == model:  # C#: if (record.Model == model)
            yield record  # C#: yield return record;


# ============================================================
# 管道第 4 段：附加费用（LINQ Select 的生成器版）
# ============================================================

def with_cost(
    records: Iterable[CallRecord], model_map: Dict[str, Model]
) -> Iterator[CostedCall]:
    """给每条记录算出费用，产出 (记录, 费用) 元组流。

    C#: records.Select(c => (c, Calculator.CalcCallCost(c, modelMap[c.Model])))
    复用 Week 1 的 calc_call_cost 纯函数 —— 不重复实现计费公式。

    教学点：生成器可以作为"转换节点"插在管道中间，
    上游是流、下游是流，自己只负责"逐个转换"。
    """
    for record in records:  # C#: foreach (var record in records)
        model = model_map[record.model]  # C#: var model = modelMap[record.Model];
        cost = calculator.calc_call_cost(record, model)  # 复用 Week 1 纯函数
        yield (record, cost)  # C#: yield return (record, cost);


# ============================================================
# 管道第 5 段：惰性截断工具（itertools 实战）
# ============================================================

def head(records: Iterable[CallRecord], n: int) -> Iterator[CallRecord]:
    """只取前 n 条 —— 用 itertools.islice。

    C#: records.Take(n)
    教学点：islice 是"短路"的 —— 取够 n 条就停，
    上游生成器被丢弃（垃圾回收），后面的行永远不会被读取。
    对无限流（generators.infinite_naturals）也能安全使用。
    """
    return islice(records, n)  # C#: records.Take(n)  —— 同样惰性


def while_model(records: Iterable[CallRecord], model: str) -> Iterator[CallRecord]:
    """一直取，直到遇到不属于该模型的记录就整体停止。

    C#: records.TakeWhile(c => c.Model == model)
    教学点：与 filter 的区别 —— TakeWhile 是"开头一段"，遇到不满足立刻短路；
    Where 是"全程筛选"。日志按模型分块写入时，TakeWhile 比 Where 快得多。
    """
    return takewhile(lambda r: r.model == model, records)  # C#: TakeWhile(c => c.Model == model)


# ============================================================
# 管道第 6 段：聚合 —— Top-K 模型（惰性流上做统计）
# ============================================================

def top_models(costed: Iterable[CostedCall], k: int) -> List[ModelTotal]:
    """在惰性流上按模型聚合费用，返回费用最高的前 k 个。

    算法（对比 LINQ）：
      1. 遍历流，用 dict 累加每个模型的 (次数, 费用) —— 流式，O(1) 内存
         C#: costed.GroupBy(c => c.Call.Model)
                   .Select(g => (g.Key, g.Count(), g.Sum(x => x.Cost)))
      2. 排序列出取前 k —— C#: .OrderByDescending(x => x.Cost).Take(k)
    内存只与"模型种类数"有关（几 KB），与日志总行数无关。

    进阶（面试点）：k 很大或流特别长时，可以用 heapq.nlargest 做 O(n log k)，
    这里 k 是模型数（个位数），直接排序即可 —— 简单优先。
    """
    totals: Dict[str, List[float]] = {}  # C#: var totals = new Dictionary<string, List<double>>();
    for record, cost in costed:  # C#: foreach (var (record, cost) in costed)
        bucket = totals.setdefault(  # C#: if (!totals.ContainsKey(m)) totals[m] = [0, 0];
            record.model, [0, 0.0]
        )  # setdefault：键不存在时放入默认值并返回 —— C#: 无直接等价，需 ContainsKey + 赋值
        bucket[0] += 1  # 次数
        bucket[1] += cost  # 费用

    # 转成 (模型名, 次数, 费用) 列表再排序 —— C#: totals.Select(kv => (kv.Key, ...))
    result = [
        (name, counts[0], counts[1]) for name, counts in totals.items()
    ]
    # 按费用降序取前 k —— C#: result.OrderByDescending(t => t.Cost).Take(k)
    result.sort(key=lambda t: t[2], reverse=True)  # C#: OrderByDescending(t => t.Cost)
    return result[:k]  # C#: .Take(k).ToList()


# ============================================================
# 管道终点：全局汇总（只累加，不建列表）
# ============================================================

def summarize(costed: Iterable[CostedCall]) -> Dict[str, float]:
    """流式汇总：总调用次数 / 总输入 token / 总输出 token / 总费用。

    返回 dict 而非类 —— 这是纯聚合的临时结果。
    C#: 遍历 IEnumerable 累加 4 个局部变量，最后返回一个对象。
    教学点：整个汇总过程从未把数据装进列表 —— 内存与日志行数无关。
    """
    total_calls = 0  # C#: var totalCalls = 0;
    total_in = 0  # C#: var totalIn = 0L;
    total_out = 0  # C#: var totalOut = 0L;
    total_cost = 0.0  # C#: var totalCost = 0d;
    for record, cost in costed:  # C#: foreach (var (record, cost) in costed)
        total_calls += 1  # C#: totalCalls++;
        total_in += record.input_tokens  # C#: totalIn += record.InputTokens;
        total_out += record.output_tokens
        total_cost += cost
    return {
        "calls": total_calls,
        "input_tokens": total_in,
        "output_tokens": total_out,
        "total_cost": total_cost,
    }


def load_model_map(config_path: str) -> Dict[str, Model]:
    """读取价格配置，构建 模型名 → Model 的查找表（复用 Week 1）。

    C#: config.Models.ToDictionary(m => m.Name)
    """
    data = calculator.load_config(config_path)  # 复用 Week 1：读 JSON + 校验结构
    return {m.name: m for m in calculator.parse_models(data["models"])}


def analyze_log(
    log_path: str,
    config_path: str,
    model_filter: Optional[str] = None,
    top_k: int = 3,
) -> Tuple[Dict[str, float], List[ModelTotal]]:
    """完整管道入口：一行调出 (汇总, Top-K) 两个结果。

    管道全貌（对比 C# 的 LINQ 链）：
      iter_lines → parse_records → filter_by_model → with_cost
      ↓ 分两路
      summarize（全量汇总） / top_models（Top-K）
    每一段都是惰性生成器，日志多大都不占内存 ——
    C#: 同样的设计用 IEnumerable<T> 实现，本质完全相同。

    教学点 —— 生成器是一次性的（single-use）：
    同一个生成器流只能消费一次（C#: 同一个 IEnumerable 通常也只能枚举一次）。
    要出两个统计结果，就**重新搭一遍管道**（文件可以重新读）——
    而不是把流物化成列表（list(costed) 会打破 O(1) 内存）。
    """
    model_map = load_model_map(config_path)

    # 搭管道（此刻什么都没执行！）—— C#: File.ReadLines().Select().Where().Select()
    def build_pipeline() -> Iterable[CostedCall]:
        """重新构建完整的惰性管道（每次调用都从头读文件）。"""
        lines = iter_lines(log_path)  # C#: File.ReadLines(path)
        records = parse_records(lines)  # C#: .Select(Deserialize)
        records = filter_by_model(records, model_filter)  # C#: .Where(...)
        return with_cost(records, model_map)  # C#: .Select(c => (c, cost))

    # 第一遍：全量汇总（真正的流式，O(1) 内存）
    summary = summarize(build_pipeline())

    # 第二遍：Top-K（重新搭管道 —— 文件重新读一遍）
    # C#: 等效做法 —— 两段 LINQ 链各自 .ReadLines() 一次，或把结果缓存起来
    tops = top_models(build_pipeline(), top_k)

    return summary, tops
