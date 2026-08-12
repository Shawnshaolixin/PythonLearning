"""业务服务层 —— 把 Week 1 的纯函数计算包成"有状态"的 Web 服务。

C# 对照主线：
  CostService ≈ 注册进 DI 容器的单例服务（services.AddSingleton<CostService>()）：
    - 构造函数加载配置   ≈ 构造函数注入 IConfiguration，应用启动时初始化
    - 内存中的调用列表    ≈ 进程内 List<CallRecord>（真实项目会换成数据库仓储）
    - 每个方法           ≈ Controller 调用的领域服务方法（业务规则放这里）

与 Week 1/2/3 的关系：
  - 复用 Week 1 的 calculator.load_config / calc_call_cost —— 计费公式不重复实现
  - 对比 Week 1：那时是"无状态纯函数"，配置读一次用一次；
    本周是"有状态服务"，配置读一次、调用记录一直累积（POST 会往里加）
"""

import os  # C#: using System.Environment;
from typing import List, Optional

from .models import (
    CallCreate,
    CallOut,
    CallRecord,
    ModelCostOut,
    ModelPrice,
    SummaryOut,
)

try:
    # 场景 1: pytest（tests 从项目根目录导入，src 作为命名空间包）
    from src.ai_cost_calculator import calculator  # type: ignore
except ImportError:
    try:
        # 场景 2: 包已安装到 venv（uv run cost-api）—— 从 site-packages 导入
        from ai_cost_calculator import calculator  # type: ignore[no-redef]
    except ImportError:
        raise RuntimeError(
            "cost_api 依赖 Week 1 的 ai_cost_calculator，请通过 "
            "`uv run cost-api` 或 pytest 运行"
        )


class UnknownModelError(Exception):
    """POST 时引用了配置里不存在的模型。

    C#: 自定义领域异常：public class UnknownModelException : Exception
    教学点：业务规则异常 vs HTTP 异常分离 —— 服务层只抛领域异常，
    由路由层（main.py）翻译成 HTTP 状态码 —— 相当于 C# 的 DomainException → BadRequest。
    """


class CostService:
    """有状态的费用计算服务（进程内单例）。"""

    def __init__(self, config_path: str) -> None:
        """从配置文件加载模型价格 + 已有调用记录。

        C#: public CostService(IConfiguration config) { ... }  —— 构造时初始化
        """
        # 复用 Week 1：读 JSON 文件 + 校验顶层结构（缺少 models/calls 会抛 ValueError）
        data = calculator.load_config(config_path)  # C#: _config.GetSection("Models").Get<List<Model>>()

        # Pydantic 校验加载 —— 比 Week 1 的 dataclass 多一层字段级校验
        # C#: JsonSerializer.Deserialize<List<Model>>(json) 自动应用 [Range] 等校验特性
        self._models: List[ModelPrice] = [
            ModelPrice.model_validate(m) for m in data["models"]
        ]
        # 配置里已有的调用记录 → 内存列表（真实项目这里是数据库表）
        # C#: _calls = new List<CallRecord>(existingCalls);  —— 后续 POST 往里 append
        self._calls: List[CallRecord] = [
            CallRecord.model_validate(c) for c in data.get("calls", [])
        ]
        # 模型名 → 价格 查找表（沿用 Week 1 的字典推导式模式）
        # C#: _modelMap = models.ToDictionary(m => m.Name);
        self._model_map: dict[str, ModelPrice] = {m.name: m for m in self._models}

    # ============================================================
    # 只读接口
    # ============================================================

    def models(self) -> List[ModelPrice]:
        """返回全部模型价格配置。C#: return _models.ToList();（防外部修改）"""
        return list(self._models)  # 返回副本 —— C#: .ToList() 避免外部直接改 List

    def list_calls(self, model: Optional[str], limit: int) -> List[CallRecord]:
        """按模型过滤 + 数量限制，返回调用记录列表。

        C#: _calls.Where(c => model == null || c.Model == model).Take(limit).ToList()
        教学点：这正是 Week 3 学过的 LINQ 语义 —— 只是数据源从文件流变成了内存 List。
        """
        # 推导式过滤 —— C#: .Where(...)
        result = [c for c in self._calls if model is None or c.model == model]
        return result[:limit]  # C#: .Take(limit).ToList()

    def calc_cost(self, call: CallRecord) -> float:
        """计算单次调用费用 —— 直接复用 Week 1 的纯函数。

        C#: Calculator.CalcCallCost(call, _modelMap[call.Model])
        注意：dict 取值是直接下标，调用方保证模型存在（路由层已校验）。
        """
        return calculator.calc_call_cost(call, self._model_map[call.model])

    def get_model_cost(self, name: str) -> Optional[ModelCostOut]:
        """返回某个模型的费用汇总；模型不存在返回 None。

        返回 None 而不是抛异常 —— 让路由层决定映射成 404 还是别的状态码。
        C#: 等价做法：返回 null，Controller 里 if (result is null) return NotFound();
        """
        if name not in self._model_map:  # C#: !_modelMap.ContainsKey(name)
            return None

        # 过滤出该模型的调用，逐个累加 —— C#: Where(...) 后循环累加
        total_in = 0  # C#: var totalIn = 0L;
        total_out = 0
        total_cost = 0.0
        count = 0
        for c in self._calls:  # C#: foreach (var c in _calls)
            if c.model == name:  # C#: if (c.Model == name)
                count += 1
                total_in += c.input_tokens
                total_out += c.output_tokens
                total_cost += self.calc_cost(c)

        # 组装响应模型 —— C#: return new ModelCostOut(name, count, totalIn, totalOut, totalCost);
        return ModelCostOut(
            model=name,
            call_count=count,
            total_input_tokens=total_in,
            total_output_tokens=total_out,
            total_cost=total_cost,
        )

    def summary(self) -> SummaryOut:
        """全局汇总（与 Week 3 summarize 逻辑相同，只是数据源是内存 List）。

        C#: 遍历 List 累加 4 个变量 —— 和 Week 1/3 的汇总一模一样。
        """
        total_calls = 0  # C#: var totalCalls = 0;
        total_in = 0
        total_out = 0
        total_cost = 0.0
        for c in self._calls:  # C#: foreach (var c in _calls)
            total_calls += 1
            total_in += c.input_tokens
            total_out += c.output_tokens
            total_cost += self.calc_cost(c)
        return SummaryOut(
            calls=total_calls,
            input_tokens=total_in,
            output_tokens=total_out,
            total_cost=total_cost,
        )

    # ============================================================
    # 写接口（有状态：往内存列表里追加）
    # ============================================================

    def add_call(self, data: CallCreate) -> CallOut:
        """新增一条调用记录：校验模型存在 → 生成 call_id → 存入内存 → 返回带费用的记录。

        C#: [HttpPost] 的 Service 方法：
            if (!_modelMap.ContainsKey(data.Model)) throw new UnknownModelException(data.Model);
            var record = new CallRecord(_nextId++, data.Model, ...);
            _calls.Add(record);
        """
        if data.model not in self._model_map:  # C#: ContainsKey 检查
            raise UnknownModelError(f"未知模型: {data.model}（可用 GET /api/models 查看）")

        # call_id 自增：取现有最大 id + 1 —— C#: _calls.Max(c => c.CallId) + 1
        next_id = max((c.call_id for c in self._calls), default=0) + 1  # 生成器表达式取最大
        # data.model_dump() 把 Pydantic 对象转成 dict —— C#: JsonSerializer.SerializeToDictionary
        record = CallRecord(call_id=next_id, **data.model_dump())

        self._calls.append(record)  # C#: _calls.Add(record); —— 内存里累积（进程内"数据库"）

        # 响应里带上计算好的费用 —— C#: return new CallOut { ... Cost = CalcCost(record) }
        return CallOut(**record.model_dump(), cost=self.calc_cost(record))
