"""Week 3 测试 —— 生成器与迭代器。

测试设计的教学点：
  1. 惰性求值的"证明" —— 用副作用计数、无限序列 + islice 短路来验证
     （急切实现会死循环/立刻抛错，能跑通就是惰性的证据）
  2. 管道正确性 —— 每个节点单独测，再端到端对比暴力实现
  3. 生成器一次性 —— 同一个流只能消费一次（C#: IEnumerable 同样适用）

fixture 复用：conftest.py 的 temp_config_file（Week 1 引入，跨周复用）。
"""

import json  # C#: using System.Text.Json;
from itertools import islice  # C#: Enumerable.Take

import pytest  # C#: using Xunit;

try:
    from src.call_streamer import generators  # type: ignore
    from src.call_streamer import pipeline as pl  # type: ignore
    from src.ai_cost_calculator.models import CallRecord, Model  # type: ignore
except ImportError:
    from call_streamer import generators  # type: ignore[no-redef]
    from call_streamer import pipeline as pl  # type: ignore[no-redef]
    from ai_cost_calculator.models import CallRecord, Model  # type: ignore[no-redef]


# ============================================================
# 知识点 1-2：迭代协议 + 生成器函数
# ============================================================

class TestIterationProtocol:
    """手写迭代器（__iter__/__next__）的行为。

    C#: 对应 IEnumerator<int> —— MoveNext() + Current 的测试。
    """

    def test_for_loop_consumes_all(self) -> None:
        # C#: foreach (var x in new RangeUpTo(3)) 收集到列表
        assert list(generators.RangeUpTo(3)) == [0, 1, 2]

    def test_empty_range_raises_stop_iteration(self) -> None:
        # C#: enumerator.MoveNext() 立即返回 false（迭代器为空）
        it = iter(generators.RangeUpTo(0))  # C#: var it = range.GetEnumerator();
        with pytest.raises(StopIteration):  # C#: Assert.False(enumerator.MoveNext())
            next(it)

    def test_next_steps_one_by_one(self) -> None:
        # C#: 手动 MoveNext() + Current 三次
        it = iter(generators.RangeUpTo(2))
        assert next(it) == 0  # C#: it.MoveNext(); Assert.Equal(0, it.Current);
        assert next(it) == 1
        with pytest.raises(StopIteration):  # 第三次 → 结束
            next(it)


class TestGeneratorFunctions:
    """生成器函数（yield）的行为。C#: 迭代器方法（yield return）。"""

    def test_count_up_to(self) -> None:
        # C#: CountUpTo(5).ToList()  ==  [0, 1, 2, 3, 4]
        assert list(generators.count_up_to(5)) == [0, 1, 2, 3, 4]

    def test_count_up_to_zero_is_empty(self) -> None:
        assert list(generators.count_up_to(0)) == []

    def test_generator_object_vs_function(self) -> None:
        """调用生成器函数返回的是生成器对象，不是列表。"""
        gen = generators.count_up_to(3)
        # C#: CountUpTo(3) 返回 IEnumerable<int>（惰性），不是 List
        assert hasattr(gen, "__next__")  # 是迭代器（C#: 是 IEnumerator）
        assert not isinstance(gen, list)  # 不是列表（C#: 不是 List<int>）

    def test_function_body_not_executed_until_consumed(self) -> None:
        """惰性求值的直接证明：函数体在 next() 之前完全不执行。

        教学点：这是生成器与普通函数最本质的区别。
        C#: 含 yield return 的方法体在 foreach 之前不执行。
        """
        executed = []  # C#: var executed = new List<int>();

        def traced(n: int):  # C#: IEnumerable<int> Traced(int n)
            for i in range(n):
                executed.append(i)
                yield i

        gen = traced(3)  # 调用：函数体 0 行执行
        assert executed == []  # ← 证明惰性
        next(gen)  # 推进一次：执行到第一个 yield
        assert executed == [0]
        list(gen)  # 消费完
        assert executed == [0, 1, 2]


# ============================================================
# 知识点 3：无限序列 —— 只有惰性才可能
# ============================================================

class TestInfiniteSequences:
    """无限生成器 + islice 截断。

    这个测试本身就是惰性的"铁证"：
    如果生成器是急切的（先算出全部再返回），list 会永远跑不完；
    能 0.1 秒跑完，就说明"要多少生产多少"。
    C#: while(true) yield return n++  +  .Take(5)  —— 同样成立。
    """

    def test_islice_takes_first_n_of_infinite(self) -> None:
        # C#: InfiniteNaturals().Take(5).ToList()
        assert list(islice(generators.infinite_naturals(), 5)) == [0, 1, 2, 3, 4]

    def test_islice_with_start_offset(self) -> None:
        # C#: InfiniteNaturals().Skip(10).Take(3)  —— 注意 Python 用 slice 语法 (10, 13)
        assert list(islice(generators.infinite_naturals(), 10, 13)) == [10, 11, 12]


# ============================================================
# 知识点 4-6：生成器表达式 / yield from / next 默认值
# ============================================================

class TestGenexpAndDelegation:
    def test_genexp_is_lazy_listcomp_is_eager(self) -> None:
        """生成器表达式 vs 列表推导式的求值时机对比。"""
        calls = {"list": 0, "gen": 0}

        def track(key: str, x: int) -> int:
            calls[key] += 1
            return x

        nums = range(4)  # C#: Enumerable.Range(0, 4)（本身惰性）

        eager = [track("list", x) for x in nums]  # C#: .Select(...).ToList() —— 立即执行 4 次
        lazy = (track("gen", x) for x in nums)  # C#: .Select(...) —— 0 次执行

        assert calls["list"] == 4
        assert calls["gen"] == 0  # ← 惰性证据

        next(lazy)  # 消费 1 个 → 才执行 1 次
        assert calls["gen"] == 1

    def test_flatten_lists_with_yield_from(self) -> None:
        # C#: 手写嵌套 foreach + yield return
        assert list(generators.flatten_lists([[1, 2], [3], [4, 5, 6]])) == [
            1, 2, 3, 4, 5, 6,
        ]

    def test_yield_from_then_continue(self) -> None:
        # 委托结束后还能继续 yield 自己的元素 —— C#: 同理
        assert list(generators.countdown(3)) == [0, 1, 2, -1]

    def test_next_with_default(self) -> None:
        # C#: enumerator.MoveNext() ? enumerator.Current : defaultValue
        assert generators.first_or(iter([7, 8]), 0) == 7  # 有元素取第一个
        assert generators.first_or(iter([]), 0) == 0  # 空流用默认值


# ============================================================
# 管道节点：逐行读 / 解析 / 过滤 / 计费
# ============================================================

class TestPipeStages:
    """每个管道节点独立测试 —— 对比 C# 对 LINQ 链式节点的单测。"""

    def test_iter_lines_is_lazy(self, tmp_path) -> None:
        """iter_lines 惰性证明：文件不存在时，调用本身不抛错。

        只有消费（next / list）时才真正打开文件 → 才抛 FileNotFoundError。
        C#: File.ReadLines(不存在路径) 的调用时机同理 —— 枚举时才抛。
        """
        missing = str(tmp_path / "not_exist.jsonl")
        lines = pl.iter_lines(missing)  # 调用：不抛错（惰性）
        with pytest.raises(FileNotFoundError):  # C#: 枚举时才抛 FileNotFoundException
            list(lines)

    def test_iter_lines_reads_line_by_line(self, tmp_path) -> None:
        log = tmp_path / "calls.jsonl"
        log.write_text("a\nb\nc\n", encoding="utf-8")
        assert list(pl.iter_lines(str(log))) == ["a\n", "b\n", "c\n"]

    def test_parse_records_skips_bad_lines(self, tmp_path) -> None:
        """坏行跳过 —— 生产环境日志混入脏数据时不崩溃。

        C#: Deserialize 失败 catch 后 continue（或返回 null 过滤）。
        """
        log = tmp_path / "calls.jsonl"
        good = json.dumps({"call_id": 1, "model": "m", "input_tokens": 10, "output_tokens": 5})
        log.write_text(
            f"{good}\nnot-json-at-all\n{good}\n"  # 中间一行是坏数据
            + '{"call_id": 2}\n',  # 缺字段也算坏行
            encoding="utf-8",
        )
        records = list(pl.parse_records(pl.iter_lines(str(log))))
        assert len(records) == 2
        assert records[0].call_id == 1
        assert records[1].call_id == 1

    def test_filter_by_model(self, tmp_path) -> None:
        """过滤节点 —— C#: Where(c => c.Model == model)。"""
        lines = [
            json.dumps(r)
            for r in [
                {"call_id": 1, "model": "a", "input_tokens": 1, "output_tokens": 1},
                {"call_id": 2, "model": "b", "input_tokens": 1, "output_tokens": 1},
                {"call_id": 3, "model": "a", "input_tokens": 1, "output_tokens": 1},
            ]
        ]
        records = pl.parse_records(iter(lines))
        filtered = list(pl.filter_by_model(records, "a"))
        assert [r.call_id for r in filtered] == [1, 3]

    def test_filter_by_model_none_passes_all(self) -> None:
        records = pl.parse_records(
            iter(['{"call_id": 1, "model": "a", "input_tokens": 1, "output_tokens": 1}'])
        )
        assert len(list(pl.filter_by_model(records, None))) == 1

    def test_takewhile_stops_at_first_mismatch(self) -> None:
        """TakeWhile vs Where 的区别：遇不满足立即短路。"""
        lines = [
            '{"call_id": %d, "model": "%s", "input_tokens": 1, "output_tokens": 1}' % (i, m)
            for i, m in [(1, "a"), (2, "a"), (3, "b"), (4, "a")]
        ]
        records = pl.parse_records(iter(lines))
        assert [r.call_id for r in pl.while_model(records, "a")] == [1, 2]
        # 注意：与 Where 不同 —— 第 4 条虽然是 "a"，但 TakeWhile 已短路，不包含


class TestCosting:
    """计费节点 —— 复用 Week 1 的纯函数，验证费用计算一致。"""

    def test_with_cost_matches_week1_formula(self, temp_config_file) -> None:
        """费用结果与 Week 1 的 calc_call_cost 逐条一致。

        temp_config_file 来自 conftest.py（模型 test-model: 1.0 / 4.0 元）。
        """
        model_map = pl.load_model_map(temp_config_file)  # 复用 Week 1 的读取逻辑

        lines = [
            '{"call_id": 1, "model": "test-model", "input_tokens": 100, "output_tokens": 50}',
            '{"call_id": 2, "model": "test-model", "input_tokens": 200, "output_tokens": 100}',
        ]
        costed = list(pl.with_cost(pl.parse_records(iter(lines)), model_map))

        # 手算：100/1e6*1.0 + 50/1e6*4.0 = 0.0001 + 0.0002 = 0.0003
        assert costed[0][1] == pytest.approx(0.0003)
        assert costed[1][1] == pytest.approx(0.0006)


# ============================================================
# 聚合：Top-K / 汇总 / 端到端
# ============================================================

class TestAggregation:
    def test_top_models_orders_by_cost(self, temp_config_file) -> None:
        """Top-K 与暴力实现（dict 聚合 + 排序）结果一致。"""
        model_map = pl.load_model_map(temp_config_file)
        lines = [
            '{"call_id": 1, "model": "test-model", "input_tokens": 1000, "output_tokens": 500}',
        ] * 10  # 10 条相同记录
        costed = pl.with_cost(pl.parse_records(iter(lines)), model_map)

        tops = pl.top_models(costed, k=5)
        # 单条费用 0.003 元 → 10 条 = 0.03 元
        assert tops == [("test-model", 10, pytest.approx(0.03))]

    def test_top_models_with_multiple_models(self) -> None:
        """多模型时按费用降序 —— C#: OrderByDescending(c => c.Cost).Take(k)。"""
        # 直接构造 Model 对象（dataclass —— C#: new Model(...)）
        model_map = {
            "cheap": Model(name="cheap", input_price_per_1m=1.0, output_price_per_1m=1.0),
            "expensive": Model(name="expensive", input_price_per_1m=10.0, output_price_per_1m=10.0),
        }
        # cheap: 10000/1e6*1.0 + 10000/1e6*1.0 = 0.02 元
        # expensive: 5000/1e6*10.0 + 5000/1e6*10.0 = 0.10 元 → 应排第一
        lines = [
            '{"call_id": 1, "model": "cheap", "input_tokens": 10000, "output_tokens": 10000}',
            '{"call_id": 2, "model": "expensive", "input_tokens": 5000, "output_tokens": 5000}',
        ]
        costed = pl.with_cost(pl.parse_records(iter(lines)), model_map)
        tops = pl.top_models(costed, k=2)
        assert [t[0] for t in tops] == ["expensive", "cheap"]

    def test_top_k_limits_results(self) -> None:
        """k 参数截断结果数量 —— C#: .Take(k).ToList()。"""
        costed = [
            (CallRecord(call_id=i, model=f"m{i}", input_tokens=1, output_tokens=1), float(i))
            for i in range(5)
        ]
        tops = pl.top_models(costed, k=2)
        assert len(tops) == 2
        # 费用最高的两个模型（4.0 和 3.0）
        assert [t[0] for t in tops] == ["m4", "m3"]

    def test_summarize_aggregates_stream(self, temp_config_file) -> None:
        """汇总与暴力遍历结果一致。"""
        model_map = pl.load_model_map(temp_config_file)
        lines = [
            '{"call_id": 1, "model": "test-model", "input_tokens": 100, "output_tokens": 50}',
            '{"call_id": 2, "model": "test-model", "input_tokens": 200, "output_tokens": 100}',
        ]
        costed = pl.with_cost(pl.parse_records(iter(lines)), model_map)
        s = pl.summarize(costed)
        assert s["calls"] == 2
        assert s["input_tokens"] == 300
        assert s["output_tokens"] == 150
        assert s["total_cost"] == pytest.approx(0.0009)  # 0.0003 + 0.0006


class TestStreamingSemantics:
    """流式语义：一次性消费 + 大文件不物化。"""

    def test_generator_is_single_use(self) -> None:
        """同一个生成器只能消费一次 —— 第二次消费到空。

        C#: 同一个 IEnumerable 迭代器对象同样只能枚举一次
        （这也是 analyze_log 里"重新搭管道"的原因）。
        """
        gen = pl.parse_records(
            iter(['{"call_id": 1, "model": "a", "input_tokens": 1, "output_tokens": 1}'])
        )
        assert len(list(gen)) == 1
        assert list(gen) == []  # ← 已耗尽（C#: 再 foreach 不会有元素）

    def test_analyze_log_end_to_end(self, temp_config_file, tmp_path) -> None:
        """端到端：临时 JSONL → analyze_log → 结果与手工计算一致。"""
        log = tmp_path / "calls.jsonl"
        lines = [
            {"call_id": 1, "model": "test-model", "input_tokens": 100, "output_tokens": 50},
            {"call_id": 2, "model": "test-model", "input_tokens": 200, "output_tokens": 100},
            "garbage-line",  # 坏行应被跳过
        ]
        log.write_text(
            "\n".join(
                l if isinstance(l, str) else json.dumps(l) for l in lines
            ),
            encoding="utf-8",
        )
        summary, tops = pl.analyze_log(
            str(log), temp_config_file, model_filter=None, top_k=3
        )
        assert summary["calls"] == 2  # 坏行被跳过
        assert summary["total_cost"] == pytest.approx(0.0009)
        assert tops == [("test-model", 2, pytest.approx(0.0009))]

    def test_analyze_log_model_filter(self, temp_config_file, tmp_path) -> None:
        log = tmp_path / "calls.jsonl"
        log.write_text(
            "\n".join(
                json.dumps(r)
                for r in [
                    {"call_id": 1, "model": "test-model", "input_tokens": 100, "output_tokens": 50},
                    {"call_id": 2, "model": "other", "input_tokens": 100, "output_tokens": 50},
                ]
            ),
            encoding="utf-8",
        )
        # 过滤 unknown 模型时，费用算 0（Week 1 行为）—— 这里只测过滤数量
        summary, _ = pl.analyze_log(str(log), temp_config_file, model_filter="test-model")
        assert summary["calls"] == 1

    def test_stream_processes_large_file_without_blowing_up(self, temp_config_file, tmp_path) -> None:
        """5 万行日志流式处理：正确 + 快。

        教学点：如果实现是"先把所有行读进内存"（W1 的做法），
        也能通过，但内存 O(n)；生成器实现内存 O(1)。
        速度验证的是"按需生产"而非"全量计算"。
        """
        log = tmp_path / "big.jsonl"
        record = {"model": "test-model", "input_tokens": 100, "output_tokens": 50}
        with open(log, "w", encoding="utf-8") as f:
            for i in range(50_000):
                record["call_id"] = i
                f.write(json.dumps(record) + "\n")

        summary, tops = pl.analyze_log(str(log), temp_config_file, top_k=1)
        assert summary["calls"] == 50_000
        # 单条 0.0003 元 → 5 万条 = 15.0 元
        assert summary["total_cost"] == pytest.approx(15.0)
        assert tops[0][1] == 50_000
