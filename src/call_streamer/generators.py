"""生成器与迭代器 —— Week 3 知识点教学模块。

本文件不是"项目功能"，而是**课程本身**：每个函数演示一个知识点。
在项目代码里，真正用到这些概念的是 pipeline.py（大日志流分析）。

========================================================================
本周主线（对照表）
========================================================================
  Python                                        C# 等价
  ------------------------------------------    --------------------------
  迭代协议 __iter__ / __next__ / StopIteration  IEnumerable<T> / IEnumerator<T>
  for x in g                                    foreach (var x in g)
  next(g)                                       enumerator.MoveNext() + Current
  生成器函数（函数体含 yield）                  C# 迭代器方法（含 yield return）
  生成器表达式 (x for x in xs)                  LINQ 惰性查询（不 ToList() 时）
  yield from sub                               foreach (var x in sub) yield return x;
  惰性求值（用到才执行）                        LINQ 的延迟执行（deferred execution）
========================================================================

最重要的一句话：**惰性（lazy）**。
Python 生成器和 C# LINQ 都是"先搭管道、后放水"：
构建管道时什么都不算，只有 foreach / for 消费时才逐个求值。
这正是后面 Week 5 做 LLM 流式输出（SSE）的核心机制。
"""

from typing import Iterator, List


# ============================================================
# 知识点 1：迭代协议 —— Python 里"可迭代"到底是什么
# ============================================================
# 任何对象，只要实现 __iter__（返回迭代器），就是"可迭代的"（Iterable）；
# 迭代器要实现 __next__（返回下一个元素，没有就抛 StopIteration）。
# C# 对应：IEnumerable<T>（可迭代）+ IEnumerator<T>（迭代器）。
#
# 对照 C# 手写迭代器：
#   C#: public class RangeUpTo : IEnumerable<int>
#       {
#           public IEnumerator<int> GetEnumerator() => new Enumerator(...);
#           class Enumerator : IEnumerator<int>
#           {
#               public bool MoveNext() { ... }
#               public int Current => value;
#           }
#       }
# Python 把 "两个接口 + MoveNext + Current" 压缩成了 2 个方法。

class RangeUpTo:
    """模仿内置 range() 的手写迭代器：从 0 数到 n-1。

    C#: 自实现 IEnumerable<int>（循环语法 for x in obj 的前提）
    """

    def __init__(self, n: int) -> None:  # C#: public RangeUpTo(int n)
        self._n = n  # C#: this.n = n;
        self._current = 0  # C#: 相当于 Enumerator 内部的 current 字段

    def __iter__(self) -> "RangeUpTo":
        """返回迭代器 —— 每次 for 循环开始时被调用一次。

        C#: GetEnumerator()。注意：这里返回 self（自己就是迭代器），
        因为迭代状态（_current）就存在自己身上。
        更严谨的做法是返回独立的迭代器对象（可多次迭代），
        这里简化为一次性的 —— 与 C# IEnumerator 语义一致。
        """
        return self  # C#: return this;

    def __next__(self) -> int:
        """返回下一个元素；没有更多元素时抛 StopIteration。

        C#: bool MoveNext() { ... } + int Current { get; }
        Python 把 MoveNext 和 Current 合并成一个方法：
        - C# 的 MoveNext 返回 false 表示结束
        - Python 的 __next__ 用"抛异常"表示结束（StopIteration）
        这是两种语言的设计差异：异常在 Python 里是正常的控制流。
        """
        if self._current >= self._n:  # C#: if (current >= n) return false;
            # 抛异常表示迭代结束 —— C#: throw new StopIterationException();
            # （.NET 里迭代器结束是正常返回，Python 用异常，本质相同）
            raise StopIteration
        result = self._current  # C#: Current => current;
        self._current += 1  # C#: current++;
        return result


def demo_for_loop_mechanics() -> None:
    """揭示 for 循环的底层机制（教学用）。

    for x in obj 其实等价于下面三行：
        1. it = iter(obj)          —— 调 obj.__iter__() 拿到迭代器
        2. 反复调 next(it)         —— 调 it.__next__() 拿下一个元素
        3. 捕获 StopIteration 就退出循环

    C#: foreach 编译后也是"GetEnumerator → while(MoveNext) { Current }"，
    和 Python 完全同构 —— 只是 C# 编译器帮你写好了，Python 也是。
    """
    it = iter(RangeUpTo(3))  # C#: var enumerator = range.GetEnumerator();
    while True:
        try:
            x = next(it)  # C#: enumerator.MoveNext() ? enumerator.Current : break
            print(x)
        except StopIteration:  # C#: 没有这个写法 —— MoveNext() 返回 false 就 break
            break


# ============================================================
# 知识点 2：生成器函数 —— 用 yield 替代手写迭代器
# ============================================================
# 手写 __iter__/__next__ 太啰嗦。只要函数体里出现 yield，
# Python 就自动把这个函数变成"生成器函数"：
#   - 调用它不会执行函数体，而是返回一个生成器对象（自动实现迭代协议）
#   - 每次 next() 从上次暂停处继续执行，直到下一个 yield
#   - 函数结束（或 return）时自动抛 StopIteration
#
# C#: 完全等价 —— 含 yield return 的方法是迭代器方法，
# 编译器自动生成状态机类。两者都是"编译器帮你写状态机"。
#
# 关键：函数体是**暂停/恢复**的，局部变量在暂停期间被保存 ——
# 这就是状态机（C# 编译器生成 MoveNext() 状态机，原理一模一样）。

def count_up_to(n: int) -> Iterator[int]:
    """从 0 数到 n-1 的生成器。C#: IEnumerable<int> CountUpTo(int n)

    演示生成器的执行流程：
      next() 第 1 次：执行到 yield 0，暂停，返回 0
      next() 第 2 次：从暂停处继续，执行到 yield 1，暂停，返回 1
      ...直到函数自然结束 → 抛 StopIteration（for 循环正常退出）
    """
    i = 0  # C#: var i = 0;
    while i < n:  # C#: while (i < n)
        yield i  # C#: yield return i;
        i += 1  # C#: i++;


def demonstrate_laziness() -> List[int]:
    """用副作用证明"调用函数时，函数体根本没执行"（惰性求值）。

    对比实验：
      普通函数调用 → 函数体立即执行（急切）
      生成器函数调用 → 只创建生成器对象，函数体 0 行都没跑（惰性）
    直到 next() 或 for 循环消费时，函数体才开始执行。

    C#: 同理 —— CountUpTo(n) 调用时方法体不执行，
    只有 foreach 时才执行（LINQ 的延迟执行）。
    """
    executed: List[int] = []  # C#: var executed = new List<int>();

    def traced(n: int) -> Iterator[int]:  # C#: IEnumerable<int> Traced(int n)
        """每次被推进时往 executed 里记一笔 —— 观察执行时机。"""
        for i in range(n):  # C#: for (var i = 0; i < n; i++)
            executed.append(i)  # C#: executed.Add(i);
            yield i  # C#: yield return i;

    gen = traced(3)  # ← 调用时刻：executed 还是空的（函数体没跑）
    assert executed == []  # ← 关键证明：惰性，什么都没发生

    first = next(gen)  # ← 第一次 next()：函数体跑到第一个 yield
    assert first == 0
    assert executed == [0]  # ← 只执行了"第一个 yield 之前"的代码

    for _ in gen:  # 消费剩余（此时 executed 已有 0，接着追加 1、2）
        pass
    assert executed == [0, 1, 2]  # ← 全部消费完，函数体才完整执行
    return executed


# ============================================================
# 知识点 3：无限序列 —— 惰性让"无穷"成为可能
# ============================================================
# C# 里无法用 List<int> 表示无限序列，但 IEnumerable<int> 可以
# （while(true) yield return n++; 完全合法）。
# Python 同理：生成器是"按需生产"，生产一个、消费一个，永不落地。

def infinite_naturals(start: int = 0) -> Iterator[int]:
    """自然数无限序列。C#: IEnumerable<int> InfiniteNaturals(int start = 0)

    永远生产，不停。配合 islice / takewhile 取前 N 个 ——
    如果先 ToList() 再 Take()，程序会永远跑不完（内存爆掉）。
    这是"先搭管道、后放水"最极端的例子。
    """
    n = start  # C#: var n = start;
    while True:  # C#: while (true)
        yield n  # C#: yield return n;
        n += 1


# ============================================================
# 知识点 4：生成器表达式（genexp）—— 惰性版列表推导式
# ============================================================
# 列表推导式 [x for x in xs]       → 立即生成完整列表（急切）
# 生成器表达式 (x for x in xs)     → 惰性流（不占内存）
# C# 对照：
#   列表推导式  ==  xs.Select(...).Where(...).ToList()
#   生成器表达式 ==  xs.Select(...).Where(...)    （不 ToList！）
# 区别就在最后有没有 ToList() —— C# 开发者对"忘写 ToList 导致延迟执行"应该很熟。

def genexp_vs_listcomp(n: int) -> tuple[int, int]:
    """对比两种写法，用副作用证明求值时机不同。C#: (int, int) 元组返回值

    返回 (列表推导式执行了几次, 生成器表达式执行了几次)。
    """
    counter = {"list": 0, "gen": 0}  # C#: var counter = new Dictionary<string, int>();

    def track(key: str, x: int) -> int:  # C#: int Track(string key, int x)
        counter[key] += 1  # C#: counter[key]++;
        return x

    nums = range(n)  # C#: Enumerable.Range(0, n)  （本身也是惰性的）

    eager = [track("list", x * 2) for x in nums]  # C#: nums.Select(x => Track("list", x*2)).ToList()
    # ↑ 列表推导式：立即把 n 个元素全部算完（执行了 n 次 track）

    lazy = (track("gen", x * 2) for x in nums)  # C#: nums.Select(x => Track("gen", x*2))  // 不 ToList()
    # ↑ 生成器表达式：只是搭了管道，一次都没执行 track！

    assert counter["list"] == n  # ← 急切的证据
    assert counter["gen"] == 0  # ← 惰性的证据：0 次！

    next(lazy)  # 消费第一个元素，才执行第 1 次 track
    assert counter["gen"] == 1  # ← 用到才执行
    return (counter["list"], counter["gen"])


# ============================================================
# 知识点 5：yield from —— 生成器委托
# ============================================================
# yield from sub_gen 等价于：for x in sub_gen: yield x
# 作用：把当前生成器"委托"给子生成器，子生成器生产完再回来继续。
# 适合：把多个来源的流"拼接"成一个流（C# 没有直接关键字，
# 只能手写 foreach (var x in sub) yield return x;）。

def flatten_lists(lists: List[List[int]]) -> Iterator[int]:
    """把列表的列表展平成单层流。C#: IEnumerable<int> Flatten(List<List<int>> lists)

    用 yield from 遍历每个子列表：
      C#: foreach (var list in lists)
              foreach (var x in list)
                  yield return x;
    Python 的 yield from 就是上面嵌套循环的简写。
    """
    for sub in lists:  # C#: foreach (var list in lists)
        yield from sub  # C#: foreach (var x in list) yield return x;
        # ↑ 把 sub 的所有元素依次"移交"出去，全部移交完才回到外层循环


def countdown(n: int) -> Iterator[int]:
    """倒计时生成器 —— 演示"yield from 之后还能继续 yield"。

    C#: 同样可以 foreach yield 之后再 yield return 自己的元素。
    """
    yield from count_up_to(n)  # 先委托：0, 1, ..., n-1
    yield -1  # 再自己生产一个：委托结束后继续执行（C#: 同理）


# ============================================================
# 知识点 6：next() 的默认值参数 —— 流的"取一帧"
# ============================================================
# next(g)            没有下一个 → 抛 StopIteration（C#: MoveNext() 返回 false）
# next(g, default)   没有下一个 → 返回 default，不抛异常
# 实际场景：读取流的第一行，如果为空流给出默认值 —— C#: TryGetFirst() 封装。

def first_or(gen: Iterator[int], default: int) -> int:
    """取流的第一个元素，空流返回默认值。

    C#: 没有直接等价 —— 需要自己写 if (enumerator.MoveNext()) return Current;
    Python 的 next(g, default) 一个调用搞定。
    """
    return next(gen, default)  # C#: enumerator.MoveNext() ? enumerator.Current : default


if __name__ == "__main__":
    # 直接运行时演示（C#: Main() 入口）
    demo_for_loop_mechanics()
    print("惰性演示:", demonstrate_laziness())
    print("前 3 个自然数:", list(count_up_to(3)))
