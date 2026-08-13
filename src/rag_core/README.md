# rag_core — 项目 C：企业知识库问答系统（周 1-4）

> AI-AGENT-LEARNING-PLAN.md 阶段 1（周 1-4）的唯一 Python 毕业项目。
> 周 1 只做地基：**Embedding + 向量数据库（ChromaDB）**。

## 本周目标（周 1）

- [x] ChromaDB 本地模式：文本 → Embedding → 入库 → 语义检索（query → top-k）
- [x] 检索性能对比：ChromaDB（HNSW 索引）vs SQLite BLOB 手写版（全表扫描）
- [x] 对比结果记录（真实数据见下）

## 快速开始

```bash
uv add chromadb                       # 安装依赖（已写入 pyproject.toml）
uv run python -m rag_core.download_models   # 下载中文 Embedding 模型（~95MB，一次性）
uv run rag-demo                       # 最小闭环演示：入库 5 条 → 语义检索 top-2
uv run rag-bench                      # 性能对比（--docs 可调数据量，默认 2000）
```

## 文件说明

| 文件 | 作用 | 对应 .NET 对照 |
|------|------|---------------|
| `vector_store.py` | ChromaDB 封装：入库 / 语义检索 / 清空 / 关闭 | 仓储类（SQLiteConnection + 增查方法） |
| `embeddings.py` | 中文 Embedding 模型（bge-small-zh，本地 ONNX 推理） | 本地 ONNX 推理器封装 |
| `demo.py` | 最小闭环演示（可直接运行） | 示例 5/6 手写版对照 |
| `bench.py` | 性能对比实验 | 「SQLite 手写 vs 向量库」取舍实验 |
| `download_models.py` | 下载 Embedding 模型（新环境一次性） | 资源初始化脚本 |

## 技术难点与解决（周 1）

1. **英文模型对中文检索失效**：ChromaDB 内置 all-MiniLM-L6-v2 是英文模型，
   「控制成本有哪些手段」这种高相关中文问题都排不进前 2。
   解决：换 bge-small-zh-v1.5（BAAI 中文小模型，512 维），并用
   `embeddings.py` 实现完整推理管线（tokenize → ONNX → mean pooling → L2 归一化）。
   *面试点：bge 查询建议加指令前缀「为这个句子生成表示以用于检索相关文章：」。*
2. **换 Embedding 模型必须重建库**：collection 的 Embedding 类型是持久化配置，
   直接换会报错（embedding function conflict）。工程上 = Embedding 版本升级 → 全量重新索引。
3. **Windows 文件句柄**：HNSW 索引文件被 mmap 锁定，不显式 `close()` 临时目录删不掉。
   C# 对照：IDisposable / Dispose 模式。
4. **HNSW 是近似索引（ANN）**：默认 ef_search 下小数据量也可能漏精确邻居；
   教学演示用 `hnsw:search_ef: 2000` 逼近精确结果（代价是查询慢一点）。
   *面试点：生产用小 ef + 召回率评估（周 3 混合检索会再讨论）。*
5. **Benchmark 数据必须唯一**：模拟文档不唯一 → 大量完全相同向量 → top-k 全是并列项，
   一致性对比失真（还踩过 query 恰好落在生成空间的坑）。

## 检索性能对比记录（周 1 输出物）

> 环境：Windows 11 / CPU / 2000 条中文模拟文档 / bge-small-zh-v1.5（512 维）。
> 口径：两方案共用同一份预计算向量；检索耗时 = 5 次取平均；top-3 用集合比较一致性。

```
Embedding（2000 条，两方案共享，不计入对比）: 2.27s
  方案                          入库耗时      检索耗时    结果一致性
  A. ChromaDB (HNSW)           0.58s        1.2ms      基准
  B. SQLite BLOB (全表扫描)     0.02s       13.7ms     一致
检索加速比：11.1x（数据量越大，A 的优势越明显）
```

**结论（面试话术版）**：
- 入库：ChromaDB 略慢（0.58s vs 0.02s）—— 建 HNSW 索引的固定成本
- 检索：ChromaDB 快 11 倍 —— HNSW 索引 O(log N) vs 全表扫描 O(N)，且差距随数据量增大
- 质量：结果与精确全表扫描一致（ef_search 调大后）
- 结论：小数据量（<10 万条）手写 SQLite 完全能用；企业级要增量写入 + 毫秒级检索时必须上向量库

## 后续周次（周 2-4 预告）

- 周 2：文档解析（pdfplumber / python-docx）+ 3 种切片策略对比实验
- 周 3：混合检索（Embedding + BM25 → RRF → Reranker）+ RAGAS 四指标评估
- 周 4：项目 C 收尾（上传接口 + Docker + 架构图，GitHub 打 tag v1.0）
