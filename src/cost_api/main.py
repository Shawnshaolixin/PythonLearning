"""FastAPI 应用入口 —— 路由 / 参数绑定 / 依赖注入 / 异常映射（Week 4 核心）。

C# 对照主线（Minimal API）：
  FastAPI(title=...)                 ≈ WebApplicationBuilder + app.MapGet(...)
  @app.get("/api/...") 装饰器         ≈ app.MapGet("/api/...", handler)
  Path(...)                          ≈ [FromRoute]
  Query(default=...)                 ≈ [FromQuery]
  请求体参数（类型标注 CallCreate）   ≈ [FromBody] + ModelState 自动校验
  Depends(get_service)               ≈ [FromServices] / 构造器注入（DI 容器解析）
  HTTPException(404, detail=...)     ≈ return Results.NotFound(...) / throw
  /docs 自动文档                     ≈ Swashbuckle 的 /swagger 页面
  路由函数返回类型                    ≈ MapGet 的 handler 返回值（FastAPI 用 response_model 约束）

启动方式：uv run cost-api  （uvicorn 在 run() 里程序化启动，见文件末尾）
"""

import os  # C#: using System.Environment;
from functools import lru_cache  # C#: 内存缓存（近似 MemoryCache）—— 保证单例
from typing import List, Optional  # C#: using System.Collections.Generic;

from fastapi import Depends, FastAPI, HTTPException, Path, Query  # C#: Microsoft.AspNetCore.*
from pydantic import BaseModel  # C#: 无直接等价 —— FastAPI 用它生成 OpenAPI 文档

try:
    from .models import CallCreate, CallOut, CallRecord, ModelCostOut, ModelPrice, SummaryOut
    from .service import CostService, UnknownModelError
except ImportError:
    # 直接运行本文件时（python main.py）—— 与 Week 2/3 相同的回退模式
    from models import (  # type: ignore[no-redef]
        CallCreate,
        CallOut,
        CallRecord,
        ModelCostOut,
        ModelPrice,
        SummaryOut,
    )
    from service import CostService, UnknownModelError  # type: ignore[no-redef]


# 创建应用实例 —— 相当于 C#: var builder = WebApplication.CreateBuilder(args);
# title/description/version 会显示在 /docs 页面上 —— C#: builder.Services.AddSwaggerGen 里配的文档信息
app = FastAPI(
    title="AI 费用统计 Web API",
    description="把 Week 1-3 的命令行费用统计能力包装成 REST API（Week 4 练习）",
    version="0.1.0",
)


@lru_cache
def get_service() -> CostService:
    """FastAPI 依赖（Dependency）—— 提供 CostService 单例。

    C#: services.AddSingleton<CostService>(sp =>
            new CostService(Configuration.GetValue<string>("CostApi:ConfigPath") ?? "config.json"));

    配置来源：环境变量 COST_API_CONFIG，缺省 "config.json"。
    C#: Configuration["CostApi:ConfigPath"] —— 环境变量和 appsettings 可以互相覆盖。
    lru_cache 保证只创建一次 —— 这正是"单例"在 Python 里的最简写法。
    """
    config_path = os.environ.get("COST_API_CONFIG", "config.json")  # C#: GetEnvironmentVariable(...)
    return CostService(config_path)


# ============================================================
# 路由 1: 健康检查（最简单的路由 —— 无参数、固定返回）
# ============================================================

@app.get("/api/health")
def health() -> dict:
    """健康检查：返回 {"status": "ok"}。

    C#: app.MapGet("/api/health", () => Results.Ok(new { status = "ok" }));
    """
    return {"status": "ok"}


# ============================================================
# 路由 2: 模型价格列表（无参数，返回配置里所有模型）
# ============================================================

@app.get("/api/models", response_model=List[ModelPrice])
def list_models(service: CostService = Depends(get_service)) -> List[ModelPrice]:
    """列出全部模型价格配置。

    C#: app.MapGet("/api/models", (CostService svc) => svc.Models());
        —— service 由 DI 容器注入（依赖注入），handler 不用自己 new
    response_model 只做输出约束/文档生成，不会真的过滤字段（这里类型一致）。
    """
    return service.models()


# ============================================================
# 路由 3: 某模型费用汇总（路径参数 + 404 处理）
# ============================================================

@app.get("/api/models/{model_name}/cost", response_model=ModelCostOut)
def model_cost(
    model_name: str = Path(..., description="模型名称（在 /api/models 中查看）"),  # C#: [FromRoute]
    service: CostService = Depends(get_service),  # C#: [FromServices] CostService svc
) -> ModelCostOut:
    """返回某个模型的调用次数 / token / 总费用；模型不存在返回 404。

    C#: app.MapGet("/api/models/{name}/cost", (string name, CostService svc) =>
            svc.GetModelCost(name) is { } result
                ? Results.Ok(result)
                : Results.NotFound($"未找到模型: {name}"));
    教学点：服务层返回 None（业务结果），路由层翻译成 HTTP 状态码 ——
    C# 里等价于"返回 null 的 Service + Controller 里判断 → NotFound()"。
    """
    result = service.get_model_cost(model_name)
    if result is None:  # C#: if (result is null)
        raise HTTPException(status_code=404, detail=f"未找到模型: {model_name}")  # C#: NotFound()
    return result


# ============================================================
# 路由 4: 调用记录列表（查询参数 + 默认值）
# ============================================================

@app.get("/api/calls", response_model=List[CallRecord])
def list_calls(
    model: Optional[str] = Query(None, description="按模型名过滤（不传返回全部）"),  # C#: [FromQuery] string? model
    limit: int = Query(100, ge=1, le=1000, description="最多返回条数"),  # C#: [FromQuery] int limit = 100（可加校验）
    service: CostService = Depends(get_service),
) -> List[CallRecord]:
    """查询调用记录，支持 model 过滤和 limit 限制。

    C#: app.MapGet("/api/calls", (string? model, int limit, CostService svc) => ...)
    教学点：Query(...) 里能带默认值和范围校验（ge=1, le=1000）——
    传 limit=0 或 limit=10000 会返回 422 —— C#: [Range] + ModelState。
    """
    return service.list_calls(model, limit)


# ============================================================
# 路由 5: 新增调用记录（请求体 + Pydantic 校验 + 领域异常映射）
# ============================================================

@app.post("/api/calls", response_model=CallOut, status_code=201)
def create_call(
    data: CallCreate,  # C#: [FromBody] CreateCallRequest data —— 绑定失败自动 422
    service: CostService = Depends(get_service),
) -> CallOut:
    """新增一条调用记录：校验通过 → 生成 call_id → 存入内存 → 返回带费用的记录。

    三个状态码的教学点：
      - 请求体字段非法（如 input_tokens 为负）→ FastAPI 自动返回 422，无需手写
      - 模型不存在（业务规则）→ 服务层抛 UnknownModelError → 这里翻译成 400
      - 成功 → 201 Created（C#: [HttpPost] 默认 200，RESTful 约定新建资源返回 201）
    """
    try:
        return service.add_call(data)
    except UnknownModelError as e:  # C#: catch (UnknownModelException ex) → BadRequest(ex.Message)
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================
# 路由 6: 全局汇总（复用 Week 1-3 的计算逻辑）
# ============================================================

@app.get("/api/summary", response_model=SummaryOut)
def summary(service: CostService = Depends(get_service)) -> SummaryOut:
    """全局汇总：总调用次数 / 总 token / 总费用。

    C#: app.MapGet("/api/summary", (CostService svc) => svc.Summary());
    逻辑本体在 service.py —— 路由层只做"参数绑定 + 响应建模"。
    """
    return service.summary()


# ============================================================
# 程序化启动：uv run cost-api
# ============================================================

def run() -> None:
    """控制台入口 —— 启动 uvicorn 开发服务器。

    C#: Program.cs 末尾的 app.Run() —— 这里用 uvicorn 程序化启动。
    生产部署时通常不用这个入口，而是直接 `uvicorn cost_api.main:app`。
    """
    import uvicorn  # C#: 无直接等价 —— Python 的 ASGI 服务器（类似 Kestrel）

    uvicorn.run("cost_api.main:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":  # C#: Main() 入口方法
    run()
