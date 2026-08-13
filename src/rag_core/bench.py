"""性能对比：ChromaDB（HNSW 索引） vs SQLite BLOB 手写版（全表扫描 + 余弦）。

运行：uv run rag-bench [--docs 2000]

C# 对照主线：
  本脚本 ≈ 示例 6（SQLite 存向量 BLOB）与专用向量库的取舍实验。
  面试时能说清「为什么不用 SQLite 手写」：数据量大后全表扫描是 O(N)，
  向量库用 HNSW 近似索引把检索降到了 O(log N) —— 本脚本就是这句结论的数据来源。

公平性设计（关键，否则对比没有说服力）：
  两个方案用同一个 Embedding 函数（都是 ChromaDB 内置 MiniLM）生成向量，
  距离口径都是余弦 —— 对比的只是「存储 + 检索」环节本身。

结论预期：
  - 入库：ChromaDB 略慢（额外建索引），差距不大
  - 检索：数据量越大，ChromaDB 的 HNSW 优势越明显（全表扫描 O(N) vs 索引 O(log N)）
  - 结果一致性：top-3 命中 id 应完全一致（同一向量 + 同一度量）
"""

import argparse  # C#: 命令行参数解析（类似 System.CommandLine）
import os  # C#: System.IO —— mkstemp 返回的句柄需要手动关闭
import random  # C#: Random —— 生成模拟文档
import sqlite3  # C#: System.Data.SQLite —— Python 内置，零依赖
import tempfile  # C#: Path.GetTempFileName
import time  # C#: Stopwatch
from pathlib import Path  # C#: System.IO

import numpy as np  # C#: 数值计算（.NET 里对应 MathNet.Numerics / 手写 for 循环）

from rag_core.embeddings import BgeSmallZh  # C#: 中文 Embedding 模型（A/B 共用，保证公平）
from rag_core.vector_store import VectorStore  # C#: using RagCore.VectorStore;

# 主题词库：随机组合出"看起来像话"的模拟文档（性能测试不需要语义质量）
TOPICS = ["成本控制", "检索增强", "模型切片", "向量索引", "费用统计", "会话管理", "缓存策略", "数据评估"]
ACTIONS = ["的最佳实践", "的实现方案", "常见陷阱", "性能对比", "落地经验", "设计要点"]


def make_docs(count: int) -> list[str]:
    """生成 count 条模拟文档（每条约 20-40 字）。

    C#: List<string> MakeDocs(int count) —— 随机组合主题词
    注意：必须保证每条文本唯一 —— 主题组合空间只有 336 种，不唯一的话
    会出现大量「完全相同的向量」，检索 top-k 全是并列项，benchmark 失真。
    """
    rng = random.Random(42)  # C#: 固定种子 —— 每次运行生成同样的数据，对比可复现
    docs: list[str] = []
    for i in range(count):  # C#: for (int i = 0; i < count; i++)
        # C#: $"{topic1}和{topic2}{action}"，rng.Sample(TOPICS, 2)
        parts = rng.sample(TOPICS, k=2)  # C#: rng.Sample —— 不重复抽 2 个主题
        # 加唯一编号后缀：文本唯一 → 向量唯一 → 检索结果无并列项
        docs.append(f"{parts[0]}与{parts[1]}{rng.choice(ACTIONS)}（记录 {i}）")  # C#: 插值唯一 ID
    return docs


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """余弦相似度（示例 5 同款公式，B 方案检索时逐个计算）。

    C#: double CosineSimilarity(float[] a, float[] b) =>
            a.Zip(b).Sum(p => p.First * p.Second) / (Norm(a) * Norm(b));
    """
    # C#: dot = a · b；denom = |a| * |b|；除以零时返回 0（防全零向量）
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1.0  # C#: ||a|| * ||b||
    return float(np.dot(a, b) / denom)  # C#: return dot / denom


def bench_sqlite(docs: list[str], vectors: list, query_vec: np.ndarray, top_k: int) -> dict:
    """方案 B：SQLite 存 BLOB，检索时全表扫描 + 手写余弦排序。

    C# 对照（示例 6 的实现）：
      INSERT INTO Documents(Id, Text, Embedding) VALUES(?, ?, ?)  -- BLOB 存向量
      SELECT Text, Embedding FROM Documents                        -- 全表读出
      然后 C# 里 for 循环算余弦 → OrderByDescending → Take(k)

    公平性：vectors 由调用方预计算传入（与方案 A 同一份），本函数只计时
    「存 BLOB + 全表检索」—— Embedding 是共享环节，不计入任何一方。
    """
    fd, tmp_path = tempfile.mkstemp(suffix=".db")  # C#: Path.GetTempFileName()
    os.close(fd)  # C#: 关闭文件句柄（否则 Windows 上文件被占用，删不掉）
    conn = sqlite3.connect(tmp_path)  # C#: new SQLiteConnection($"Data Source={tmp}")
    conn.execute("CREATE TABLE documents (id TEXT, text TEXT, embedding BLOB)")  # C#: 建表

    t0 = time.perf_counter()  # C#: var sw = Stopwatch.StartNew();
    # C#: 逐条序列化 float[] → BLOB（BinaryWriter / BitConverter）
    rows = [
        (f"doc-{i}", doc, np.array(v, dtype=np.float32).tobytes())
        for i, (doc, v) in enumerate(zip(docs, vectors))  # C#: docs.Zip(vectors)
    ]
    conn.executemany("INSERT INTO documents VALUES (?, ?, ?)", rows)  # C#: 批量插入
    conn.commit()
    insert_secs = time.perf_counter() - t0  # C#: sw.Elapsed.TotalSeconds

    # 检索：全表扫描（数据量大时这里是瓶颈，O(N) 逐条算余弦）。跑 5 次取平均（去噪声）
    t0 = time.perf_counter()
    for _ in range(5):  # C#: 多次测量取平均
        vecs, texts = [], []
        for id_, text, blob in conn.execute("SELECT id, text, embedding FROM documents"):
            vecs.append(np.frombuffer(blob, dtype=np.float32))  # C#: 字节数组 → float[]
            texts.append((id_, text))
        sims = [cosine_similarity(query_vec, v) for v in vecs]  # C#: 全表余弦（LINQ）
        # C#: rows.OrderByDescending(r => r.Similarity).Take(k).Select(r => r.Id)
        top = sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)[:top_k]  # C#: 排序取前 k
    query_secs = (time.perf_counter() - t0) / 5  # C#: 平均单次耗时

    conn.close()
    Path(tmp_path).unlink()  # C#: File.Delete —— 用完即删临时库
    return {
        "insert_secs": insert_secs,
        "query_secs": query_secs,
        "top_ids": [texts[i][0] for i in top],  # C#: 前 k 名的文档 id（用于一致性对比）
    }


def bench_chroma(docs: list[str], vectors: list, query_vec: np.ndarray, top_k: int, work_dir: Path) -> dict:
    """方案 A：ChromaDB（内置 HNSW 索引，检索走索引不是全表扫）。"""
    store = VectorStore(str(work_dir / "chroma"), embedding_fn=None)  # C#: 打开向量库（首次建库）
    store.clear()

    t0 = time.perf_counter()
    # C#: collection.Add(ids, documents, embeddings) —— 显式传向量，跳过内部重算
    store.add_documents(
        docs,
        embeddings=vectors,  # C#: 传入预计算向量（教学点：库里也可自动算，这里为了公平手动传）
    )
    insert_secs = time.perf_counter() - t0

    # 检索走 HNSW 索引（O(log N)）。跑 5 次取平均（去噪声）
    t0 = time.perf_counter()
    for _ in range(5):
        result = store._collection.query(
            query_embeddings=[query_vec],  # C#: 查询向量（索引查找，不是全表扫）
            n_results=top_k,
        )
    query_secs = (time.perf_counter() - t0) / 5

    store.close()  # C#: Dispose() —— 释放 mmap 文件句柄（Windows 必须，否则临时目录删不掉）

    return {
        "insert_secs": insert_secs,
        "query_secs": query_secs,
        "top_ids": result["ids"][0],
    }


def main() -> None:
    """对比实验入口。

    C#: static void Main() —— 控制台入口
    """
    # C#: var parser = new CommandLineParser(); --docs 参数（默认 2000 条）
    parser = argparse.ArgumentParser(description="ChromaDB vs SQLite BLOB 检索性能对比")
    parser.add_argument("--docs", type=int, default=2000, help="模拟文档条数（默认 2000）")
    args = parser.parse_args()  # C#: 解析命令行参数

    count = args.docs
    # 固定问题：保证两次运行结果可比。
    # 注意：query 必须是生成空间（TOPICS × ACTIONS）之外的自然句 ——
    # 否则会出现多条相似度 1.0 的并列（make_docs 生成重复文本），并列排序没意义。
    query = "怎样评估知识库检索结果的好坏？"
    top_k = 3

    print(f"生成 {count} 条模拟文档 …")
    docs = make_docs(count)  # C#: var docs = MakeDocs(count);

    # 两个方案共用同一份 Embedding（公平对比：差异只在存储 + 检索）。
    # Embedding 单独计时 —— 它是共享环节，计入任何一方都不公平。
    emb_fn = BgeSmallZh()  # C#: var embFn = new BgeSmallZh();
    t0 = time.perf_counter()
    vectors = emb_fn(docs)  # C#: 批量 Embedding（2000 条 CPU 推理，可看到进度感）
    query_vec = np.array(emb_fn([query])[0], dtype=np.float32)
    embed_secs = time.perf_counter() - t0

    # 临时工作目录：两个方案的数据都放这里，跑完自动清
    with tempfile.TemporaryDirectory() as work_dir:  # C#: using 临时目录（自动清理）
        print("方案 A：ChromaDB（HNSW 索引）…")
        a = bench_chroma(docs, vectors, query_vec, top_k, Path(work_dir))
        print("方案 B：SQLite BLOB 手写版（全表扫描）…")
        b = bench_sqlite(docs, vectors, query_vec, top_k)

    # C#: Console.WriteLine($"...") 格式化对比表
    print("\n对比结果：")
    # C#: $"Embedding（两方案共享，不计入对比）: {embed_secs:F2}s"
    print(f"Embedding（{count} 条 bge-small-zh 本地推理，两方案共享）: {embed_secs:.2f}s")
    print(f"  {'方案':<28}{'入库耗时':>12}{'检索耗时':>14}   结果一致性")
    # C#: 字符串插值对齐：{a['insert_secs']:>10.2f}s
    print(f"  {'A. ChromaDB (HNSW)':<28}{a['insert_secs']:>9.2f}s{a['query_secs'] * 1000:>11.1f}ms   基准")
    # 用集合比较：并列（距离相同）时两个实现的内部顺序不保证，但命中集合必须一致。
    # C#: set 等价物 —— HashSet<T> 相等比较（忽略顺序）
    consistent = set(a["top_ids"]) == set(b["top_ids"])
    print(f"  {'B. SQLite BLOB (全表扫描)':<28}{b['insert_secs']:>9.2f}s{b['query_secs'] * 1000:>11.1f}ms   "
          f"{'一致' if consistent else '不一致！'}")

    speedup = b["query_secs"] / a["query_secs"]  # C#: 检索加速比
    print(f"\n检索加速比：{speedup:.1f}x（数据量越大，A 的优势越明显 —— 可加大 --docs 再跑）")
    print("为什么：A 用 HNSW 近似最近邻索引（O(log N)），B 是逐条算余弦的全表扫描（O(N)）。")
    print("面试话术：这就是『向量数据库 vs SQLite 手写』取舍的数据版答案。")


if __name__ == "__main__":  # C#: Main() 入口方法
    main()
