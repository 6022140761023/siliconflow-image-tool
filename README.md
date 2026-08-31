# 生图工具（文生图 / Text-to-Image）

输入一段文字描述，自动生成一张图片并保存到本地。基于[硅基流动（SiliconFlow）](https://siliconflow.cn/) API，支持中文提示词。

## 目录结构

```
生图/
├── image_gen.py       # 工具本体（命令行 + Python 函数 + LLM Tool 声明，三合一）
├── requirements.txt   # Python 依赖
├── .env.example       # API Key 配置模板
├── README.md          # 本文件
└── output/            # 生成的图片自动保存在这里（运行时自动创建）
```

## 快速开始

### 1. 安装依赖

需要 Python 3.10 或更高版本，然后：

```powershell
pip install -r requirements.txt
```

### 2. 配置 API Key

1. 到 [硅基流动控制台](https://cloud.siliconflow.cn/) 注册并创建一个 API Key
2. 把 `.env.example` 复制为 `.env`，填入你的 Key：

```
SILICONFLOW_API_KEY=sk-你的Key
```

> ⚠️ `.env` 包含你的私密 Key，不要提交到 git、不要发给别人。

### 3. 生成第一张图

```powershell
python image_gen.py "一只在月球上喝咖啡的橘猫，插画风"
```

成功后图片保存在 `output/` 文件夹里，命令行会输出 JSON 结果（包含文件路径）。

## 用法

### 命令行

```powershell
# 最基本：一句话生图
python image_gen.py "赛博朋克风格的重庆夜景"

# 指定尺寸（竖版适合海报/手机壁纸）
python image_gen.py "古风山水，云雾缭绕" --size 576x1024

# 切换模型（英文提示词推荐 FLUX）
python image_gen.py "a cat astronaut on the moon" --model black-forest-labs/FLUX.1-schnell

# 指定输出目录
python image_gen.py "..." --out D:\我的图片
```

### 在 Python 代码里调用

```python
from image_gen import generate_image

result = generate_image("一只在月球上喝咖啡的橘猫")

if result["ok"]:
    print("图片已保存:", result["path"])
else:
    print("失败原因:", result["error"])
```

### 作为 LLM 工具（Function Calling）

脚本内置了符合 OpenAI 格式的工具声明 `TOOL_SCHEMA`，可直接注册给支持 Function Calling 的大模型（DeepSeek、Qwen、GPT 等），让模型自己决定何时生图：

```python
from image_gen import generate_image, TOOL_SCHEMA

# 把 TOOL_SCHEMA 放进 LLM 请求的 tools 参数
# 模型返回 tool_call 后，按参数执行：
result = generate_image(**tool_call["arguments"])
# 再把 result（含图片路径）喂回模型即可
```

模型只能看到工具的名称/描述/参数，看不到你的 API Key。

## 参数说明

| 参数 | 可选值 | 默认值 | 说明 |
|------|--------|--------|------|
| `prompt` | 任意文字 | （必填） | 图片描述，写得越具体效果越好 |
| `--size` | `1024x1024`、`1024x576`、`576x1024`、`768x768` | `1024x1024` | 宽x高，单位像素 |
| `--model` | 见下表 | `Kwai-Kolors/Kolors` | 生图模型 |
| `--out` | 任意路径 | `output/` | 图片保存目录 |

## 模型选择

| 模型 | 特点 | 适合场景 |
|------|------|---------|
| `Kwai-Kolors/Kolors`（默认） | 中文理解好 | 中文提示词、国风、日常生图 |
| `black-forest-labs/FLUX.1-schnell` | 速度快、价格低 | 英文提示词、快速出草稿 |
| `black-forest-labs/FLUX.1-dev` | 质量最高、较慢较贵 | 精细成品图 |

## 提示词小技巧

- **具体 > 抽象**：`"橘猫，宇航员头盔放在旁边，地球挂在星空背景中，插画风"` 比 `"一只猫"` 效果好得多
- **带上风格词**：插画风 / 照片级写实 / 水彩 / 像素风 / 赛博朋克……
- **带上构图**：特写 / 全景 / 俯视 / 居中构图……

## 常见问题

**Q：报错 `未找到 SILICONFLOW_API_KEY`？**
检查 `.env` 是否和 `image_gen.py` 在同一个文件夹里，Key 拼写是否正确（`sk-` 开头）。

**Q：报错 `HTTP 401`？**
Key 无效或已过期，去硅基流动控制台重新创建。

**Q：报错 `HTTP 429` 或余额相关？**
账户余额不足或触发限流，去控制台充值/稍后再试。

**Q：下载图片很慢？**
工具已内置流式下载和超时重试机制，偶发的 CDN 慢速会自动处理。如果频繁失败，检查网络代理设置。

## 安全与费用

- 每次生图都会消耗硅基流动账户余额（Kolors/FLUX-schnell 价格很低，FLUX-dev 较贵），注意控制调用次数。
- `.env` 已加入 `.gitignore`，但请自己确认不要意外泄露 Key。
- 生成的图片链接是临时签名 URL（约 1 小时过期），本地文件才是持久保存的。
