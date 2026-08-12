"""Pydantic 数据模型 —— 请求校验与响应建模。

C# 对照主线（本周最核心的知识点之一）：
  Pydantic v2 的 BaseModel ≈ C# 的 record + DataAnnotations + FluentValidation 三合一：
    - class ModelPrice(BaseModel)  ≈ public record ModelPrice(string Name, decimal InputPricePer1M, ...)
    - Field(gt=0)                 ≈ [Range(1, double.MaxValue)] 或 FluentValidation 的 RuleFor(...).GreaterThan(0)
    - model_validate(dict)        ≈ JsonSerializer.Deserialize<T>(json) + 自动校验
    - 校验失败                    ≈ ModelState.IsValid == false → ASP.NET 自动返回 400/422

与 Week 1 的对比：
  Week 1 用 dataclass（只存数据不校验），配置结构靠 load_config 里手动 if 判断；
  本周用 Pydantic（存数据 + 自动校验），字段规则写在类型上 —— 这是 Web 层的标配。
"""

from pydantic import BaseModel, Field  # C#: System.Text.Json.Serialization + System.ComponentModel.DataAnnotations


class ModelPrice(BaseModel):
    """模型价格配置（对应 Week 1 的 Model dataclass，多了字段级校验）。

    C#: [Required] public string Name { get; set; }
        [Range(0, double.MaxValue)] public double InputPricePer1M { get; set; }
    """

    name: str = Field(min_length=1)  # C#: [Required] —— 空字符串直接校验失败
    input_price_per_1m: float = Field(gt=0)  # C#: [Range] —— 单价必须大于 0
    output_price_per_1m: float = Field(gt=0)


class CallCreate(BaseModel):
    """POST /api/calls 的请求体 —— 客户端提交的调用记录（没有 call_id，由服务端生成）。

    C#: public record CreateCallRequest(string Model, int InputTokens, int OutputTokens);
        [Range(0, int.MaxValue)] public int InputTokens { get; set; }  —— 负数自动 422

    教学点：校验失败时 FastAPI 自动返回 422 + 详细的字段错误列表，
    不需要手写 if/return —— 对比 C# 的 ModelState 自动绑定校验。
    """

    model: str = Field(min_length=1)  # C#: [Required]
    input_tokens: int = Field(ge=0)  # C#: [Range(0, int.MaxValue)]
    output_tokens: int = Field(ge=0)


class CallRecord(BaseModel):
    """一条调用记录（存库/响应用的完整形态，call_id 由服务端生成）。

    C#: public record CallRecord(int CallId, string Model, int InputTokens, int OutputTokens);
    """

    call_id: int  # C#: 自增主键（真实项目里是数据库自增 ID）
    model: str
    input_tokens: int
    output_tokens: int


class CallOut(CallRecord):
    """响应模型：继承 CallRecord，追加计算好的费用。

    C#: 继承 + 新增属性：public record CallOut(...) : CallRecord(...) { double Cost; }
    教学点：Pydantic 支持类继承 —— 请求体 / 存储体 / 响应体往往是三个类，
    用继承避免重复字段（真实项目里这层常叫 DTO）。
    """

    cost: float  # C#: public double Cost { get; set; }


class ModelCostOut(BaseModel):
    """GET /api/models/{name}/cost 的响应 —— 某个模型的费用汇总。

    C#: public record ModelCostOut(string Model, int CallCount, long TotalInputTokens, ...);
    """

    model: str
    call_count: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost: float


class SummaryOut(BaseModel):
    """GET /api/summary 的响应 —— 全部调用汇总。

    C#: public record SummaryOut(int Calls, long InputTokens, long OutputTokens, double TotalCost);
    """

    calls: int
    input_tokens: int
    output_tokens: int
    total_cost: float
