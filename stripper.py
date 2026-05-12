#!/usr/bin/env python3
"""
图片破甲器 - PNG C2PA / 隐水印元数据批量清除工具
移除 PNG 文件中的 C2PA caBX 块及其他非标准追踪元数据
"""

import struct
import sys
import os
from pathlib import Path

# Windows GBK 终端下强制 UTF-8 输出，避免中文乱码
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 已知的 PNG 元数据追踪块（大小写敏感，4 字节）
STRIP_CHUNKS = {
    b"caBX",  # C2PA metadata box (Coalition for Content Provenance and Authenticity)
    b"caBL",  # C2PA block list
    b"tEXt",  # 文本元数据（可能含追踪信息，可选清除）
    b"iTXt",  # 国际化文本元数据
    b"zTXt",  # 压缩文本元数据
    b"eXIf",  # EXIF 数据（可能含 GPS 等）
}

# 默认只清除 C2PA + EXIF，不清除 tEXt 等（可被正常软件使用）
DEFAULT_STRIP = {b"caBX", b"caBL", b"eXIf"}

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def parse_png(filepath):
    """解析 PNG 文件，返回 chunk 列表 [(type, data, crc, offset_start)]"""
    with open(filepath, "rb") as f:
        data = f.read()

    if data[:8] != PNG_SIG:
        return None, "Not a valid PNG file"

    chunks = []
    pos = 8
    while pos < len(data):
        if pos + 8 > len(data):
            break
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        chunk_type = data[pos + 4 : pos + 8]
        chunk_data = data[pos + 8 : pos + 8 + length]
        crc = data[pos + 8 + length : pos + 12 + length]
        chunks.append((chunk_type, chunk_data, crc, pos))
        pos += 12 + length

    return chunks, None


def strip_c2pa(filepath, strip_set, dry_run=False):
    """移除 PNG 文件中的指定 chunk 类型，返回 (removed_chunks, old_size, new_size)"""
    chunks, err = parse_png(filepath)
    if err:
        return None, err, 0, 0

    old_size = os.path.getsize(filepath)
    removed = []
    kept = []

    for chunk_type, chunk_data, crc, pos in chunks:
        if chunk_type in strip_set:
            removed.append(chunk_type.decode("ascii", errors="replace"))
        else:
            kept.append((chunk_type, chunk_data, crc))

    if not removed:
        return [], None, old_size, old_size

    if dry_run:
        return removed, None, old_size, 0

    # 重建 PNG
    new_data = bytearray(PNG_SIG)
    for chunk_type, chunk_data, crc in kept:
        new_data.extend(struct.pack(">I", len(chunk_data)))
        new_data.extend(chunk_type)
        new_data.extend(chunk_data)
        new_data.extend(crc)

    new_size = len(new_data)
    with open(filepath, "wb") as f:
        f.write(new_data)

    return removed, None, old_size, new_size


def process_paths(paths, strip_set, dry_run=False):
    """批量处理文件/文件夹"""
    png_files = []
    for p in paths:
        pp = Path(p)
        if pp.is_dir():
            png_files.extend(sorted(pp.glob("**/*.png")))
        elif pp.is_file() and pp.suffix.lower() == ".png":
            png_files.append(pp)

    if not png_files:
        print("未找到 PNG 文件。")
        return

    total_removed = 0
    total_saved = 0
    failed = 0

    for fpath in png_files:
        removed, err, old_size, new_size = strip_c2pa(str(fpath), strip_set, dry_run)
        if err:
            print(f"[错误] {fpath.name}: {err}")
            failed += 1
            continue

        if dry_run:
            if removed:
                print(f"[发现] {fpath.name}: {', '.join(removed)}")
                total_removed += 1
        else:
            if removed:
                saved = old_size - new_size
                total_saved += saved
                total_removed += 1
                print(f"[清除] {fpath.name}: {', '.join(removed)} ({old_size:,} → {new_size:,} bytes, -{saved:,})")
            else:
                print(f"[跳过] {fpath.name}: 无目标元数据")

    if dry_run:
        print(f"\n共扫描 {len(png_files)} 个文件，发现 {total_removed} 个含可清除元数据")
    else:
        print(f"\n处理完成: {total_removed} 个已清除, {len(png_files) - total_removed - failed} 个已跳过, {failed} 个失败")
        if total_saved > 0:
            print(f"共释放: {total_saved:,} bytes")


def main():
    print("=" * 50)
    print("  图片破甲器 - C2PA / 隐水印元数据清除工具")
    print("=" * 50)

    import argparse

    parser = argparse.ArgumentParser(description="清除 PNG 中的 C2PA 追踪元数据")
    parser.add_argument("paths", nargs="+", help="PNG 文件或文件夹路径")
    parser.add_argument("--dry-run", "-n", action="store_true", help="仅检测，不修改文件")
    parser.add_argument(
        "--strip-all", "-a", action="store_true",
        help="清除所有元数据块（含 tEXt/iTXt/zTXt/eXIf），默认仅清除 C2PA+EXIF"
    )
    parser.add_argument(
        "--chunks", "-c", nargs="+",
        help="自定义要清除的 chunk 列表，如: caBX eXIf tEXt"
    )

    args = parser.parse_args()

    if args.chunks:
        strip_set = {c.encode("ascii") for c in args.chunks}
    elif args.strip_all:
        strip_set = STRIP_CHUNKS
    else:
        strip_set = DEFAULT_STRIP

    print(f"\n清除目标: {', '.join(c.decode() for c in strip_set)}")
    if not args.dry_run:
        print("[!] 警告: 将直接修改原文件！建议先备份。")
        print("提示: 使用 -n 参数可仅检测不修改。\n")
    else:
        print("(仅检测模式，不会修改文件)\n")

    process_paths(args.paths, strip_set, dry_run=args.dry_run)

    if args.dry_run:
        print("\n使用 'python stripper.py <路径>' 执行实际清除。")


if __name__ == "__main__":
    main()
