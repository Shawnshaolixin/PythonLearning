# rag_core — 项目 C：企业知识库问答系统（周 1-4）

> AI-AGENT-LEARNING-PLAN.md 阶段 1（周 1-4）的唯一 Python 毕业项目。
> 周 1 做地基：**Embedding + 向量数据库（ChromaDB）**；周 2 做文档链路：
> **文档解析（pdfplumber / python-docx）+ 3 种切片策略对比实验**。

## 本周目标（周 1）

- [x] ChromaDB 本地模式：文本 → Embedding → 入库 → 语义检索（query → top-k）
- [x] 检索性能对比：ChromaDB（HNSW 索引）vs SQLite BLOB 手写版（全表扫描）
- [x] 对比结果记录（真实数据见下）

## 本周目标（周 2）

- [x] 文档解析：PDF（pdfplumber）/ Word（python-docx）/ Markdown 直读，统一 `ParsedDocument` 结构
- [x] 三种切片策略：fixed（滑动窗口）/ recursive（LangChain 同款递归降级）/ semantic（句向量贪心合并）
- [x] 真实语料实验：面试文档 → .pdf/.docx fixture → 解析回文本 → 10 道金标问答 × top-3 命中率对比
- [x] 实验卫生：bge 查询前缀（仅查询侧）+ 相同切片去重（保留 Word 保真版）—— 两个 Q05 调试归因
- [x] 对比结果记录（真实数据见下）

## 快速开始

```bash
uv add chromadb                       # 安装依赖（已写入 pyproject.toml）
uv run python -m rag_core.download_models   # 下载中文 Embedding 模型（~95MB，一次性）
uv run rag-demo                       # 最小闭环演示：入库 5 条 → 语义检索 top-2
uv run rag-bench                      # 性能对比（--docs 可调数据量，默认 2000）

# 周 2：解析 → 切片 → 入库 → 对比实验
uv run python -m rag_core.make_samples      # 面试文档 → 2 PDF + 2 Word fixture（含往返验证）
uv run rag-ingest --input src/rag_core/data/samples   # 全链路入库（默认 recursive 策略）
uv run rag-chunk-compare               # 3 策略 × 10 金标问 × top-3 命中率对比（实验，见下）
```

## 文件说明

| 文件 | 作用 | 对应 .NET 对照 |
|------|------|---------------|
| `vector_store.py` | ChromaDB 封装：入库 / 语义检索 / 清空 / 关闭 | 仓储类（SQLiteConnection + 增查方法） |
| `embeddings.py` | 中文 Embedding 模型（bge-small-zh，本地 ONNX 推理 + 查询前缀） | 本地 ONNX 推理器封装 |
| `demo.py` | 最小闭环演示（可直接运行） | 示例 5/6 手写版对照 |
| `bench.py` | 性能对比实验 | 「SQLite 手写 vs 向量库」取舍实验 |
| `download_models.py` | 下载 Embedding 模型（新环境一次性） | 资源初始化脚本 |
| `parsers.py` | 解析分发：`parse_file(path)` 按扩展名 → ParsedDocument | 按扩展名分发的工厂方法 |
| `golden_qa.py` | 10 道金标问答（从源文档逐字验证）+ 空白归一化 | 测试数据常量 |
| `make_samples.py` | .md → .pdf / .docx fixture 生成 + 金标短语往返验证 | 一次性数据准备脚本 |
| `chunking.py` | 3 种切片策略 + STRATEGIES 注册表 + 中文句切分 | 策略模式 + Dictionary 注册表 |
| `ingest.py` | 解析 → 切片 → Embedding → 入库 CLI（rag-ingest） | 管线脚本 |
| `chunk_compare.py` | 切片策略对比实验（rag-chunk-compare，命中矩阵） | A/B 实验骨架（同 bench.py） |

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

## 技术难点与解决（周 2）

1. **中文 PDF 字体不内嵌字形 → 提取失败**：reportlab 的 STSong-Light 是 CID 字体
   （引用但不内嵌字形），pdfplumber 在缺字体机器上提取出乱码/空文本（pdfplumber
   issue #508 同款问题）。解决：fpdf2 + 显式注册 TTF（SimHei 子集化内嵌字形，
   提取可靠）。`make_samples.py` 有候选字体链（环境变量 → data/fonts → C:\Windows\Fonts）。
   *面试点：PDF 的「页面流」结构 —— 提取文本要处理页间/行间断行。*
2. **PDF 是页面流、Word 是段落流**：pdfplumber 在行尾插 `\n`（行内断行噪声），
   python-docx 是段落级解析（保真度高）。同一文档两个格式的解析文本结构不同 →
   相同内容的切片向量不同。实验处理：相同内容去重时**保留 Word 版**（向量更干净）。
3. **「数据必须唯一」教训延伸到检索**：语料 = PDF + Word 双份内容，同一段文字被切出
   两份相同切片，top-k 被重复项挤占（Q05 调试实测 #1 #2 是同一段话 —— 命中是
   「副本运气」不是真实召回）。解决：归一化文本（去空白）作去重键。
4. **bge 查询前缀落地**：入库文档**不加**前缀，查询**加**前缀
   （「为这个句子生成表示以用于检索相关文章：」，embeddings.py 的 `embed_query()`）。
   bge 训练时查询与文档用不同模板，短查询不加前缀与长文档向量错位
   （Q05 型短查询 miss 的归因之一）。
5. **语义阈值校准（本周最深的坑）**：相邻句相似度分布（本语料）P5=0.274 / P50=0.428 /
   P95=0.655。纯阈值 0.75 时**几乎没有任何相邻句对**能合并（590 块、平均 18 字，
   过度切碎灾难）；加 `min_size=50` 碎片合并后 0.75 又把碎句**粘成 ~313 字大块**
   （命中率虚高）。校准值 0.45（≈P50~P60）让阈值合并真正工作 → 平均 148 字、30%。
   调参三件套：**命中矩阵 + avg_len + 相似度分位数**，不能只看命中率。
6. **bge 512 token 截断是静默的**：语义块超 512 token 时向量只反映前缀。
   解决：max_size 默认 800 → 400（中文 ≈ 400 token）。
7. **make_samples 往返验证**：生成 fixture 后立即解析回文本，10 条金标短语
   空白归一化后逐字验证存活（PDF/Word 都过），任何失败退出非 0 —— 保证
   「实验语料真的来自源文档」。
8. **Windows GBK 控制台**：不能打印 ✓/✗/部分中文 → CLI 输出统一 ASCII（OK/XX），
   报错 `UnicodeEncodeError: 'gbk' codec` 时先怀疑终端编码。

## 切片策略对比记录（周 2 输出物）

> 环境：Windows 11 / CPU / bge-small-zh-v1.5（512 维）。
> 语料：data/samples/ 下 2 份 PDF + 2 份 Word（`game_interview_guide.md` +
> `game_interview_100_questions.md` 转换，共 38,878 字符，PDF+Word 双份内容
> 已按归一化文本去重，保留 Word 版）。
> 口径：10 道金标问答 × top-3，命中 = 答案短语（空白归一化）∈ 任一切片；
> 查询耗时 5 次取平均（与周 1 bench 同口径）。

```
对比表（threshold=0.75，语义策略「未校准 + 碎片合并」对照档）：
  策略        切片数   平均长度   命中率   切片耗时   查询耗时
  fixed       151      294 字    80%     0.0s      6.6ms
  recursive   100      247 字    50%     0.0s      6.0ms
  semantic     71      313 字    70%     7.4s     11.2ms
  （semantic 的 7.4s = 逐句向量推理，一次性成本；入库 3.5s 已含）

命中矩阵（OK = 答案短语出现在 top-3）：
  问题                                       fixed  recursive  semantic
  Q01 仿真开发和游戏开发的本质区别是什么？       XX     XX         OK
  Q02 海外休闲游戏公司招人时最看重什么？        OK     XX         XX
  Q03 休闲游戏的核心循环长什么样？             OK     OK         XX
  Q04 激励视频广告应该放在哪些场景？           OK     OK         OK
  Q05 新手引导的核心目标是什么？              XX     XX         OK
  Q06 Addressables 在资源更新上有什么优势？    OK     OK         XX
  Q07 插屏广告为什么容易伤害体验？            OK     XX         OK
  Q08 为什么奖励发放必须做幂等？              OK     OK         OK
  Q09 D1 留存低应该先排查什么？              OK     XX         OK
  Q10 协程的本质是什么？                    OK     OK         OK
```

**阈值对比（同语料、同一判定口径）**：

```
  semantic @ threshold=0.45（校准值）：124 块、平均 148 字、命中 30%（Q02/Q04/Q10 命中）
  semantic @ threshold=0.75（未校准）： 71 块、平均 313 字、命中 70%
```

**结论（面试话术版）**：

- **长答案（Q01 17 字 / Q05 21 字）**：fixed 机械窗口把句子切碎 → 全灭；
  semantic 句子对齐 + 主题合并 → 命中。`切片粒度 = 检索粒度` 的直接证据。
- **短短语（Q02 9 字 / Q06 6 字）**：semantic 大块把短语稀释在上下文里 → 全灭；
  fixed 小块反而占优。**没有万能策略，问题分布决定选型**。
- **recursive 半吊子（50%）**：边界贴结构但 PDF 断行噪声 + 双份内容
  使其 5/10 全凭边界运气 —— 真实工程里它仍是默认首选（成本最低、边界可解释）。
- **命中率会随块变大虚高**：0.75 档「碎片合并把碎句粘成 313 字大块」的 70%
  与 0.45 档的 30%，差距大半是块大小，不是语义边界质量 —— 调参必须看矩阵 + avg_len。
- **查询延迟三策略接近（6~11ms）**：切片策略影响「召回质量」，不影响「检索速度」。
- **生产建议**：小 chunk 检索 + 命中后扩展上下文（Parent Document Retrieval），
  周 4 收尾项目时会演示；大语料上差距会拉大，届时用 RAGAS 定量评估（周 3）。

## 后续周次（周 3-4 预告）

- 周 3：混合检索（Embedding + BM25 → RRF → Reranker）+ RAGAS 四指标评估
- 周 4：项目 C 收尾（上传接口 + Docker + 架构图，GitHub 打 tag v1.0）
