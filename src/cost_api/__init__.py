"""cost_api —— Week 4: AI 费用统计 Web API（FastAPI 入门）。

把 Week 1-3 的命令行费用统计能力包装成 REST API：
  models.py    Pydantic v2 数据模型（请求校验 / 响应建模）
  service.py   业务服务层（有状态单例，复用 Week 1 计算函数）
  main.py      FastAPI 应用（路由 / 参数 / Depends / 异常）
"""
