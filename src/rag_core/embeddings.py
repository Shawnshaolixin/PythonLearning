"""自定义中文 Embedding 模型 —— bge-small-zh-v1.5（ONNX 本地推理）。

C# 对照主线：
  本类 ≈ C# 里封装本地 ONNX 推理器（Microsoft.ML.OnnxRuntime + Tokenizer）：
    float[] Embed(string text)  -- 文本 → 512 维向量
  推理管线（教学点，面试会问）：
    tokenize → ONNX 推理 → mean pooling（按 attention_mask 加权平均）→ L2 归一化

为什么不用 ChromaDB 内置 MiniLM：
  内置 all-MiniLM-L6-v2 是英文模型，中文语义表征很弱（demo 里「控制成本」检索
  排不进前 2）—— 企业中文知识库必须换中文模型，这是周 1 的核心技术难点。
  选 bge-small-zh-v1.5：BAAI 出品的开源中文模型，512 维，检索质量与速度平衡。
  模型文件放 rag_core/data/models/（.gitignore，首次用下载脚本补齐）。
"""

from pathlib import Path  # C#: System.IO
from typing import List  # C#: System.Collections.Generic

import numpy as np  # C#: 数值计算（.NET 用 MathNet.Numerics 或手写）
import onnxruntime as ort  # C#: Microsoft.ML.OnnxRuntime —— chromadb 已带此依赖
from tokenizers import Tokenizer  # C#: HuggingFace Tokenizers（chromadb 已带此依赖）

from chromadb.api.types import EmbeddingFunction  # C#: 接口（实现 __call__ 协议）


class BgeSmallZh(EmbeddingFunction[List[str]]):
    """中文 Embedding 模型封装：文本列表 → 向量列表。

    C#: public class BgeSmallZh : IEmbeddingFunction { public float[][] Embed(IEnumerable<string> texts) }
    教学点：ChromaDB 的 embedding_function 只需要实现 __call__(texts) -> vectors，
    内部推理细节（tokenize / pooling / 归一化）都封装在这个类里。
    """

    MAX_LENGTH = 512  # C#: const int MaxLength = 512 —— bge 模型最大序列长度
    BATCH_SIZE = 64  # C#: const int BatchSize = 64 —— 分块推理，防大列表吃爆内存

    # bge 官方建议（README 周 1 面试点落地）：短查询文本加指令前缀后检索质量明显更好；
    # 文档入库**不加**前缀 —— 前缀只属于查询侧（C#: 查询专用的常量模板）
    QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："

    def embed_query(self, text: str) -> list[float]:
        """查询向量：bge 查询侧加指令前缀（与入库文档不加前缀形成对照）。

        C#: float[] EmbedQuery(string text) —— 查询专用方法
        为什么只对查询加：bge 训练时查询与文档用不同模板，短查询（几字到几十字）
        不加前缀时与长文档向量错位，chunk_compare 实测 Q05 型短查询会 miss（README 记录）。
        """
        return self([self.QUERY_PREFIX + text])[0]

    # 模型文件目录：rag_core/data/models/bge-small-zh/（已加入 .gitignore）
    MODEL_DIR = Path(__file__).parent / "data" / "models" / "bge-small-zh"

    def __init__(self, model_dir: Path | None = None):  # C#: public BgeSmallZh(string? modelDir = null)
        """加载 tokenizer + ONNX 模型。

        C#: 构造函数里加载资源（Tokenizer 文件 + ONNX Session），首次加载较慢。
        """
        self.model_dir = model_dir or self.MODEL_DIR  # C#: ?? 空合并运算符

        # tokenizer：把中文文本切分成 token id 序列（C#: Tokenizer.FromFile(...)）
        self.tokenizer = Tokenizer.from_file(str(self.model_dir / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=self.MAX_LENGTH)  # C#: 超长截断
        # 不传 length = 动态 padding：批内按最长句补齐（短句不浪费算力）
        self.tokenizer.enable_padding(pad_id=self.tokenizer.token_to_id("[PAD]"))

        # ONNX 推理会话（CPU；量化/GPU 是后续优化方向，面试可提）
        self.session = ort.InferenceSession(
            str(self.model_dir / "model.onnx"),
            providers=["CPUExecutionProvider"],  # C#: SessionOptions + CPU 提供程序
        )

    def __call__(self, input: List[str]) -> List[List[float]]:
        """文本列表 → 512 维向量列表（ChromDB 调用的唯一入口）。

        C#: float[][] Embed(List<string> texts)
        """
        vectors: List[List[float]] = []
        # 分块处理：bench 2000 条时避免一次性把整个矩阵塞进显存/内存
        for i in range(0, len(input), self.BATCH_SIZE):  # C#: for (i = 0; i < n; i += 64)
            batch = input[i : i + self.BATCH_SIZE]  # C#: batch = texts.Skip(i).Take(64)
            vectors.extend(self._embed_batch(batch))
        return vectors

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """单批推理：tokenize → ONNX → mean pooling → L2 归一化。

        教学点（RAG 面试必问「Embedding 怎么算出来的」）：
          1. tokenize：文本 → input_ids / attention_mask（token_type_ids 单句全 0）
          2. ONNX 前向 → last_hidden_state（每 token 一个向量）
          3. mean pooling：所有 token 向量按 attention_mask 加权平均 → 句子向量
          4. L2 归一化：模长变 1，余弦相似度 = 点积，检索更快（bge 官方推荐）
        """
        encodings = self.tokenizer.encode_batch(texts)  # C#: tokenizer.EncodeBatch(texts)

        # C#: 把 Encoding 转成 numpy 矩阵（C# 里是 int[,]）
        input_ids = np.array([e.ids for e in encodings], dtype=np.int64)  # (N, seq)
        attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
        token_type_ids = np.zeros_like(input_ids)  # C#: 单句模型恒为 0

        # ONNX 推理 → last_hidden_state: (N, seq, 512)
        (last_hidden,) = self.session.run(
            None,  # C#: 输出全部节点（这里只有一个）
            {"input_ids": input_ids, "attention_mask": attention_mask, "token_type_ids": token_type_ids},
        )

        # mean pooling：按 attention_mask 加权平均（padding 位置的向量不参与）
        mask = attention_mask[:, :, None].astype(np.float32)  # (N, seq, 1) 广播用
        pooled = (last_hidden * mask).sum(axis=1) / mask.sum(axis=1)  # (N, 512)

        # L2 归一化：向量模长 → 1（这样余弦相似度 = 点积，可直接用 dot 排序）
        pooled = pooled / np.linalg.norm(pooled, axis=1, keepdims=True)

        return pooled.tolist()  # C#: numpy → List<List<float>>
