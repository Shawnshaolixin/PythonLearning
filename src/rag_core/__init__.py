"""rag_core —— 项目 C：企业知识库问答系统（周 1-4）。

周 1：Embedding + 向量数据库（ChromaDB）
  vector_store.py — ChromaDB 本地模式封装（入库 / 语义检索）
  demo.py         — 最小闭环演示：存几条 → 问一个问题 → top-k 结果
  bench.py        — 性能对比：ChromaDB vs SQLite BLOB 手写版（面试弹药）

后续周次将在此包内扩展（切片 / 混合检索 / RAGAS 评估）。
"""
