# Codex 3D Artifact API 接口文档

## 1. 接口概述

本服务通过同一个 HTTP 接口提供两种能力：

- `render_3d_views`：根据参考图片生成同一角色或产品的六方向 3D 效果图。
- `reconstruct_stl`：根据多视图参考图片和目标尺寸生成适合 3D 打印的 STL 文件。

业务接口：

```http
POST /v1/generate
Content-Type: application/json
```

本地默认地址：

```text
http://127.0.0.1:8000/v1/generate
```

在线 Swagger 文档：

```text
http://127.0.0.1:8000/docs
```

## 2. 接口鉴权

如果服务端配置了 `SERVICE_API_KEY`，调用方必须通过请求头提交服务访问密钥：

```http
X-API-Key: 你的服务访问密钥
```

`X-API-Key` 只用于访问本服务，与 OpenAI API Key 不同。

调用方不提交 OpenAI API Key。图片功能使用服务器环境变量 `OPENAI_API_KEY`，STL 功能使用服务器本机的 Codex/ChatGPT 登录状态。服务器凭据不会出现在接口请求或响应中。服务端和反向代理仍不应记录完整请求正文，避免泄露图片 Base64。

## 3. 通用图片格式

请求中的每张图片使用以下结构：

```json
{
  "mime_type": "image/png",
  "data_base64": "图片BASE64"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `mime_type` | string | 否 | 支持 `image/png`、`image/jpeg`、`image/webp`，默认 `image/png`。 |
| `data_base64` | string | 是 | 图片原始 Base64；也接受 `data:image/png;base64,...` 格式。 |

每次请求最少上传 1 张、最多上传 6 张图片。

## 4. 功能一：生成六方向 3D 图片

### 4.1 请求示例

```json
{
  "mode": "render_3d_views",
  "image_model": "gpt-image-2",
  "images": [
    {
      "mime_type": "image/png",
      "data_base64": "图片BASE64"
    }
  ],
  "requirement": "PVC公仔质感，保留角色特征和挂孔",
  "views": [
    "front",
    "back",
    "left",
    "right",
    "left_front",
    "right_rear"
  ],
  "image_size": "1024x1024",
  "image_quality": "high"
}
```

### 4.2 请求字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | string | 是 | 无 | 固定为 `render_3d_views`。 |
| `image_model` | string | 否 | `gpt-image-2` | 本次请求使用的图片生成模型。 |
| `images` | array | 是 | 无 | 1～6 张外观或结构参考图。 |
| `requirement` | string | 是 | 无 | 用户对材质、细节、背景等补充要求，长度 1～30000 个字符。 |
| `views` | array | 否 | 六个标准视角 | 需要生成的视角；每个视角生成一张图片。 |
| `image_size` | string | 否 | `1024x1024` | 可选 `1024x1024`、`1536x1024`、`1024x1536`、`auto`。 |
| `image_quality` | string | 否 | `high` | 可选 `low`、`medium`、`high`、`auto`。 |

### 4.3 视角取值

| 值 | 含义 |
| --- | --- |
| `front` | 正面水平正视。 |
| `back` | 相对正面旋转 180° 的背面。 |
| `left` | 角色自身左侧 90°。 |
| `right` | 角色自身右侧 90°。 |
| `left_front` | 角色自身左前方约 45°。 |
| `right_rear` | 角色自身右后方约 45°。 |

### 4.4 curl 示例

```bash
curl -sS http://127.0.0.1:8000/v1/generate \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: 你的服务访问密钥' \
  --data-binary @examples/render_request.json \
  > render_response.json
```

生成结果位于响应的 `artifacts` 数组中，每张图片的 `kind` 为 `image`，`mime_type` 为 `image/png`。

## 5. 功能二：多视图重建 STL

### 5.1 请求示例

```json
{
  "mode": "reconstruct_stl",
  "codex_model": "gpt-5.6-sol",
  "images": [
    {
      "mime_type": "image/png",
      "data_base64": "正面图BASE64"
    },
    {
      "mime_type": "image/png",
      "data_base64": "背面图BASE64"
    }
  ],
  "requirement": "生成适合3D打印的单件实体模型",
  "dimensions_mm": {
    "width": 40,
    "depth": 40,
    "height": 40,
    "preserve_reference_proportions": true
  },
  "include_editable_source": true
}
```

### 5.2 请求字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | string | 是 | 无 | 固定为 `reconstruct_stl`。 |
| `codex_model` | string | 否 | `gpt-5.6-sol` | 本次 STL 重建使用的 Codex 模型。 |
| `images` | array | 是 | 无 | 1～6 张多视图参考图。建议依次传正面、背面、角色左侧、角色右侧、左前 45°、右后 45°。 |
| `requirement` | string | 是 | 无 | 用户的建模、打印及细节要求。 |
| `dimensions_mm` | object | 是 | 无 | 目标尺寸，单位按毫米解释。 |
| `include_editable_source` | boolean | 否 | `true` | 是否要求返回可编辑建模源文件 `source.zip`。 |

### 5.3 尺寸字段

```json
{
  "width": 40,
  "depth": 40,
  "height": 40,
  "preserve_reference_proportions": true
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `width` | number | 三者至少一个 | 模型左右方向最大尺寸，范围大于 0 且不超过 1000 mm。 |
| `depth` | number | 三者至少一个 | 模型前后方向最大尺寸，范围大于 0 且不超过 1000 mm。 |
| `height` | number | 三者至少一个 | 模型底部到顶部最大尺寸，范围大于 0 且不超过 1000 mm。 |
| `preserve_reference_proportions` | boolean | 否 | 默认 `true`。尺寸冲突时优先保留参考图比例，避免角色被明显拉宽、压扁或拉长。 |

当 `preserve_reference_proportions` 为 `true`，输入的三个尺寸与参考图比例冲突时，最终模型可能不会同时严格等于三个目标尺寸，实际尺寸以响应中的 `dimensions_mm` 和验证报告为准。

### 5.4 curl 示例

```bash
curl -sS http://127.0.0.1:8000/v1/generate \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: 你的服务访问密钥' \
  --data-binary @examples/stl_request.json \
  > stl_response.json
```

## 6. 成功响应

两个功能使用统一的响应结构：

```json
{
  "request_id": "4f53ccbbf16d4fc49ec956744463d7ae",
  "mode": "reconstruct_stl",
  "summary": "已生成简化初版 STL 并完成网格检查。",
  "classification": "simplified_initial",
  "dimensions_mm": {
    "width": 40.72,
    "depth": 24.47,
    "height": 40.0
  },
  "artifacts": [
    {
      "kind": "stl",
      "filename": "model.stl",
      "mime_type": "model/stl",
      "data_base64": "文件BASE64",
      "byte_length": 15645700,
      "sha256": "文件SHA256"
    }
  ],
  "usage": {
    "codex": {
      "input_tokens": 12000,
      "cached_input_tokens": 3000,
      "output_tokens": 4200,
      "total_tokens": 16200,
      "input_text_tokens": 0,
      "input_image_tokens": 0,
      "output_image_tokens": 0,
      "raw": null
    },
    "image_generation": {
      "input_tokens": 0,
      "cached_input_tokens": 0,
      "output_tokens": 0,
      "total_tokens": 0,
      "input_text_tokens": 0,
      "input_image_tokens": 0,
      "output_image_tokens": 0,
      "raw": null
    },
    "total_tokens": 16200,
    "note": "Token counts are provider-reported usage; they are not a price estimate."
  },
  "warnings": [],
  "codex_thread_id": "可选的Codex任务ID"
}
```

### 6.1 响应字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `request_id` | string | 本次服务任务的唯一标识。 |
| `mode` | string | 本次执行的功能。 |
| `summary` | string | 任务结果摘要。 |
| `classification` | string/null | STL 结果级别：`simplified_initial` 或 `detailed_reconstruction`；图片模式为 `null`。 |
| `dimensions_mm` | object/null | 从最终 STL 重新读取后测得的实际尺寸；图片模式为 `null`。 |
| `artifacts` | array | 生成文件及其 Base64 内容。 |
| `usage` | object | 图片模型和 Codex 分别报告的 Token 用量。 |
| `warnings` | array | 使用量不可用、模型简化或验证限制等警告。 |
| `codex_thread_id` | string/null | Codex 运行事件提供的任务 ID。 |

### 6.2 产物类型

| `kind` | 常见文件 | 说明 |
| --- | --- | --- |
| `image` | `01_front.png` 等 | 六方向图片。 |
| `stl` | `model.stl` | 最终二进制 STL。STL 本身不记录单位，导入切片软件时按毫米解释。 |
| `preview` | `preview_front.png` 等 | 直接从最终 STL 网格渲染的预览。 |
| `report` | `validation.json` | 尺寸和网格验证报告。 |
| `source` | `source.zip` | 可编辑建模源文件。 |

### 6.3 Token 用量

- 图片模式主要查看 `usage.image_generation`。
- STL 模式主要查看 `usage.codex`。
- `usage.total_tokens` 是本次任务中服务商返回的 Token 总数，不是费用金额。
- 如果当前模型、账户或 Codex CLI 没有返回 Token 数据，相应字段为 `0`，并在 `warnings` 中说明。

## 7. 提取 Base64 文件

提取 STL：

```bash
jq -r '.artifacts[] | select(.filename == "model.stl") | .data_base64' \
  stl_response.json | base64 --decode > model.stl
```

提取所有产物可使用工程中的客户端：

```bash
python3 examples/client.py reconstruct_stl front.png back.png \
  --codex-model 'gpt-5.6-sol' \
  --height 40 \
  --requirement '生成适合3D打印的单件实体模型'
```

## 8. 错误响应

FastAPI 错误采用以下基本结构：

```json
{
  "detail": "错误说明"
}
```

| HTTP 状态码 | 含义 |
| --- | --- |
| `401` | `X-API-Key` 缺失或错误。 |
| `422` | 请求 JSON 字段缺失、类型错误、尺寸非法或枚举值不支持。 |
| `500` | 服务内部未处理错误。 |
| `502` | OpenAI、Codex 或生成结果异常，例如缺少必需产物或 STL 无效。 |
| `503` | 服务器找不到 Codex CLI。 |
| `504` | Codex 建模任务超过配置的执行时间。 |

## 9. 健康检查

```http
GET /health
```

响应示例：

```json
{
  "status": "ok",
  "default_image_model": "gpt-image-2",
  "default_codex_model": "gpt-5.6-sol"
}
```

健康检查只表示 HTTP 服务正在运行，不代表 OpenAI API Key 有效，也不代表 Codex 建模环境已经完成真实任务验证。

