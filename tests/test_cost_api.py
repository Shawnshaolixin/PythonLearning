"""FastAPI 接口测试 —— Week 4。

C# 对照主线：
  TestClient(app)            ≈ ASP.NET 的 WebApplicationFactory<Program>() —— 内存内启动测试服务器
  client.get("/api/...")     ≈ HttpClient.GetAsync(...)（无需真的跑 uvicorn）
  dependency_overrides       ≈ 测试时替换 DI 注册（等价于给 IHost 换一个假 Service）
  status_code / .json()      ≈ response.StatusCode / JsonSerializer.Deserialize

测试数据（和 conftest 风格一致，但这里用临时文件 + dependency_overrides 注入）：
  gpt-4o      in ¥2.5/1M, out ¥10/1M
  gpt-4o-mini in ¥0.15/1M, out ¥0.6/1M
"""

import json  # C#: using System.Text.Json;
from pathlib import Path  # C#: System.IO.Path

import pytest  # C#: using Xunit;
from fastapi.testclient import TestClient  # C#: WebApplicationFactory<Program>().CreateClient()

from src.cost_api import main  # 与 call_streamer 相同的 pytest 导入方式（src 命名空间包）
from src.cost_api.service import CostService


# ============================================================
# Fixture：为每个测试准备独立的临时配置 + 测试客户端
# ============================================================

@pytest.fixture
def client(tmp_path: Path):  # C#: 每个测试方法的 [SetUp]
    """构造指向临时配置文件的测试客户端（每个测试互不影响）。

    教学点 —— dependency_overrides：
      FastAPI 的依赖替换表，把 get_service 换成返回"临时配置服务"的工厂。
      C# 等价：测试里不用真 appsettings.json，而是覆盖 DI 注册
        （builder.Services.AddSingleton<CostService>(sp => new CostService(testConfig))）。
      这是"依赖注入"最有价值的地方 —— 测试不用改业务代码就能换实现。
    """
    config_file = tmp_path / "config.json"  # C#: Path.Combine(tmpDir, "config.json")
    config_file.write_text(  # C#: File.WriteAllText(path, json, Encoding.UTF8)
        json.dumps(
            {
                "models": [
                    {"name": "gpt-4o", "input_price_per_1m": 2.5, "output_price_per_1m": 10.0},
                    {"name": "gpt-4o-mini", "input_price_per_1m": 0.15, "output_price_per_1m": 0.6},
                ],
                "calls": [
                    {"call_id": 1, "model": "gpt-4o", "input_tokens": 1000, "output_tokens": 500},
                    {"call_id": 2, "model": "gpt-4o", "input_tokens": 2000, "output_tokens": 300},
                    {"call_id": 3, "model": "gpt-4o-mini", "input_tokens": 5000, "output_tokens": 1000},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # 替换依赖：get_service() 返回用临时配置创建的服务
    # C#: 等价于测试启动时 services.Replace(ServiceDescriptor.Singleton<CostService>(...))
    # 注意：必须先创建实例再返回 —— 真实的 get_service 是 lru_cache 单例，
    # 覆盖实现也必须保持"同一个实例"（否则 POST 存的数据 GET 时就读不到了）
    service = CostService(str(config_file))

    def override_get_service() -> CostService:
        return service

    main.app.dependency_overrides[main.get_service] = override_get_service  # C#: DI 覆盖注册

    # TestClient 上下文管理器里发请求 —— C#: await using var app = factory.CreateClient();
    with TestClient(main.app) as c:
        yield c

    # 测试结束清理 —— 恢复原始依赖（避免影响其他测试文件）
    main.app.dependency_overrides.clear()


# ============================================================
# 测试 1-2：基础路由 + 响应模型
# ============================================================

def test_health(client):
    """健康检查：最简单的路由返回固定 JSON。"""
    resp = client.get("/api/health")  # C#: await client.GetAsync("/api/health")
    assert resp.status_code == 200  # C#: Assert.Equal(HttpStatusCode.OK, ...)
    assert resp.json() == {"status": "ok"}


def test_list_models(client):
    """模型价格列表：2 个模型，字段完整。"""
    resp = client.get("/api/models")
    assert resp.status_code == 200
    data = resp.json()  # C#: JsonSerializer.Deserialize<List<Model>>(...)
    assert len(data) == 2
    assert data[0]["name"] == "gpt-4o"
    assert data[0]["input_price_per_1m"] == 2.5  # float 原样返回
    # 响应模型只输出声明的字段 —— C#: 序列化时只输出属性的等价行为
    assert set(data[0].keys()) == {"name", "input_price_per_1m", "output_price_per_1m"}


# ============================================================
# 测试 3-4：路径参数 + 404
# ============================================================

def test_model_cost_ok(client):
    """某模型费用汇总：gpt-4o 两条调用。

    期望值手算：
      in  = 1000 + 2000 = 3000 token
      out = 500 + 300   = 800 token
      cost = 3000/1e6*2.5 + 800/1e6*10 = 0.0075 + 0.008 = 0.0155 元
    """
    resp = client.get("/api/models/gpt-4o/cost")
    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "gpt-4o"
    assert data["call_count"] == 2
    assert data["total_input_tokens"] == 3000
    assert data["total_output_tokens"] == 800
    assert data["total_cost"] == pytest.approx(0.0155)  # 浮点比较用 approx（C#: Assert.Equal(0.0155, c, 5)）


def test_model_cost_not_found(client):
    """不存在的模型 → 404 + 错误信息。"""
    resp = client.get("/api/models/not-exist/cost")
    assert resp.status_code == 404
    assert "not-exist" in resp.json()["detail"]


# ============================================================
# 测试 5：查询参数（过滤 + 限制）
# ============================================================

def test_list_calls_filter(client):
    """按模型过滤调用记录。"""
    resp = client.get("/api/calls", params={"model": "gpt-4o"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    assert all(c["model"] == "gpt-4o" for c in resp.json())


def test_list_calls_limit(client):
    """limit 限制返回条数。"""
    resp = client.get("/api/calls", params={"limit": 1})
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["call_id"] == 1  # 保持插入顺序（C#: List 也是插入序）


def test_list_calls_invalid_limit(client):
    """limit 越界（0 或 10000）→ 422 —— Query(ge/le) 校验。"""
    for bad in (0, 10000):
        resp = client.get("/api/calls", params={"limit": bad})
        assert resp.status_code == 422


# ============================================================
# 测试 6-8：POST 请求体（校验 / 业务规则 / 状态累积）
# ============================================================

def test_create_call_ok(client):
    """新增调用记录：201 + call_id 自增 + 费用计算。

    gpt-4o-mini: in=1000/1e6*0.15 + out=500/1e6*0.6 = 0.00015 + 0.0003 = 0.00045
    """
    resp = client.post(
        "/api/calls",
        json={"model": "gpt-4o-mini", "input_tokens": 1000, "output_tokens": 500},
    )
    assert resp.status_code == 201  # C#: CreatedAtAction
    data = resp.json()
    assert data["call_id"] == 4  # 现有最大 3 + 1 —— 服务端生成
    assert data["cost"] == pytest.approx(0.00045)


def test_create_call_validation_error(client):
    """字段非法（负数 token）→ 422（FastAPI 自动校验，无需手写 if）。"""
    resp = client.post(
        "/api/calls",
        json={"model": "gpt-4o", "input_tokens": -1, "output_tokens": 100},
    )
    assert resp.status_code == 422
    # 422 响应体是 FastAPI 的标准校验错误结构（C#: ModelState 错误列表的等价物）
    assert resp.json()["detail"][0]["loc"] == ["body", "input_tokens"]


def test_create_call_unknown_model(client):
    """模型不存在（业务规则）→ 400（不是 422 —— 字段本身合法，是业务不允许）。"""
    resp = client.post(
        "/api/calls",
        json={"model": "unknown-model", "input_tokens": 100, "output_tokens": 100},
    )
    assert resp.status_code == 400
    assert "unknown-model" in resp.json()["detail"]


def test_create_call_persists(client):
    """POST 后状态累积：再查 summary 能看到新增的记录（服务是有状态的）。"""
    client.post("/api/calls", json={"model": "gpt-4o", "input_tokens": 1000, "output_tokens": 1000})
    resp = client.get("/api/summary")
    assert resp.json()["calls"] == 4  # 3 条初始 + 1 条新增


# ============================================================
# 测试 9：全局汇总
# ============================================================

def test_summary(client):
    """全局汇总。

    期望值手算：
      calls = 3
      in  = 1000+2000+5000 = 8000
      out = 500+300+1000  = 1800
      cost = gpt-4o 0.0155 + gpt-4o-mini (5000/1e6*0.15 + 1000/1e6*0.6 = 0.00075+0.0006=0.00135)
           = 0.01685 元
    """
    resp = client.get("/api/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["calls"] == 3
    assert data["input_tokens"] == 8000
    assert data["output_tokens"] == 1800
    assert data["total_cost"] == pytest.approx(0.01685)
