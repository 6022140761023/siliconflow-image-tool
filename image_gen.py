"""
image_gen.py — 文生图 Tool（硅基流动 SiliconFlow API）

作为函数调用（给 Agent 用）:
    from image_gen import generate_image
    result = generate_image("一只在月球上喝咖啡的猫")
    # 成功: {"ok": True, "path": "output/xxx.png", "url": "...", "model": "...", "seed": 123}
    # 失败: {"ok": False, "error": "401 Unauthorized: ..."}

命令行直接用（在本文件夹内运行）:
    python image_gen.py "一只在月球上喝咖啡的猫"
    python image_gen.py "a cat on the moon" --model black-forest-labs/FLUX.1-schnell --size 1024x576

模型说明:
    Kwai-Kolors/Kolors              —— 默认，中文 prompt 理解好
    black-forest-labs/FLUX.1-schnell —— 速度快、便宜，英文 prompt 更佳
    black-forest-labs/FLUX.1-dev     —— 质量更高，更贵更慢
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

API_URL = "https://api.siliconflow.cn/v1/images/generations"
DEFAULT_MODEL = "Kwai-Kolors/Kolors"
DEFAULT_SIZE = "1024x1024"
GEN_TIMEOUT = 120   # 生成接口超时（秒）
DOWNLOAD_TIMEOUT = 60

# 项目根目录（tools/ 的上一级）
# 包目录（本脚本所在文件夹）—— 自包含设计：Key 和生成的图片都在包内
PACKAGE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PACKAGE_DIR / "output"

# OpenAI Function Calling 格式的工具声明 —— 注册给 LLM 用
# 模型只能看到这部分（名字/描述/参数），看不到也看不到需要看实现细节
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "generate_image",
        "description": (
            "根据文本描述生成一张图片并保存到本地，返回文件路径。"
            "中文提示词用默认模型效果最好；英文提示词可切换 FLUX 模型。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "图片描述（提示词），越具体效果越好",
                },
                "size": {
                    "type": "string",
                    "enum": ["1024x1024", "1024x576", "576x1024", "768x768"],
                    "description": "图片尺寸，默认 1024x1024",
                },
                "model": {
                    "type": "string",
                    "enum": [
                        "Kwai-Kolors/Kolors",
                        "black-forest-labs/FLUX.1-schnell",
                        "black-forest-labs/FLUX.1-dev",
                    ],
                    "description": "生图模型：Kolors 擅长中文；FLUX.1-schnell 快且便宜；FLUX.1-dev 质量高",
                },
            },
            "required": ["prompt"],
            "additionalProperties": False,
        },
    },
}


def _load_api_key() -> str:
    """按优先级查找 Key：环境变量 → 包目录 .env → 上级目录 .env。"""
    key = os.environ.get("SILICONFLOW_API_KEY")
    if key:
        return key
    for env_file in (PACKAGE_DIR / ".env", PACKAGE_DIR.parent / ".env"):
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("SILICONFLOW_API_KEY="):
                    return line.split("=", 1)[1].strip()
    return ""


def generate_image(
    prompt: str,
    size: str = DEFAULT_SIZE,
    model: str = DEFAULT_MODEL,
    output_dir: str | None = None,
    batch_size: int = 1,
) -> dict:
    """
    文生图。成功返回 {"ok": True, "path": ...}，失败返回 {"ok": False, "error": ...}。
    图片一定落盘，只把路径返回给调用方，避免大文件进入模型上下文。
    """
    if not prompt or not prompt.strip():
        return {"ok": False, "error": "prompt 不能为空"}

    api_key = _load_api_key()
    if not api_key:
        return {"ok": False, "error": "未找到 SILICONFLOW_API_KEY（检查 .env 或环境变量）"}

    payload = {
        "model": model,
        "prompt": prompt.strip(),
        "image_size": size,
        "batch_size": batch_size,
        "num_inference_steps": 20,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=GEN_TIMEOUT)
    except requests.RequestException as e:
        return {"ok": False, "error": f"请求生成接口失败: {e}"}

    if resp.status_code != 200:
        # 把 API 的错误原样返回，方便模型/用户判断（余额不足、参数非法等）
        body = resp.text[:500]
        return {"ok": False, "error": f"HTTP {resp.status_code}: {body}"}

    try:
        data = resp.json()
        image_url = data["images"][0]["url"]
    except (ValueError, KeyError, IndexError) as e:
        return {"ok": False, "error": f"响应格式异常: {e}; 原始内容: {resp.text[:300]}"}

    # 下载图片落盘
    out_dir = Path(output_dir) if output_dir else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"img_{time.strftime('%Y%m%d_%H%M%S')}.png"
    out_path = out_dir / filename

    # 流式下载：CDN 偶发首字节慢，用 (连接超时, 读超时) 并分块写入
    try:
        with requests.get(image_url, stream=True, timeout=(30, DOWNLOAD_TIMEOUT)) as img_resp:
            img_resp.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in img_resp.iter_content(chunk_size=65536):
                    f.write(chunk)
    except requests.RequestException as e:
        return {"ok": False, "error": f"图片下载失败: {e}; url: {image_url}"}

    return {
        "ok": True,
        "path": str(out_path),
        "url": image_url,
        "model": model,
        "size": size,
        "seed": data.get("seed"),
        "prompt": prompt.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="硅基流动文生图工具")
    parser.add_argument("prompt", help="图片描述（提示词）")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"模型名，默认 {DEFAULT_MODEL}")
    parser.add_argument("--size", default=DEFAULT_SIZE, help=f"图片尺寸，默认 {DEFAULT_SIZE}")
    parser.add_argument("--out", default=None, help="输出目录，默认 output/")
    args = parser.parse_args()

    result = generate_image(args.prompt, size=args.size, model=args.model, output_dir=args.out)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
