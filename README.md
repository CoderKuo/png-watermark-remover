# 图片破甲器

检测和清除 PNG 图片中的 C2PA 隐水印及追踪元数据。

## 背景

ChatGPT（GPT-Image2 / DALL-E）等 AI 工具生成的 PNG 图片会嵌入 **C2PA**（Coalition for Content Provenance and Authenticity）元数据块，用于标记图片来源、生成软件、生成时间等信息。这些数据嵌入在 PNG chunk 中，肉眼不可见，但可被 C2PA 兼容工具读取和追踪。

本工具可以检测并清除这些隐水印，保护你的隐私。如果你不希望别人知道你使用了 AI 生成图片，可以在发布前使用本工具清理图片。

## 功能

- **检测模式** — 解析 PNG 文件结构，列出所有 C2PA / EXIF / 文本元数据块
- **清除模式** — 移除指定 chunk 类型，重建干净的 PNG 文件
- **对比模式** — 清除前后对比，确认隐水印已移除
- **批量处理** — 支持文件拖放，可处理单个文件或整个文件夹
- **JSON 输出** — `--json` 参数可输出机器可读格式，方便集成

## 安装

本工具纯 Python 编写，无第三方依赖，需要 Python 3.7+。

```bash
git clone https://github.com/CoderKuo/png-watermark-remover.git
cd png-watermark-remover
```

## 使用方法

### 检测隐水印

```bash
python detect.py image.png -v
python detect.py ./images/ --json          # 批量检测，输出 JSON
python detect.py before.png after.png -c   # 对比两张图片的元数据差异
```

### 清除隐水印

```bash
python stripper.py image.png               # 默认清除 C2PA + EXIF
python stripper.py ./images/               # 批量处理整个文件夹
python stripper.py image.png --dry-run     # 仅检测，不修改文件
python stripper.py image.png --strip-all   # 清除所有元数据块
```

### Windows 拖放操作

将图片文件或文件夹直接拖到 `检测.bat` 或 `破甲.bat` 图标上即可。

## 清除范围

| Chunk | 说明 | 默认清除 |
|-------|------|---------|
| caBX  | C2PA 内容溯源元数据（AI 生成/软件/时间戳） | ✓ |
| caBL  | C2PA 块列表 | ✓ |
| eXIf  | EXIF 数据（可能含 GPS 等） | ✓ |
| tEXt  | 文本元数据 | 可选 |
| iTXt  | 国际化文本 | 可选 |
| zTXt  | 压缩文本 | 可选 |

## 注意事项

- 清除操作会**直接修改原文件**，建议先备份
- 目前仅支持 PNG 格式
- 某些网站/平台会在上传时单独扫描 C2PA 信息，本工具仅保证文件本身不含元数据

## License

MIT
