# ai-cost-calculator

读取 JSON 配置、统计 LLM API 调用费用的命令行工具。

> Week 1 练习项目：Python 工程环境 + 基础语法（dataclass / typing / 推导式 / JSON / 异常处理）。

## 环境要求

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)（推荐）

## 快速开始

```bash
# 创建虚拟环境并安装项目
uv sync

# 运行：统计费用（表格输出）
uv run ai-cost-calculator --config config.json

# 运行：JSON 结构化输出
uv run ai-cost-calculator --config config.json --json
```

## 项目结构

```
src/ai_cost_calculator/   # Week 1: 费用统计器（函数式）
  models.py      数据模型（dataclass）
  calculator.py  读 JSON + 计算逻辑
  cli.py         命令行入口（argparse）
src/cost_reporter/        # Week 2: 账单报告生成器（面向对象）
  errors.py      自定义异常体系
  report.py      CostReport 类（@property / 魔术方法）
  formatters.py  格式化器（抽象基类 + 继承多态）
  cli.py         命令行入口（--format 参数）
src/call_streamer/        # Week 3: 大日志流费用分析器（生成器与迭代器）
  generators.py  知识点教学（迭代协议 / yield / 惰性求值 / yield from）
  pipeline.py    流式管道（读行 → 解析 → 过滤 → 算费用 → 聚合）
  cli.py         命令行入口（--log / --model / --top / --head）
  sample_gen.py  示例日志生成器（--lines 100000）
src/cost_api/             # Week 4: AI 费用统计 Web API（FastAPI 入门）
  models.py      Pydantic v2 模型（请求校验 / 响应建模）
  service.py     业务服务层（有状态单例，复用 Week 1 计算函数）
  main.py        FastAPI 应用（路由 / 参数绑定 / Depends / 异常映射）
src/llm_chat/             # Week 5: LLM 命令行聊天工具（LLM API 调用 + 流式输出）
  chat.py        对话核心（OpenAI SDK / 流式生成器 / 消息历史管理）
  cost.py        Token 用量 → 费用（复用 Week 1 计费公式）
  cli.py         命令行入口（uv run llm-chat）
config.json      示例配置文件
```

## 配置格式

```json
{
  "models": [
    { "name": "模型名", "input_price_per_1m": 输入单价, "output_price_per_1m": 输出单价 }
  ],
  "calls": [
    { "call_id": 1, "model": "模型名", "input_tokens": 1200, "output_tokens": 350 }
  ]
}
```

费用公式：`输入token/1e6 * 输入单价 + 输出token/1e6 * 输出单价`

---

## Week 2：账单报告生成器（面向对象进阶）

> 在 Week 1 基础上重构扩展，练习 Python 类体系 vs C# 的差异：
> `class`/`self`（构造函数/`this`）、`@property`（get-only 属性）、魔术方法（`ToString`/`Equals`）、
> 自定义异常、继承 + 抽象方法（`abstract class`/`override`）。

### 运行

```bash
# 文本表格（默认）
uv run cost-reporter --config config.json

# Markdown 表格
uv run cost-reporter --config config.json --format markdown

# JSON
uv run cost-reporter --config config.json --format json
```

### 与 Week 1 的关系

- **复用**：`CostReport` 类的解析/汇总逻辑直接调用 Week 1 的 `calculator.py`（类做编排，函数做计算）
- **新增**：未知模型会通过 `validate()` 抛 `UnknownModelError`（Week 1 是静默计 0 费用）—— fail-fast
- **测试**：复用 Week 1 conftest.py 的 fixture

---

## Week 3：大日志流费用分析器（生成器与迭代器）

> 场景：生产环境每天几十万行 LLM 调用日志（JSONL），内存装不下 → 用生成器搭"水管"，
> 数据流式经过，内存占用 O(1)。这是 **LLM 流式输出（SSE）的底层机制**，Week 5 会用到。

### 知识点（C# 对照主线）

| Python | C# 等价 |
|--------|---------|
| 迭代协议 `__iter__` / `__next__` / `StopIteration` | `IEnumerable<T>` / `IEnumerator<T>` + `MoveNext()` |
| 生成器函数（函数体含 `yield`） | 迭代器方法（含 `yield return`） |
| 惰性求值（用到才执行） | LINQ 延迟执行（不 `ToList()` 时） |
| 生成器表达式 `(x for x in xs)` | `xs.Select(...)` 不 ToList |
| `yield from sub` | `foreach (var x in sub) yield return x;` |
| `itertools.islice` / `takewhile` | LINQ `.Take(n)` / `.TakeWhile(...)` |
| 无限序列（`while True: yield`） | LINQ 无法用 List 表达，IEnumerable 可以 |
| `next(g, default)` | `enumerator.MoveNext() ? Current : default` |

**最核心一句话：先搭管道、后放水。** 构建管道时什么都不算，只有 for 消费时才逐个求值。

### 运行

```bash
# 1. 生成 10 万行示例日志（固定随机种子，可复现）
uv run call-streamer-gen --lines 100000 --out calls.jsonl

# 2. 全量分析：汇总 + Top-3 模型（10 万行约 0.6 秒）
uv run call-streamer --log calls.jsonl --config config.json

# 3. 只统计某个模型
uv run call-streamer --log calls.jsonl --config config.json --model qwen-max

# 4. JSON 输出
uv run call-streamer --log calls.jsonl --config config.json --top 2 --json

# 5. 惰性演示：只读取前 3 行（islice 短路）
uv run call-streamer --log calls.jsonl --config config.json --head 3
```

### 管道结构（对比 LINQ 链）

```
iter_lines → parse_records → filter_by_model → with_cost
     ↓                        ↓                   ↓
File.ReadLines          .Select(Deserialize)  .Select(c => (c, cost))
     ↓
summarize（全量汇总）/ top_models（Top-K 聚合）
```

两个关键设计决策：
1. **生成器一次性**：同一个流只能消费一次 → 汇总和 Top-K 各自重新搭一遍管道（文件重读）
2. **内存与日志行数无关**：聚合用 dict 按模型累加，内存只与模型种类数相关

### 观察

跑一次 10 万行示例：`deepseek-v4-flash` 调用最多（6 万次）但费用最低（29 元），
`deepseek-v4-pro` 调用少（3 万次）却花掉大头（108 元）—— 贵模型省着用，这就是成本控制。

### 测试

`tests/test_call_streamer.py` 共 28 个用例，重点验证"惰性"：
- 副作用计数证明函数体在 `next()` 前不执行
- 无限序列 + `islice` 能跑完（急切实现会死循环）
- `iter_lines` 传不存在的文件不报错，`list()` 消费时才抛
- 大文件（5 万行）流式处理正确性

---

## Week 4：AI 费用统计 Web API（FastAPI 入门）

> 把 Week 1-3 的命令行工具包装成 REST API。本周是**从"脚本"到"服务"的转折点**——
> Python 的 Web 后端能力和 .NET 的对应关系极强，重点感受"同样的分层思想，换一种写法"。

### 运行

```bash
# 1. 启动开发服务器（FastAPI 自动加载 config.json）
uv run cost-api

# 2. 浏览器打开自动生成的 API 文档（≈ Swashbuckle /swagger）
#    http://127.0.0.1:8000/docs
```

接口一览（Swagger 里可以直接"Try it out"）：

| 接口 | 作用 | 参数教学点 |
|------|------|-----------|
| `GET /api/health` | 健康检查 | 最简单路由 |
| `GET /api/models` | 模型价格列表 | 无参数 |
| `GET /api/models/{name}/cost` | 某模型费用汇总 | 路径参数 + 404 |
| `GET /api/calls?model=&limit=` | 调用记录查询 | 查询参数 + 默认值 |
| `POST /api/calls` | 新增调用记录 | 请求体校验 422 / 业务规则 400 / 成功 201 |
| `GET /api/summary` | 全局汇总 | 复用 Week 1-3 计算逻辑 |

### 知识点（C# 对照主线）

| Python / FastAPI | C# 等价 |
|------------------|---------|
| `@app.get("/api/...")` 装饰器 | `app.MapGet("/api/...", handler)`（Minimal API） |
| Pydantic v2 `BaseModel` + `Field(gt=0)` | record + DataAnnotations（`[Required]` / `[Range]`）+ FluentValidation 合体 |
| 请求体参数类型标注 → 自动 422 | `[FromBody]` + ModelState 自动绑定校验 |
| `Path(...)` / `Query(default)` | `[FromRoute]` / `[FromQuery]` |
| `Depends(get_service)` | DI 容器解析（`[FromServices]` / 构造器注入） |
| `HTTPException(404, detail=...)` | `Results.NotFound(...)` |
| `/docs` 自动文档 | Swashbuckle `/swagger` |
| `uvicorn`（ASGI 服务器） | Kestrel |
| 环境变量 `COST_API_CONFIG` | `IConfiguration` / 环境变量覆盖 |

**三个关键设计决策**：

1. **分层**：`models.py`（数据/校验）→ `service.py`（业务规则）→ `main.py`（路由/HTTP）。
   服务层只抛领域异常 `UnknownModelError`，路由层翻译成 HTTP 状态码 —— 和 C# 的 Controller 调 Service 一致。
2. **复用 Week 1**：`service.py` 直接调用 `calculator.load_config` / `calc_call_cost`，计费公式只写一次。
   区别：Week 1 是"无状态纯函数"，本周是"有状态单例"——POST 的记录累积在内存 List 里（真实项目会换成数据库）。
3. **校验层级**：字段级校验（负数 token → 422）由 Pydantic 自动完成；业务级校验（未知模型 → 400）在服务层。
   这和 C# 的"ModelState 管格式、业务代码管规则"分工完全相同。

### 测试

`tests/test_cost_api.py` 共 12 个用例，核心是 `TestClient`（≈ `WebApplicationFactory<Program>`）：
- **`dependency_overrides` 替换依赖**：不读真实 `config.json`，注入指向临时配置的服务 —— 等价于测试时替换 DI 注册
- 覆盖三态码：422（字段非法）/ 400（模型不存在）/ 404（路径参数找不到）
- 验证服务是有状态的：POST 后 summary 能看到新增记录

---

## Week 5：LLM 命令行聊天工具（LLM API 调用 + 流式输出）

> 把 HelloWorld 示例 1（.NET 聊天循环）用 Python + OpenAI SDK 重写，并加上多模型切换 /
> 流式输出 / Token 费用统计 / 历史保存加载。**前 4 周的知识点在这里汇合**：
> Week 1 的计费公式、Week 3 的生成器（流式输出的底层机制）、Week 4 的分层思想。

### 环境准备

```bash
# 1. 设置 DeepSeek API key（DeepSeek 开放平台申请: https://platform.deepseek.com）
export DEEPSEEK_API_KEY=sk-xxx      # Windows cmd: set DEEPSEEK_API_KEY=sk-xxx

# 2. 可选：换其他 OpenAI 兼容服务（默认 DeepSeek）
export DEEPSEEK_BASE_URL=https://api.deepseek.com
```

### 运行

```bash
uv run llm-chat                                    # 默认 deepseek-chat，流式
uv run llm-chat --model deepseek-reasoner          # 切换模型
uv run llm-chat --no-stream                        # 非流式（一次等完整回复）
uv run llm-chat --system "你是 Python 老师" --temperature 0.5
uv run llm-chat --load history.json                # 加载历史继续聊
uv run llm-chat --save history.json                # 退出时保存历史
```

聊天中的命令：`/exit` 退出 · `/clear` 清空历史 · `/save 路径` 保存 · `/load 路径` 加载

每轮对话后打印 token 用量 + 费用。**费用统计复用 Week 1 的计费公式**：
`config.json` 里配置模型价格（如 `deepseek-chat`）后即可显示真实费用，未配置会给出提示。

### 知识点（C# 对照主线）

| Python / OpenAI SDK | C# 等价 |
|---------------------|---------|
| `OpenAI(api_key, base_url)` | `new OpenAIClient(apiKey, options)`（同一套 API 设计） |
| `client.chat.completions.create(...)` | `client.Chat.Completions.CreateAsync(...)` |
| messages 列表（system/user/assistant） | `List<ChatMessage>` |
| `stream=True` 返回可迭代对象 | `Stream = true` 的流式响应 |
| 逐块 `chunk.choices[0].delta.content` | `ContentUpdate[0].Text`（`await foreach`） |
| `resp.usage.prompt_tokens` | `resp.Usage.PromptTokens` |
| `stream_options={"include_usage": True}` | `StreamOptions = new() { IncludeUsage = true }` |

**两个关键设计**：

1. **流式 = Week 3 生成器的实战应用**：`stream_reply` 是生成器函数，逐块 `yield` 文本。
   CLI 用 `consume_stream` 边收边打印 —— 期间还学了一个冷知识：**生成器的 return 值不在
   生成器对象上，而是藏在迭代结束时抛出的 `StopIteration` 异常里（`e.value`）**，
   for 循环会把它吞掉，所以要手动 `next()` + 捕获。
2. **测试不花钱**：`tests/test_llm_chat.py` 全程用假响应（`SimpleNamespace` 构造假 chunk），
   等价于 C# 的 Moq —— 函数签名即依赖边界，测试端替换成假实现即可。10 个用例覆盖
   流式逐块输出、空块跳过、usage 缺失兜底、历史保存/加载/过滤、上下文裁剪、费用换算。

### 测试

```bash
uv run pytest           # 104 个用例全部通过（含 Week 1-5）
```
