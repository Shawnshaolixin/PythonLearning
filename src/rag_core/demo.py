"""周 1 最小闭环演示：文本 → Embedding 入库 → 语义检索（query → top-k）。

运行：uv run rag-demo

流程：
  1. 初始化本地向量库（数据落在 rag_core/data/chroma/）
  2. 存入几条 AI 费用主题的文档
  3. 问两个问题，各返回 top-2
  4. 观察重点：问题 2 与匹配文档「字面完全不同」却命中了 —— 这就是 Embedding 语义检索
     和 SQL 精确匹配（LIKE / ==）的本质区别，也是 RAG 能工作的地基。
"""

import shutil  # C#: 目录递归删除（Directory.Delete(recursive: true)）
from pathlib import Path  # C#: using System.IO;

from rag_core.embeddings import BgeSmallZh  # C#: 自定义中文 Embedding 模型（本地 ONNX）
from rag_core.vector_store import VectorStore  # C#: using RagCore.VectorStore;

# 示例文档：主题延续本仓库的 AI 费用统计（周 2 起会换成真实企业文档解析）
SAMPLE_DOCS = [
    # 每条 ≈ 知识库里的一条记录（C# 侧对应 List<string> 或数据行）
    "DeepSeek 的输入价格为每百万 token 0.5 元，输出价格为每百万 token 2 元，输出价格是输入价格的 4 倍。",
    "OpenAI 的 GPT-4o 模型输入价格每百万 token 2.5 美元，输出价格每百万 token 10 美元。",
    "AI 应用控制成本的关键手段包括：分级模型、缓存相似问题和设置 Token 预算告警。",
    "FastAPI 是基于 Starlette 和 Pydantic 的现代 Python Web 框架，性能接近 NodeJS。",
    "RAG（检索增强生成）通过从外部知识库检索相关片段来减少模型幻觉，提高回答准确率。",
]


def show_query(store: VectorStore, query: str) -> None:
    """打印一次检索的 top-2 结果。

    C#: void ShowQuery(VectorStore store, string query) —— 输出到控制台的辅助方法
    """
    print(f"\n问：{query}")
    hits = store.search(query, top_k=2)  # C#: var hits = store.Search(query, topK: 2);
    for rank, hit in enumerate(hits, start=1):  # C#: hits.Select((h, i) => ...) 带序号
        # C#: $"#{rank} [距离 {hit.Distance:F3}] {hit.Document}"
        print(f"  #{rank} [距离 {hit.distance:.3f}] {hit.document}")


def main() -> None:
    """演示入口。

    C#: static void Main() —— 控制台程序入口
    """
    # 数据目录固定在包内 data/chroma/（已加入 .gitignore，不提交）
    chroma_dir = Path(__file__).parent / "data" / "chroma"  # C#: Path.Combine(包目录, "data", "chroma")

    # 整个删掉重建，而不是只 clear()：collection 的 Embedding 模型是持久化配置，
    # 换模型必须重建库（工程知识点：Embedding 版本升级 → 全量重新索引）
    shutil.rmtree(chroma_dir, ignore_errors=True)  # C#: Directory.Delete(dir, recursive: true)

    # 关键：传入中文 Embedding 模型 —— 内置 MiniLM 是英文模型，中文检索会排错序
    #（想亲眼看差别：把这行参数删掉再跑一次，观察"控制成本"问题命中不了）
    store = VectorStore(str(chroma_dir), embedding_fn=BgeSmallZh())  # C#: new BgeSmallZh() 注入
    store.add_documents(SAMPLE_DOCS)  # C#: INSERT INTO ... 批量入库
    print(f"已入库 {store.count()} 条文档\n")  # C#: $"已入库 {store.Count()} 条文档"

    show_query(store, "DeepSeek 的输入和输出价格差多少倍？")
    show_query(store, "怎么省下 AI 服务的开销？")
    # ↑ 这句与文档 3（"控制成本的关键手段"）字面零重合词（省下/开销 vs 控制/成本），
    #   却能命中 —— 语义相似，而不是关键词相同。这就是 Embedding 检索的意义。
    #   对比：SELECT * FROM documents WHERE text LIKE "%开销%" 会返回空。

    print("\n对照实验（想直观感受差别，把 query 换成 SQL）：")
    print('  SELECT * FROM documents WHERE text LIKE "%花费%"  -- 结果为空')


if __name__ == "__main__":  # C#: Main() 入口方法
    main()
