"""向量存储封装 —— ChromaDB 本地模式（周 1：Embedding + 向量数据库）。

C# 对照主线：
  PersistentClient(path)             ≈ 打开一个持久化存储（类似 SQLiteConnection 指到 .db 文件）
  get_or_create_collection(name)     ≈ CREATE TABLE IF NOT EXISTS Documents(...)
  collection.add(ids, documents)     ≈ INSERT INTO Documents(Id, Text) VALUES(...)
  collection.query(query_texts, k)   ≈ SELECT ... 按余弦相似度排序取前 k 条

与 .NET HelloWorld 示例 5/6 的关系：
  示例 5 手写了「Embedding → 余弦相似度 → 排序」，示例 6 用 SQLite 存向量 BLOB；
  ChromaDB 把这三件事打包了（内部用 HNSW 索引 + 向量距离），不用自己写——
  这正是 bench.py 要对比的「手写方案 vs 专用向量库」的性能差距来源。
"""

from dataclasses import dataclass  # C#: record
from typing import List, Optional

import chromadb  # C#: NuGet 包（ChromaDB.Client），本地模式不需要服务端
from chromadb.config import Settings


@dataclass
class SearchHit:
    """一条检索结果。

    C#: public record SearchHit(string Id, string Document, float Distance);
    """

    id: str  # C#: string Id —— 文档唯一标识
    document: str  # C#: string Document —— 原始文本
    distance: float  # C#: float Distance —— 距离值（cosine 时 = 1 - 相似度，越小越相关）


class VectorStore:
    """ChromaDB 向量库封装（本地持久化）。

    C# 对照：一个仓储类 ≈ SqliteDocumentRepository（封装连接 + 增/查方法）。
    教学点：调用方完全不接触向量和距离公式 —— 和手写版（示例 5/6）相比，
    业务代码里剩下的只有「入库」和「检索」两个动作。
    """

    def __init__(
        self,
        path: str,
        collection_name: str = "documents",
        embedding_fn=None,  # C#: IEmbeddingFunction? —— 自定义 Embedding（默认用库内置英文模型）
    ):
        """打开（或创建）本地向量库。

        C#: public VectorStore(string path, string collectionName = "documents",
                               IEmbeddingFunction? embeddingFn = null)
        对应构造函数里打开连接 + 确保表存在。

        教学点：不传 embedding_fn 时 ChromaDB 用内置 MiniLM（英文模型，中文效果差）；
        中文知识库必须传 BgeSmallZh（见 demo.py / bench.py）。
        """
        self._client = chromadb.PersistentClient(
            path=path,  # C#: 数据目录（≈ SQLite .db 文件的存放目录，持久化到磁盘）
            settings=Settings(anonymized_telemetry=False),  # 关闭匿名遥测（学习项目不需要）
        )
        # 动态拼 collection 配置：只有传了自定义模型才覆盖默认（C#: 可选参数 + null 判断）
        collection_kwargs = {
            "name": collection_name,
            # 距离函数选余弦相似度（与示例 5 手写版同口径，bench.py 才能公平对比）
            "metadata": {
                "hnsw:space": "cosine",  # C#: 建表时的配置参数
                # ANN 近似度旋钮：search_ef 越大越接近精确结果（代价是慢一点）。
                # 教学演示用大值（结果与精确检索一致，说服力强）；生产用小值
                #（如默认 10~100）+ 召回率评估 —— 周 3 混合检索会再讨论。
                "hnsw:search_ef": 2000,
            },
        }
        if embedding_fn is not None:
            collection_kwargs["embedding_function"] = embedding_fn  # C#: 覆盖默认 Embedding
        self._collection = self._client.get_or_create_collection(**collection_kwargs)

    def add_documents(
        self,
        documents: List[str],
        ids: Optional[List[str]] = None,
        embeddings: Optional[List[List[float]]] = None,  # C#: float[][]? —— 预计算向量（可选）
    ) -> None:
        """文档入库：文本 → Embedding → 写入向量索引。

        C#: INSERT INTO Documents(Id, Text, Embedding) VALUES(...)

        教学点 1：ChromaDB 默认用内置的 MiniLM 模型做 Embedding（首次运行会下载模型），
        不传 embeddings 时库内自动计算 —— 和示例 5 里手写 Embedding 步骤形成对比。
        教学点 2：embeddings 参数用于「外部预计算后传入」，bench.py 用它保证
        与 SQLite 方案用同一份向量（公平对比，不重复计算）。
        """
        if ids is None:
            # C#: Enumerable.Range(0, n).Select(i => $"doc-{i}").ToList()
            ids = [f"doc-{i}" for i in range(len(documents))]

        if embeddings is None:
            # C#: await _db.InsertBulkAsync(documents)（库内自动算向量，批量写入）
            self._collection.add(ids=ids, documents=documents)
        else:
            self._collection.add(ids=ids, documents=documents, embeddings=embeddings)

    def search(self, query: str, top_k: int = 5) -> List[SearchHit]:
        """语义检索：query → Embedding → 相似度排序 → 取前 k 条。

        手写版对照（示例 5 的实现）：
          var emb = Embed(query);
          var rows = SELECT Text, Embedding FROM Documents;
          var ranked = rows
              .OrderByDescending(r => CosineSimilarity(emb, r.Embedding))  # C#: 手写余弦
              .Take(topK);                                                # C#: 取前 k
        """
        result = self._collection.query(
            query_texts=[query],  # C#: 查询列表（批量查询时传多条，这里只查一条）
            n_results=top_k,  # C#: .Take(top_k) —— 返回的条数上限
        )
        # ChromaDB 返回形状：{ "ids": [[...]], "documents": [[...]], "distances": [[...]] }
        # 外层列表对应 query_texts 的每条查询，所以取 [0] 是本次查询的结果。
        hits: List[SearchHit] = []
        for i, doc_id in enumerate(result["ids"][0]):  # C#: for (int i = 0; i < ids.Count; i++)
            hits.append(
                SearchHit(
                    id=doc_id,
                    document=result["documents"][0][i],  # C#: result.Documents[i]
                    distance=result["distances"][0][i],  # C#: result.Distances[i]
                )
            )
        return hits  # C#: 返回 List<SearchHit>（已按距离升序排好）

    def close(self) -> None:
        """关闭底层客户端，释放文件句柄。

        C#: public void Dispose() —— IDisposable 模式
        Windows 上 HNSW 索引文件被 mmap 映射，不关闭会导致临时目录清理失败
        （PermissionError: 另一个程序正在使用此文件）。
        """
        self._client.close()

    def count(self) -> int:
        """当前库中文档数量。

        C#: SELECT COUNT(*) FROM Documents
        """
        return self._collection.count()

    def clear(self) -> None:
        """清空全部文档（演示脚本重复运行时避免 id 冲突）。

        C#: DELETE FROM Documents;
        """
        ids = self._collection.get().get("ids", [])  # C#: 先查出全部 id（空表时返回空列表）
        if ids:  # C#: if (ids.Count > 0) —— chromadb 拒绝空 id 列表，空表直接跳过
            self._collection.delete(ids=ids)
