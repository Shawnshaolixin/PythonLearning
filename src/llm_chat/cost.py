"""费用计算 —— 把 API 返回的 token 用量喂给 Week 1 的计费公式。

C# 对照主线：
  本模块 ≈ 复用 .NET 版 Calculator 的静态方法（HelloWorld 里费用统计的思路）
  关键设计：计费公式只在 Week 1 的 calculator.py 里存在一份，
  这里做的是"适配" —— 把 API 的 (model, prompt_tokens, completion_tokens)
  包装成 Week 1 认识的 CallRecord，再调用 calc_call_cost。
"""

from typing import Optional

try:
    # 场景 1: pytest（tests 从项目根目录导入，src 作为命名空间包）
    from src.ai_cost_calculator import calculator  # type: ignore
    from src.ai_cost_calculator.models import CallRecord  # type: ignore
except ImportError:
    try:
        # 场景 2: 包已安装到 venv（uv run llm-chat）—— 从 site-packages 导入
        from ai_cost_calculator import calculator  # type: ignore[no-redef]
        from ai_cost_calculator.models import CallRecord  # type: ignore[no-redef]
    except ImportError:
        raise RuntimeError(
            "llm_chat 依赖 Week 1 的 ai_cost_calculator，请通过 "
            "`uv run llm-chat ...` 或 pytest 运行"
        )


def usage_cost(
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int,
    config_path: str,
) -> Optional[float]:
    """按 config.json 的价格计算本次调用费用。

    返回 None 表示 config.json 里没有该模型的价格（费用未知，不影响对话）。
    C#: var model = modelMap.GetValueOrDefault(modelName);  // null 表示未配置
        return model is null ? null : Calculator.CalcCallCost(record, model);
    """
    data = calculator.load_config(config_path)  # 复用 Week 1：读 JSON + 校验结构
    # 字典推导式建查找表 —— C#: models.ToDictionary(m => m.Name)
    model_map = {m.name: m for m in calculator.parse_models(data["models"])}

    model = model_map.get(model_name)  # C#: TryGetValue —— 未配置时得到 None
    if model is None:  # C#: if (model is null)
        return None

    # 把 API 的 token 用量包装成 Week 1 认识的 CallRecord，复用计费公式
    # C#: new CallRecord(0, modelName, promptTokens, completionTokens)
    call = CallRecord(
        call_id=0,  # 聊天场景无业务主键，填 0 占位
        model=model_name,
        input_tokens=prompt_tokens,  # 输入 token 即 prompt token
        output_tokens=completion_tokens,  # 输出 token 即 completion token
    )
    # 复用 Week 1 纯函数：费用 = in/1e6*单价 + out/1e6*单价
    return calculator.calc_call_cost(call, model)
