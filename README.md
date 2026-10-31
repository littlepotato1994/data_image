# Codex 3D Artifact API

一个统一的 JSON/Base64 HTTP 接口，提供两个功能：

- `render_3d_views`：输入一至六张参考图，通过已登录 ChatGPT 的 Codex 内置 ImageGen 输出六个方向的 3D 公仔图。
- `reconstruct_stl`：输入多视图、尺寸和要求，调用非交互 Codex，在隔离任务目录中实际生成 STL、网格预览、验证报告和可编辑源文件。

两个功能都使用 `codex exec --json`，服务从 JSONL 事件中读取累计 token usage。它是 token 数量，不是费用估算。
如果特定 Codex CLI 版本或账户后端没有在事件中提供 usage，数值返回 0，并在 `warnings` 中明确说明。

## 运行条件

- Python 3.11+；建议 Python 3.12。
- 已安装并可运行 `codex` CLI，且已通过 `codex login` 登录 ChatGPT。图片与 STL 模式均使用该登录状态。
- 本机 Codex 必须提供内置 `imagegen` 技能和 `image_gen` 工具；不需要 `OPENAI_API_KEY` 或 API 余额。
- 生产环境建议在服务端配置 `SERVICE_API_KEY`，调用方通过 `X-API-Key` 请求头发送。该密钥只保护本服务，不用于调用 OpenAI。

本地启动：

```bash
cd /Users/lihaihui/Desktop/code/codex-3d-api
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export SERVICE_API_KEY='your-service-key'
export CODEX_BIN='/absolute/path/to/codex'
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

打开 `http://localhost:8000/docs` 可查看并直接调用 OpenAPI/Swagger 接口。

完整中文请求、响应和错误码说明见 [API.md](API.md)。

Docker：

```bash
docker build -t codex-3d-api .
docker run --rm -p 8000:8000 \
  -e SERVICE_API_KEY='your-service-key' \
  -v "$PWD/var:/app/var" \
  codex-3d-api
```

## 接口

`POST /v1/generate`

请求为 JSON。图片的 `data_base64` 可使用纯 Base64 或 `data:image/png;base64,...`。调用方可以选择 `codex_model`，默认值为 `gpt-5.6-sol`。图片工具由已登录的 ChatGPT/Codex 管理，接口不接受 `image_model` 或 OpenAI API Key。最大输入、输出和超时可通过 `.env.example` 中的环境变量调整。

长任务推荐使用异步接口：

- `POST /v1/jobs`：提交请求，立即返回 `job_id`（HTTP 202）。
- `GET /v1/jobs/{job_id}`：查询 `queued`、`running`、`completed` 或 `failed`。
- `GET /v1/jobs/{job_id}/result`：完成后获取与同步接口相同的 Base64 响应。

本机默认一次只执行一个 Codex 任务，后续任务保持 `queued`，避免并发挤占 ChatGPT 使用额度。完整轮询客户端见 [examples/async_client.py](examples/async_client.py)。

图片六视图示例见 [examples/render_request.json](examples/render_request.json)：

```bash
curl -sS http://localhost:8000/v1/generate \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: your-service-key' \
  --data-binary @examples/render_request.json > render_response.json
```

STL 示例见 [examples/stl_request.json](examples/stl_request.json)：

```bash
curl -sS http://localhost:8000/v1/generate \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: your-service-key' \
  --data-binary @examples/stl_request.json > stl_response.json
```

响应结构：

```json
{
  "request_id": "...",
  "mode": "reconstruct_stl",
  "summary": "...",
  "classification": "simplified_initial",
  "dimensions_mm": {"width": 40.72, "depth": 24.47, "height": 40.0},
  "artifacts": [
    {
      "kind": "stl",
      "filename": "model.stl",
      "mime_type": "model/stl",
      "data_base64": "...",
      "byte_length": 15645700,
      "sha256": "..."
    }
  ],
  "usage": {
    "codex": {
      "input_tokens": 12000,
      "cached_input_tokens": 3000,
      "output_tokens": 4200,
      "total_tokens": 16200
    },
    "image_generation": {
      "input_tokens": 0,
      "output_tokens": 0,
      "total_tokens": 0
    },
    "total_tokens": 16200,
    "note": "Token counts are provider-reported usage; they are not a price estimate."
  },
  "warnings": []
}
```

提取 Base64 文件：

```bash
jq -r '.artifacts[] | select(.filename == "model.stl") | .data_base64' \
  stl_response.json | base64 --decode > model.stl
```

也可以使用只依赖 Python 标准库的完整客户端，它会编码输入图片、调用接口并解码全部产物：

```bash
python3 examples/client.py render_3d_views reference.png \
  --requirement '生成同一实体的六个方向，纯白背景'

python3 examples/async_client.py render_3d_views reference.png \
  --requirement '生成同一实体的六个方向，纯白背景'

python3 examples/client.py reconstruct_stl front.png back.png left.png right.png \
  --codex-model 'gpt-5.6-sol' \
  --height 40 \
  --requirement '按参考比例生成单件实心模型，保留一体式挂孔'
```

## 行为与限制

图片功能在一个临时 Codex 任务中连续调用内置 ImageGen，并要求使用参考图和之前生成结果作为一致性锚点。它不使用 Platform Images API。内置工具可能无法严格满足请求的像素尺寸，且生成结果仍可能出现跨视角差异。

STL 功能使用 Codex 代理循环：它读取参考图，在任务目录内创建建模代码、导出 STL，再生成来自实际 STL 的预览和验证报告。结果质量依赖参考图、尺寸、模型、运行环境和任务时限。服务要求 Codex 明确标记 `simplified_initial` 或 `detailed_reconstruction`，不会把效果图改名为 STL。

当前端点是同步长任务接口。图片可能需要数分钟，STL 可能更久。生产部署建议在外层增加作业队列、对象存储和状态查询接口，并避免让网关记录完整 Base64 请求或响应。服务默认任务完成后删除临时工作目录；设置 `KEEP_JOBS=true` 可保留调试文件。

Codex 使用 `workspace-write` 沙箱和自动审批，不使用绕过沙箱的危险参数。用户的 `requirement` 被放进明确的数据边界；仍应在互联网边界前设置身份认证、配额、请求大小限制和审计日志。

## 测试

测试不调用 OpenAI，也不消耗 token：

```bash
pytest -q
```

真实连通测试会消耗 ChatGPT/Codex 使用额度，应使用示例请求显式执行。

## 官方资料

- [Codex as a platform](https://developers.openai.com/blog/codex-as-a-platform)
- [Codex authentication](https://learn.chatgpt.com/docs/auth?surface=cli)
- [Counting tokens](https://developers.openai.com/api/docs/guides/token-counting)

