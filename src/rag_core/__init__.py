"""rag_core —— 项目 C：企业知识库问答系统（周 1-4）。

周 1：Embedding + 向量数据库（ChromaDB）
  vector_store.py — ChromaDB 本地模式封装（入库 / 语义检索 / bge 查询前缀）
  demo.py         — 最小闭环演示：存几条 → 问一个问题 → top-k 结果
  bench.py        — 性能对比：ChromaDB vs SQLite BLOB 手写版（面试弹药）

周 2：文档处理 + 切片策略
  parsers.py      — 解析分发：pdf（pdfplumber）/ docx（python-docx）/ md / txt
  golden_qa.py    — 10 道金标问答（实验判定口径，从源文档逐字验证）
  make_samples.py — 面试文档 → .pdf / .docx fixture + 往返验证（一次性）
  chunking.py     — 3 种切片策略：fixed / recursive / semantic（句向量贪心合并）
  ingest.py       — 解析 → 切片 → 入库 CLI（rag-ingest）
  chunk_compare.py— 切片策略对比实验（rag-chunk-compare，金标命中率矩阵）

后续周次将在此包内扩展（混合检索 / RAGAS 评估 / 收尾）。
"""
