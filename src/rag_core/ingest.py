"""入库 CLI —— 文档 → 解析 → 切片 → Embedding → ChromaDB（rag-ingest）。

C# 对照主线：
  本工具 ≈ C# 里的控制台流水线工具（DocumentIndexer）：
    int Main(string[] args)  -- argparse 解析 → 逐文件执行流水线
  流水线：ParseFile → Chunk → Embedding → 入库
          （各环节都复用 rag_core 已有模块，这是「分层 + 复用」的教学示范）

设计决策（与学习者确认）：本周只做 CLI 入库，不做 FastAPI 上传接口
（周 4 项目收尾时再包成 /upload 接口）—— 先让切片实验跑起来。
"""

import argparse  # C#: 命令行参数解析（对标 CommandLineParser 库）
import time  # C#: System.Diagnostics.Stopwatch
from pathlib import Path  # C#: System.IO

from rag_core.chunking import STRATEGIES, summarize  # C#: 策略注册表 + 统计
from rag_core.embeddings import BgeSmallZh  # C#: 中文 Embedding 模型
from rag_core.parsers import ParsedDocument, parse_file  # C#: 解析分发器
from rag_core.vector_store import VectorStore  # C#: 仓储类（ChromaDB 封装）

# 默认数据目录与 demo.py 共用（跑 rag-demo 会清空它 —— README 有说明）
DEFAULT_CHROMA_DIR = Path(__file__).parent / "data" / "chroma"

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".md", ".txt"}  # C#: HashSet<string>


def ingest_file(
    store: VectorStore,
    path: Path,
    strategy: str,
    **chunk_kwargs,  # C#: params 风格 —— chunk-size / overlap / threshold 透传
) -> dict:
    """单文件流水线：解析 → 切片 → 入库，返回统计。C#: IndexDocument(store, path, ...)"""

    # 1) 解析（C#: var doc = ParseFile(path)）
    t0 = time.perf_counter()  # C#: Stopwatch.StartNew()
    doc: ParsedDocument = parse_file(path)
    parse_secs = time.perf_counter() - t0

    # 2) 切片（C#: var chunks = ChunkBy(strategy, doc.Text, kwargs)）
    t0 = time.perf_counter()
    if strategy == "semantic":
        # 语义策略需要注入句向量来源（C#: 依赖注入 —— IEmbeddingFunction）
        chunk_kwargs["embedding_fn"] = BgeSmallZh()
    chunks = STRATEGIES[strategy](doc.text, source=f"{path.stem} ({doc.format})", **chunk_kwargs)
    chunk_secs = time.perf_counter() - t0

    # 3) 入库（C#: repo.AddDocuments(chunks.Select(c => c.Text))）
    t0 = time.perf_counter()
    ids = [f"{path.stem}-{doc.format}-{c.index}" for c in chunks]  # C#: 来源可追溯的 id
    store.add_documents([c.text for c in chunks], ids=ids)
    add_secs = time.perf_counter() - t0

    stats = summarize(chunks)
    return {
        "path": str(path),
        "format": doc.format,
        "chars": len(doc.text),
        "paragraphs": doc.paragraph_count,
        "parse_secs": parse_secs,
        "chunk_secs": chunk_secs,
        "add_secs": add_secs,
        "stats": stats,
    }


def collect_files(input_path: Path) -> list[Path]:
    """收集待入库文件：文件直接收，目录递归找支持的扩展名。

    C#: 目录遍历 —— Directory.EnumerateFiles(input, "*", SearchOption.AllDirectories)
    """
    if input_path.is_file():
        return [input_path]
    return sorted(  # C#: 排序保证可复现（C#: OrderBy）
        p for p in input_path.rglob("*") if p.suffix.lower() in SUPPORTED_SUFFIXES
    )


def main() -> None:
    """CLI 入口：rag-ingest。C#: Main()"""

    parser = argparse.ArgumentParser(description="解析 + 切片 + 入库（rag_core 周 2）")
    parser.add_argument("--input", required=True, help="文件或目录（支持 .md/.txt/.pdf/.docx）")
    parser.add_argument("--strategy", choices=sorted(STRATEGIES), default="recursive", help="切片策略")
    parser.add_argument("--chunk-size", type=int, default=300, help="fixed 的 size / recursive 的 max_size")
    parser.add_argument("--overlap", type=int, default=50, help="fixed 专用：窗口重叠字符数")
    parser.add_argument("--min-size", type=int, default=50, help="recursive 专用：碎片合并下限")
    parser.add_argument("--threshold", type=float, default=0.75, help="semantic 专用：句子相似度阈值（0.45 校准值对比见 README）")
    parser.add_argument("--collection", default="docs", help="ChromaDB 集合名（≥3 字符）")
    parser.add_argument("--chroma-dir", default=str(DEFAULT_CHROMA_DIR), help="ChromaDB 数据目录")
    args = parser.parse_args()  # C#: 命令行参数绑定

    input_path = Path(args.input)
    files = collect_files(input_path)
    if not files:
        print(f"没有找到可入库的文件：{input_path}")
        return

    # 构造分策略参数字典：只透传相关参数（C#: 按策略构造选项对象）
    kwargs: dict = {"size": args.chunk_size, "overlap": args.overlap} if args.strategy == "fixed" else {}
    if args.strategy == "recursive":
        kwargs = {"max_size": args.chunk_size, "min_size": args.min_size}
    if args.strategy == "semantic":
        kwargs = {"threshold": args.threshold}

    store = VectorStore(args.chroma_dir, collection_name=args.collection, embedding_fn=BgeSmallZh())
    store.clear()  # 幂等：重复运行不因 id 冲突报错（C#: 与 bench 同做法）
    print(f"策略 [{args.strategy}]，集合 [{args.collection}]，共 {len(files)} 个文件")

    total_chunks = 0
    for path in files:
        result = ingest_file(store, path, args.strategy, **kwargs)
        total_chunks += result["stats"].count
        print(
            f"  {result['path']}：格式={result['format']}，字符={result['chars']}，"
            f"切片={result['stats'].count}，平均={result['stats'].avg_len:.0f} 字，"
            f"解析={result['parse_secs']:.2f}s，切片={result['chunk_secs']:.2f}s，入库={result['add_secs']:.2f}s"
        )

    print(f"完成：共 {total_chunks} 条 → {args.collection} @ {args.chroma_dir}")


if __name__ == "__main__":  # C#: Main() 入口方法
    main()
