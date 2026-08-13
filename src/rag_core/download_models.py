"""下载本地 Embedding 模型（bge-small-zh-v1.5, ONNX）。

运行：uv run python -m rag_core.download_models

为什么需要：模型文件 ~95MB 已加入 .gitignore（不进版本库），
新环境 clone 后第一次跑 rag-demo / rag-bench 前先执行本脚本。

为什么用 hf-mirror.com：官方 HuggingFace 在国内直连不稳定，
hf-mirror 是国内镜像（仅作为下载源，模型文件本身与官方一致）。
"""

import sys  # C#: Environment
import urllib.request  # C#: HttpClient（标准库，零额外依赖）
from pathlib import Path  # C#: System.IO

from rag_core.embeddings import BgeSmallZh  # C#: 复用模型路径常量

# (文件名, 仓库内相对路径) —— Xenova 是 transformers.js 社区导出的 ONNX 版本
FILES = [
    ("model.onnx", "onnx/model.onnx"),
    ("tokenizer.json", "tokenizer.json"),
    ("config.json", "config.json"),
]
BASE_URL = "https://hf-mirror.com/Xenova/bge-small-zh-v1.5/resolve/main"  # C#: const string


def ensure_model(model_dir: Path = BgeSmallZh.MODEL_DIR) -> None:
    """缺什么补什么：逐个检查 + 下载模型文件。

    C#: void EnsureModel(DirectoryInfo modelDir) —— 首次运行初始化资源
    """
    missing = [name for name, _ in FILES if not (model_dir / name).exists()]  # C#: Where + Select
    if not missing:  # C#: if (missing.Count == 0)
        print(f"模型已就绪：{model_dir}")
        return

    print(f"缺少 {len(missing)} 个文件，开始下载（模型 ~95MB，视网速 1-3 分钟）…")
    model_dir.mkdir(parents=True, exist_ok=True)  # C#: Directory.CreateDirectory（递归建目录）

    for name, repo_path in FILES:  # C#: foreach (var file in FILES)
        target = model_dir / name
        if target.exists():  # C#: 已存在的跳过（断点续传式跳过）
            continue
        url = f"{BASE_URL}/{repo_path}"  # C#: $"{BaseUrl}/{repoPath}"
        print(f"  下载 {name} …")
        urllib.request.urlretrieve(url, target)  # C#: await HttpClient.GetByteArrayAsync + File.WriteAllBytes
        print(f"    OK（{target.stat().st_size / 1024 / 1024:.1f} MB）")  # C#: 文件大小（MB）


def main() -> None:
    """入口。

    C#: static void Main()
    """
    try:
        ensure_model()
    except Exception as e:  # C#: catch (Exception ex)
        print(f"下载失败：{e}（检查网络后重试；也可手动下载模型放到 {BgeSmallZh.MODEL_DIR}）")
        sys.exit(1)  # C#: Environment.Exit(1)


if __name__ == "__main__":  # C#: Main() 入口方法
    main()
