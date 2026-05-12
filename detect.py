#!/usr/bin/env python3
"""
图片破甲器 - C2PA 隐水印检测脚本
检测 PNG 文件中是否存在 C2PA / 追踪元数据，并输出详细信息用于对比
"""

import struct
import sys
import os
import json
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PNG_SIG = b"\x89PNG\r\n\x1a\n"
TRACKING_CHUNKS = {b"caBX", b"caBL", b"eXIf", b"tEXt", b"iTXt", b"zTXt"}

CHUNK_LABELS = {
    b"caBX": "C2PA 内容溯源元数据 (caBX)",
    b"caBL": "C2PA 块列表 (caBL)",
    b"eXIf": "EXIF 数据 (eXIf)",
    b"tEXt": "文本元数据 (tEXt)",
    b"iTXt": "国际化文本 (iTXt)",
    b"zTXt": "压缩文本 (zTXt)",
}


def parse_png(filepath):
    with open(filepath, "rb") as f:
        data = f.read()
    if data[:8] != PNG_SIG:
        return None, "不是有效的 PNG 文件"
    chunks = []
    pos = 8
    while pos < len(data):
        if pos + 8 > len(data):
            break
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        chunk_type = data[pos + 4 : pos + 8]
        chunk_data = data[pos + 8 : pos + 8 + length]
        crc = data[pos + 8 + length : pos + 12 + length]
        chunks.append((chunk_type, chunk_data, crc))
        pos += 12 + length
    return chunks, None


def extract_c2pa_info(chunk_data):
    """从 caBX 块中提取可读的摘要信息"""
    info = {}
    data = chunk_data

    # 提取所有可读 ASCII 字符串 (>=4 字符)
    current = b""
    strings = []
    for b in data:
        if 32 <= b < 127:
            current += bytes([b])
        else:
            if len(current) >= 4:
                s = current.decode("ascii")
                if any(kw in s.lower() for kw in ["c2pa", "gpt", "openai", "dalle", "trained", "created",
                                                   "software", "urn:", "xmp:", "instance", "claim",
                                                   "signature", "trufo", "icon", "hash", "asset"]):
                    strings.append(s)
            current = b""
    info["keywords"] = strings

    # 提取 C2PA action
    if b"c2pa.created" in data:
        info["action"] = "created (AI 生成)"
    elif b"c2pa.converted" in data:
        info["action"] = "converted (格式转换)"

    if b"gpt-image" in data:
        info["software"] = "OpenAI gpt-image"
    if b"trainedAlgorithmicMedia" in data:
        info["source_type"] = "AI 生成内容"

    # 提取时间戳
    for kw in [b"t2026", b"t2025", b"t2024"]:
        idx = data.find(kw)
        if idx >= 0:
            ts = data[idx + 1 : idx + 21].decode("ascii", errors="replace")
            ts = ts.rstrip("Z").rstrip("z")
            info["timestamp"] = ts
            break

    # 提取 UUID
    if b"urn:c2pa:" in data:
        idx = data.find(b"urn:c2pa:")
        end = data.find(b"\x00", idx)
        if end < 0:
            end = min(idx + 64, len(data))
        uuid_raw = data[idx:end]
        info["uuid"] = uuid_raw.decode("ascii", errors="replace")

    return info


def detect_file(filepath, json_out=False):
    chunks, err = parse_png(filepath)
    if err:
        return {"error": err}

    file_size = os.path.getsize(filepath)
    found = []
    standard = []
    total_meta = 0

    for chunk_type, chunk_data, crc in chunks:
        label = CHUNK_LABELS.get(chunk_type, None)
        size = len(chunk_data)
        if chunk_type in TRACKING_CHUNKS:
            entry = {
                "type": chunk_type.decode("ascii"),
                "size": size,
                "label": label or f"未知追踪块 ({chunk_type.decode('ascii')})",
            }
            if chunk_type == b"caBX":
                c2pa_info = extract_c2pa_info(chunk_data)
                entry["c2pa"] = c2pa_info
            elif chunk_type in (b"tEXt", b"iTXt", b"zTXt"):
                try:
                    text = chunk_data.decode("utf-8", errors="replace")
                    if "\x00" in text:
                        key, value = text.split("\x00", 1)
                        entry["key"] = key
                        entry["value"] = value[:200]
                    else:
                        entry["preview"] = text[:200]
                except:
                    pass
            found.append(entry)
            total_meta += size
        else:
            standard.append(chunk_type.decode("ascii", errors="replace"))

    result = {
        "file": str(Path(filepath).name),
        "file_size": file_size,
        "image_size": f"{chunks[0][1][:8].hex()}" if chunks else "?",
        "total_chunks": len(chunks),
        "tracking_chunks": found,
        "tracking_count": len(found),
        "tracking_bytes": total_meta,
        "has_watermark": len(found) > 0,
        "standard_chunks": standard,
    }
    return result


def print_result(result, verbose=False):
    print(f"\n{'='*60}")
    print(f"  文件: {result['file']}")
    print(f"  大小: {result['file_size']:,} bytes")
    print(f"  总块数: {result['total_chunks']}")
    print(f"{'='*60}")

    if result.get("error"):
        print(f"  [错误] {result['error']}")
        return

    if not result["has_watermark"]:
        print(f"  状态: [OK] 未检测到追踪元数据")
        return

    print(f"  状态: [!!] 检测到 {result['tracking_count']} 个追踪元数据块 ({result['tracking_bytes']:,} bytes)")
    print(f"  {'─'*50}")

    for chunk in result["tracking_chunks"]:
        print(f"  [{chunk['type']}] {chunk['label']}")
        print(f"    大小: {chunk['size']:,} bytes")

        if "c2pa" in chunk:
            c2pa = chunk["c2pa"]
            if "software" in c2pa:
                print(f"    生成软件: {c2pa['software']}")
            if "action" in c2pa:
                print(f"    操作: {c2pa['action']}")
            if "source_type" in c2pa:
                print(f"    来源类型: {c2pa['source_type']}")
            if "timestamp" in c2pa:
                print(f"    生成时间: {c2pa['timestamp']}")
            if "uuid" in c2pa:
                print(f"    UUID: {c2pa['uuid']}")
            if "keywords" in c2pa and verbose:
                for kw in c2pa["keywords"][:10]:
                    print(f"    [{kw}]")

        if "key" in chunk:
            print(f"    Key: {chunk['key']}")
            print(f"    Value: {chunk.get('value', chunk.get('preview', ''))}")

    print(f"  {'─'*50}")
    print(f"  结论: 该图片含有可追踪的元数据，建议清除后再发布")


def compare_results(r1, r2):
    """对比两个检测结果"""
    print(f"\n{'='*60}")
    print(f"  对比报告")
    print(f"{'='*60}")
    print(f"  A: {r1['file']}  ({r1['file_size']:,} bytes)")
    print(f"  B: {r2['file']}  ({r2['file_size']:,} bytes)")

    a_has = r1["has_watermark"]
    b_has = r2["has_watermark"]

    if a_has and not b_has:
        print(f"\n  [OK] 清除成功: {r1['tracking_count']} 个元数据块已被移除")
        print(f"  释放: {r1['tracking_bytes']:,} bytes")
        print(f"  文件缩小: {r1['file_size'] - r2['file_size']:,} bytes")
    elif not a_has and not b_has:
        print(f"\n  两个文件均无追踪元数据")
    elif a_has and b_has:
        print(f"\n  [!!] B 文件仍含有元数据，清除可能不完整")
        print(f"  A: {r1['tracking_count']} 块, B: {r2['tracking_count']} 块")
    elif not a_has and b_has:
        print(f"\n  [?!] 反向变化: B 比 A 多了元数据")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="检测 PNG 中的 C2PA 追踪元数据")
    parser.add_argument("paths", nargs="+", help="PNG 文件或文件夹路径")
    parser.add_argument("--json", "-j", action="store_true", help="JSON 格式输出")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细信息")
    parser.add_argument("--compare", "-c", action="store_true", help="对比模式 (至少2个文件)")

    args = parser.parse_args()

    png_files = []
    for p in args.paths:
        pp = Path(p)
        if pp.is_dir():
            png_files.extend(sorted(pp.glob("**/*.png")))
        elif pp.is_file() and pp.suffix.lower() == ".png":
            png_files.append(pp)

    if not png_files:
        print("未找到 PNG 文件。")
        return

    results = []
    for fpath in png_files:
        r = detect_file(str(fpath))
        results.append(r)
        if not args.json:
            print_result(r, verbose=args.verbose)

    if args.json:
        print(json.dumps(results if len(results) > 1 else results[0],
                         ensure_ascii=False, indent=2))

    if args.compare and len(results) >= 2:
        compare_results(results[0], results[1])
    elif args.compare:
        print("对比模式需要至少 2 个文件。")


if __name__ == "__main__":
    main()
