"""切片策略对比实验 —— 3 种策略 × 10 道金标问题 × top-3 命中率（rag-chunk-compare）。

C# 对照主线：
  本工具 ≈ bench.py 同款 A/B 对比实验骨架（公平性声明 / 5 次平均 / 对比表 / 面试话术）：
    固定语料 + 共享预处理 → 每策略独立跑 → 命中矩阵 + 结论

实验设计（本周「面试弹药」，README 有完整记录）：
  1. 语料：data/samples/ 下 2 份 PDF + 2 份 Word 的**解析文本**（整个链路被实验驱动）
  2. 金标判定：10 道问题（golden_qa.py），命中 = 答案短语（空白归一化）∈ 任一 top-3 切片
  3. 公平性：同一语料 / 同一 Embedding 模型（BgeSmallZh 单实例）/ 同一判定口径
     —— 只有切片策略不同，各策略取「自然默认参数」
  4. 命中矩阵（10×3）比命中率数字更有教学价值：能看出哪类问题在哪策略下翻车

运行：uv run rag-chunk-compare [--samples-dir ...] [--chunk-size 300] ...
"""

import argparse  # C#: 命令行参数解析
import tempfile  # C#: System.IO（临时目录，用后自动清理）
import time  # C#: Stopwatch
from pathlib import Path  # C#: System.IO

from rag_core.chunking import STRATEGIES, summarize  # C#: 策略注册表 + 统计
from rag_core.embeddings import BgeSmallZh  # C#: 中文 Embedding 模型
from rag_core.golden_qa import GOLDEN_QA, normalize  # C#: 金标问答 + 空白归一化
from rag_core.parsers import ParsedDocument, parse_file  # C#: 解析分发器
from rag_core.vector_store import VectorStore  # C#: 仓储类（ChromaDB 封装）

DEFAULT_SAMPLES_DIR = Path(__file__).parent / "data" / "samples"  # C#: make_samples 输出目录
STRATEGY_COLLECTIONS = {"fixed": "chunk_fixed", "recursive": "chunk_recursive", "semantic": "chunk_semantic"}


def load_corpus(samples_dir: Path) -> list[ParsedDocument]:
    """解析语料：samples/ 下 2 份 PDF + 2 份 Word（走 parse_file，实验驱动全链路）。

    C#: 语料加载 —— foreach 目录文件调用 ParseFile
    """
    docs: list[ParsedDocument] = []
    for path in sorted(samples_dir.glob("*.pdf")) + sorted(samples_dir.glob("*.docx")):
        docs.append(parse_file(path))
    return docs


def run_strategy(
    strategy: str,
    corpus: list[ParsedDocument],
    chunk_kwargs: dict,
    embedder: BgeSmallZh,
    work_dir: Path,
    top_k: int,
    rounds: int,
) -> dict:
    """单策略完整跑：切片 → 入库 → 10 问 × rounds 轮检索，返回统计 + 命中情况。

    C#: RunStrategy(strategy, corpus, options, embedder, workDir, topK, rounds)
        —— 独立临时目录 + 独立集合，策略之间零共享（隔离性）
    """
    t_chunk = time.perf_counter()
    all_chunks = []
    for doc in corpus:
        source = f"{Path(doc.source).stem} ({doc.format})"  # C#: 来源标签（命中时显示）
        all_chunks.extend(STRATEGIES[strategy](doc.text, source=source, **chunk_kwargs))
    chunk_secs = time.perf_counter() - t_chunk

    # 相同内容去重：语料是「PDF + Word 双份内容」，同一段文字被切出两份完全相同的
    # 切片，top-k 会被重复项挤占（Q05 调试实测：#1 #2 是同一段话，含两份副本时
    # 命中是「副本运气」而非真实召回）。周 1 bench 的教训「数据必须唯一」在检索
    # 场景同样成立 —— 重复 = 召回位浪费。
    # 双份内容冲突时保留 Word 版：python-docx 是段落级解析，行内无断行噪声；
    # PDF 提取会在行尾插 \n（页面流），同一文字的向量更脏（README 有记录）。
    before = len(all_chunks)
    best_by_key: dict[str, Chunk] = {}  # C#: Dictionary<string, Chunk> —— 去重键 → 最佳切片
    for c in all_chunks:
        key = normalize(c.text)  # C#: 归一化后作去重键（PDF/Word 空白细节不同）
        if key not in best_by_key:
            best_by_key[key] = c
        elif "docx" in c.source and "docx" not in best_by_key[key].source:
            best_by_key[key] = c  # C#: 后来的 Word 版替换先到的 PDF 版（保真度优先）
    all_chunks = list(best_by_key.values())
    dedup_count = before - len(all_chunks)

    stats = summarize(all_chunks)

    # 独立集合（C#: 每策略一个集合 —— 互不污染）
    store = VectorStore(
        str(work_dir),
        collection_name=STRATEGY_COLLECTIONS[strategy],
        embedding_fn=embedder,  # C#: 注入同一个 Embedding 实例（公平性关键）
    )
    t_add = time.perf_counter()
    store.add_documents([c.text for c in all_chunks])
    add_secs = time.perf_counter() - t_add

    # 检索：10 问 × rounds 轮（命中取第 1 轮，延迟取全部轮次平均 —— 与 bench 同口径）
    hits: list[bool] = []
    latencies: list[float] = []
    for _ in range(rounds):
        for qa in GOLDEN_QA:
            t0 = time.perf_counter()
            results = store.search(qa.question, top_k=top_k)
            latencies.append(time.perf_counter() - t0)
            if len(hits) < len(GOLDEN_QA):  # 只记录第一轮的命中
                answer_norm = normalize(qa.answer)
                hit = any(answer_norm in normalize(h.document) for h in results)  # C#: results.Any(...)
                hits.append(hit)
    store.close()  # C#: IDisposable —— 必须先关再删临时目录（bench 踩过的坑）

    return {
        "chunks": all_chunks,
        "stats": stats,
        "hits": hits,
        "dedup_count": dedup_count,
        "chunk_secs": chunk_secs,
        "add_secs": add_secs,
        "avg_query_ms": sum(latencies) / len(latencies) * 1000 if latencies else 0.0,
        "hit_rate": sum(hits) / len(hits) if hits else 0.0,
    }


def main() -> None:
    """CLI 入口：rag-chunk-compare。C#: Main()"""

    parser = argparse.ArgumentParser(description="切片策略对比实验（金标命中率）")
    parser.add_argument("--samples-dir", default=str(DEFAULT_SAMPLES_DIR), help="fixture 目录（先跑 make_samples）")
    parser.add_argument("--chunk-size", type=int, default=300, help="fixed 的 size / recursive 的 max_size")
    parser.add_argument("--overlap", type=int, default=50, help="fixed 专用")
    parser.add_argument("--min-size", type=int, default=50, help="recursive 专用")
    parser.add_argument(
        "--threshold", type=float, default=0.75,
        help="semantic 专用：句子相似度阈值（0.75 = 未校准对照；校准值 0.45 与两种阈值的差异见 README）",
    )
    parser.add_argument("--top-k", type=int, default=3, help="检索返回条数")
    parser.add_argument("--runs", type=int, default=5, help="查询耗时取平均的轮次")
    args = parser.parse_args()

    corpus = load_corpus(Path(args.samples_dir))
    if not corpus:
        print(f"语料为空：{args.samples_dir}（请先运行 uv run python -m rag_core.make_samples）")
        return

    total_chars = sum(len(d.text) for d in corpus)
    print("=" * 72)
    print("切片策略对比实验（rag-chunk-compare）")
    print("=" * 72)
    print(f"语料：{len(corpus)} 个文件（2 PDF + 2 Word 解析文本），共 {total_chars:,} 字符")
    print(f"问题：{len(GOLDEN_QA)} 道金标问答 × top-{args.top_k}，判定 = 答案短语（归一化）∈ 任一切片")
    print("公平性声明：同一语料 / 同一 Embedding 模型（BgeSmallZh 单实例）/ 同一判定口径")
    print("            —— 只有切片策略不同；各策略用自然默认参数（fixed 有 overlap，其余无）")
    print("去重说明：语料 = PDF + Word 双份内容，按归一化文本去重，")
    print("          同内容保留解析保真度更高的 Word 版（PDF 行内有断行噪声），")
    print("          保证 top-k 不被重复切片挤占（周 1 bench『数据必须唯一』教训）")
    print()

    embedder = BgeSmallZh()  # 单实例，三个策略共用（C#: 共享依赖 —— 公平性关键）

    # 分策略参数（C#: 按策略构造选项对象）；semantic 需注入句向量来源
    strategy_kwargs: dict[str, dict] = {
        "fixed": {"size": args.chunk_size, "overlap": args.overlap},
        "recursive": {"max_size": args.chunk_size, "min_size": args.min_size},
        "semantic": {"threshold": args.threshold, "min_size": args.min_size, "embedding_fn": embedder},
    }
    results: dict[str, dict] = {}

    with tempfile.TemporaryDirectory(prefix="rag_chunk_compare_") as work:  # C#: using —— 自动清理
        for strategy in ("fixed", "recursive", "semantic"):
            print(f"--- 策略 [{strategy}] 跑实验中（语义策略含句向量 Embedding，会慢一些）---")
            results[strategy] = run_strategy(
                strategy, corpus, strategy_kwargs[strategy], embedder, Path(work), args.top_k, args.runs
            )
            r = results[strategy]
            print(f"    切片 {r['stats'].count} 条（平均 {r['stats'].avg_len:.0f} 字），"
                  f"去重 {r['dedup_count']} 条，切片耗时 {r['chunk_secs']:.1f}s，入库 {r['add_secs']:.1f}s")
            if strategy == "semantic":
                print(f"    语义策略额外开销：句向量 Embedding 已含在切片耗时 {r['chunk_secs']:.1f}s 内（逐句推理）")
        print()

    # ---- 命中矩阵（10 问 × 3 策略）----
    print("命中矩阵（OK = 答案短语出现在 top-3）：")
    header = f"{'问题':<34}" + "".join(f"{s[:8]:>10}" for s in results)
    print(header)
    for i, qa in enumerate(GOLDEN_QA, 1):
        row = f"Q{i:02d} {qa.question[:28]:<32}"
        for r in results.values():
            row += f"{'OK' if r['hits'][i-1] else 'XX':>10}"
        print(row)
    print()

    # ---- 对比表 ----
    print("对比表（5 次取平均，与周 1 bench 同口径）：")
    print(f"{'策略':<12}{'切片数':>8}{'平均长度':>10}{'命中率':>10}{'平均查询':>10}")
    for strategy, r in results.items():
        print(
            f"{strategy:<12}{r['stats'].count:>8}{r['stats'].avg_len:>9.0f}字"
            f"{r['hit_rate']*100:>9.0f}%"
            f"{r['avg_query_ms']:>9.1f}ms"
        )
    print()

    # ---- 结论（面试话术版）----
    print("结论（面试话术版）：")
    best = max(results, key=lambda s: results[s]["hit_rate"])
    print(f"  1. 本语料（{total_chars:,} 字符小语料）三策略命中率均较高（{best} 最佳）—— "
          "小语料上差距不悬殊是正常现象，真实差异在大语料 + 长答案上")
    for strategy, r in results.items():
        misses = [GOLDEN_QA[i] for i, h in enumerate(r["hits"]) if not h]
        if misses:
            print(f"  2. [{strategy}] 未命中的问题：{', '.join(q.question[:20] for q in misses)} —— 切碎的答案片段没进 top-3")
    print("  3. 切片粒度 = 检索粒度：fixed 机械切分易把长答案切碎（Q01/Q05 长答案），"
          "recursive 边界贴语义结构，semantic 用句向量把主题边界翻译成切片边界")
    print(f"  4. 语义最贵：句向量 Embedding 是一次性成本（本次约 {results['semantic']['chunk_secs']:.1f}s），"
          "且阈值敏感 —— 但『命中率』随块变大虚高（0.75 时碎片合并把碎句粘成 ~324 字大块），"
          "调参必须看命中矩阵 + avg_len，不能只看命中率（README 有 0.45 vs 0.75 完整记录）")
    print("  5. 查询延迟三策略接近（同向量库）—— 切片策略影响的是「召回质量」，不是「检索速度」")
    print("     * 生产建议：小 chunk 检索 + 命中后扩展上下文（Parent Document Retrieval）")


if __name__ == "__main__":  # C#: Main() 入口方法
    main()
