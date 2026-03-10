#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROM.WAD <-> TXT (2 chiều) cho GTA Chinatown Wars (NDS) - DS_GXT

Mục tiêu:
  1) Xuất: hỏi đường dẫn ROM.WAD (KHÔNG hỏi .nds), xuất TXT vào thư mục.
  2) Nhập: hỏi đường dẫn ROM.WAD + thư mục TXT, xuất rom_nw.wad (và rom_nw.toc nếu có ROM.TOC cạnh ROM.WAD).

"Repoint" trong phạm vi AN TOÀN:
  - Tool luôn cập nhật lại length (u16) của string trong DS_GXT (nội bộ file GXT).
  - Khi import, tool chỉ ghi đè trong vùng đệm 0xAD NGAY SAU file DS_GXT (đến trước byte khác 0xAD).
    => Cho phép text dài hơn/nhỏ hơn *miễn là còn đủ padding 0xAD*.
  - Tool KHÔNG dịch chuyển (move) các chunk khác trong ROM.WAD vì cấu trúc tổng thể của ROM.WAD
    còn nhiều vùng dữ liệu xen kẽ (không phải toàn 0xAD). Nếu cần "move file" thực sự,
    phải reverse-engineer thêm index/pointer tổng của WAD.

Token hỗ trợ trong TXT:
  - ~n~            : newline (0x000A)
  - ~#HEX~         : chèn trực tiếp codepoint u16 (vd ~#FF00~, ~#5C~)
  - <HEX>          : tương tự (~#HEX~) (vd <A9>, <FF0C>)

Lowercase custom mapping theo bảng bạn đưa:
  0x5C..0x75  <=>  a..z
Uppercase giữ ASCII:
  0x41..0x5A  <=>  A..Z

Xuất file:
  out_dir/0000_001CD200.txt ...
  out_dir/_manifest.json  (chứa off/raw_end/max_alloc ... dùng cho import)

"""

from __future__ import annotations
import json
import re
import struct
from pathlib import Path

SIG = b"DS_GXT"
ALIGN = 0x200
PAD_BYTE = 0xAD

TAG_RE = re.compile(r"~#([0-9A-Fa-f]{1,8})~")
ALT_TAG_RE = re.compile(r"<([0-9A-Fa-f]{2,8})>")

def align_up(n: int, a: int = ALIGN) -> int:
    return (n + (a - 1)) & ~(a - 1)

# =======================
#  Encode / Decode symbols
# =======================
def decode_symbol(cp: int) -> str:
    # newline
    if cp == 0x000A:
        return "~n~"

    # tag/control
    if cp > 0xFEEF:
        return f"~#{cp:X}~"

    # A-Z
    if 0x41 <= cp <= 0x5A:
        return chr(cp)

    # a-z (custom)
    if 0x5C <= cp <= 0x75:
        return chr(ord('a') + (cp - 0x5C))

    # ASCII printable
    if 0x20 <= cp < 0x7F:
        return chr(cp)

    if cp == 0:
        return ""

    # fallback
    if cp <= 0xFF:
        return f"~#{cp:X}~"
    try:
        return chr(cp)
    except ValueError:
        return f"~#{cp:X}~"

def encode_text_to_symbols(s: str) -> list[int]:
    cps: list[int] = []
    i = 0
    while i < len(s):
        if s.startswith("~n~", i):
            cps.append(0x000A)
            i += 3
            continue

        m = TAG_RE.match(s, i)
        if m:
            cps.append(int(m.group(1), 16))
            i = m.end()
            continue

        m2 = ALT_TAG_RE.match(s, i)
        if m2:
            cps.append(int(m2.group(1), 16))
            i = m2.end()
            continue

        ch = s[i]
        if 'A' <= ch <= 'Z':
            cps.append(ord(ch))
        elif 'a' <= ch <= 'z':
            cps.append(0x5C + (ord(ch) - ord('a')))
        else:
            cps.append(ord(ch))
        i += 1
    return cps

# =======================
#  DS_GXT parse / build
# =======================
def _u16(b: bytes, off: int) -> int:
    return struct.unpack_from("<H", b, off)[0]

def parse_gxt(buf: bytes, off: int) -> dict | None:
    if buf[off:off + 6] != SIG:
        return None
    if off + 8 > len(buf):
        return None

    num = _u16(buf, off + 6)
    p = off + 8
    strings: list[list[int]] = []

    for _ in range(num):
        if p + 2 > len(buf):
            return None
        L = _u16(buf, p)
        p += 2
        if p + L * 2 > len(buf):
            return None
        if L:
            cps = list(struct.unpack_from("<" + "H" * L, buf, p))
        else:
            cps = []
        p += L * 2
        strings.append(cps)

    return {"num": num, "cps": strings, "end": p}

def build_gxt(strings_cps: list[list[int]]) -> bytes:
    num = len(strings_cps)
    out = bytearray()
    out += SIG
    out += struct.pack("<H", num)

    for i, cps in enumerate(strings_cps):
        # bỏ null dư ở cuối nếu có
        while cps and cps[-1] == 0:
            cps = cps[:-1]
        if i == num - 1:
            cps2 = cps + [0]  # last string includes terminating null
        else:
            cps2 = cps

        out += struct.pack("<H", len(cps2))
        if cps2:
            out += struct.pack("<" + "H" * len(cps2), *cps2)

    return bytes(out)

def scan_gxt_offsets(buf: bytes) -> list[int]:
    offs: list[int] = []
    start = 0
    while True:
        p = buf.find(SIG, start)
        if p == -1:
            break
        info = parse_gxt(buf, p)
        if info is not None:
            offs.append(p)
            start = p + 6
        else:
            start = p + 1
    return offs

def compute_max_alloc_end(buf: bytes, off: int, raw_end: int) -> int:
    """
    max_alloc_end = điểm dừng trước byte != 0xAD, bắt đầu từ aligned_end(raw_end).
    """
    p = align_up(raw_end, ALIGN)
    n = len(buf)
    while p < n and buf[p] == PAD_BYTE:
        p += 1
    return p

# =======================
#  TXT IO
# =======================
def write_txt(out_path: Path, idx: int, off: int, raw_end: int, max_end: int, strings: list[list[int]]):
    lines: list[str] = []
    lines.append(f"; DS_GXT idx={idx} off=0x{off:X} raw_end=0x{raw_end:X} max_end=0x{max_end:X} max_alloc=0x{(max_end-off):X} num={len(strings)}")
    for si, cps in enumerate(strings):
        # bỏ null cuối nếu là string cuối
        if si == len(strings) - 1 and cps and cps[-1] == 0:
            cps = cps[:-1]
        s = "".join(decode_symbol(cp) for cp in cps)
        s = s.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "~n~")
        lines.append(f"{si}={s}")
    out_path.write_text("\n".join(lines), encoding="utf-8")

def read_txt_kv(txt_path: Path) -> dict[int, str]:
    kv: dict[int, str] = {}
    for line in txt_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip("\ufeff").rstrip()
        if not line or line.startswith(";") or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        if k.isdigit():
            kv[int(k)] = v.strip()
    return kv

# =======================
#  Export / Import
# =======================
def export_rom_wad(rom_wad_path: str, out_dir: str):
    wad_path = Path(rom_wad_path)
    data = wad_path.read_bytes()

    outp = Path(out_dir)
    outp.mkdir(parents=True, exist_ok=True)

    offsets = scan_gxt_offsets(data)
    manifest = []
    for idx, off in enumerate(offsets):
        info = parse_gxt(data, off)
        if info is None:
            continue
        raw_end = info["end"]
        max_end = compute_max_alloc_end(data, off, raw_end)
        fname = f"{idx:04d}_{off:08X}.txt"
        write_txt(outp / fname, idx, off, raw_end, max_end, info["cps"])
        manifest.append({
            "idx": idx,
            "off": off,
            "raw_end": raw_end,
            "max_end": max_end,
            "max_alloc": max_end - off,
            "num": info["num"],
            "file": fname,
        })

    (outp / "_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Export: {len(manifest)} DS_GXT -> {outp}")

def import_rom_wad(rom_wad_path: str, txt_dir: str, out_wad_path: str, out_toc_path: str | None = None):
    wad_path = Path(rom_wad_path)
    data = bytearray(wad_path.read_bytes())

    txtp = Path(txt_dir)
    man_path = txtp / "_manifest.json"
    if not man_path.exists():
        raise FileNotFoundError("Thiếu _manifest.json (hãy Export trước).")
    manifest = json.loads(man_path.read_text(encoding="utf-8"))

    replaced = 0
    errors: list[str] = []

    for m in manifest:
        idx = int(m["idx"])
        off = int(m["off"])
        max_alloc = int(m["max_alloc"])
        num = int(m["num"])
        txt_file = txtp / m["file"]
        if not txt_file.exists():
            continue

        info = parse_gxt(data, off)
        if info is None:
            errors.append(f"idx={idx} off=0x{off:X}: không parse được DS_GXT (bỏ qua)")
            continue

        kv = read_txt_kv(txt_file)

        new_strings: list[list[int]] = []
        for si in range(num):
            if si in kv:
                cps = encode_text_to_symbols(kv[si])
            else:
                # giữ nguyên string gốc (trừ null cuối)
                cps = info["cps"][si]
                if si == num - 1 and cps and cps[-1] == 0:
                    cps = cps[:-1]
            new_strings.append(cps)

        new_gxt = build_gxt(new_strings)

        if len(new_gxt) > max_alloc:
            errors.append(
                f"idx={idx} off=0x{off:X}: DS_GXT mới 0x{len(new_gxt):X} > max_alloc 0x{max_alloc:X} ({txt_file.name})"
            )
            continue

        patch = new_gxt + bytes([PAD_BYTE]) * (max_alloc - len(new_gxt))
        data[off:off + max_alloc] = patch
        replaced += 1

    Path(out_wad_path).write_bytes(data)
    print(f"[OK] Import: patched {replaced}/{len(manifest)} DS_GXT -> {out_wad_path}")

    # ROM.TOC: nếu user muốn, copy nguyên file (không sửa) để tiện đóng gói lại NDS
    if out_toc_path:
        print(f"[OK] ROM.TOC -> {out_toc_path}")

    if errors:
        print("\n[!] Các file QUÁ DÀI (không đủ padding 0xAD), tool giữ nguyên bản gốc cho các file này:")
        for e in errors[:80]:
            print(" -", e)
        if len(errors) > 80:
            print(f" ... và {len(errors)-80} lỗi nữa.")

def main():
    print("ROM.WAD <-> TXT (DS_GXT) tool - GTA Chinatown Wars (NDS)")
    print("1) Xuất TXT")
    print("2) Nhập TXT -> rom_nw.wad")
    mode = input("Chọn (1/2): ").strip()

    if mode == "1":
        wad = input("Đường dẫn ROM.WAD: ").strip().strip('"')
        out_dir = input("Thư mục xuất TXT: ").strip().strip('"')
        export_rom_wad(wad, out_dir)

    elif mode == "2":
        wad = input("Đường dẫn ROM.WAD: ").strip().strip('"')
        txt_dir = input("Thư mục TXT: ").strip().strip('"')

        wad_path = Path(wad)
        out_wad = str(wad_path.with_name("rom_nw.wad"))

        # auto copy toc nếu có
        toc_path = wad_path.with_name("ROM.TOC")
        out_toc = None
        if toc_path.exists():
            out_toc = str(wad_path.with_name("rom_nw.toc"))
            Path(out_toc).write_bytes(toc_path.read_bytes())

        import_rom_wad(wad, txt_dir, out_wad, out_toc)

    else:
        print("Mode không hợp lệ.")

if __name__ == "__main__":
    main()
