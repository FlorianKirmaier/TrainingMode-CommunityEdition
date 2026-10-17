#!/usr/bin/env python3
# AI-written (Claude), experimental: adds Slippi's replay recording to a TM-CE ISO.
"""
Copies a TM-CE ISO and appends Slippi's "Slippi Recording" codes, taken from an installed Slippi Dolphin, to its codes.gct.
The game ID stays GTME01, so the Slippi Dolphin loads none of its own codes for it; nothing of Slippi's is copied into
this repository and a newer Slippi Dolphin only needs this script run again.

Usage: add-recording.py [--skip <part of a code's name>]... <TM-CE.iso> <output.iso> [<Slippi Dolphin Sys folder>]
"""
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile

DEFAULT_SYS = os.path.expanduser(
    "~/Library/Application Support/Slippi Launcher/netplay/Slippi Dolphin.app/Contents/Resources/Sys")
SECTION = "$Required: Slippi Recording"
# TM-CE has the same code at these hooks, or they are not needed for recording
SKIP = ("Initialize Player Data", "Initialize Stage Data", "CSS KO Stars")
# Static functions from Slippi's bootloader the recording codes call: EXITransferBuffer, ProcessGecko
BOOTLOADER_FUNCTIONS = (0x800055F0, 0x800055FC)
SHOULD_RECORD = 0x80005604
GECKO_HEAP_PTR = 0x80005600
# A spot in the unused tournament-mode block Slippi already writes into; holds an empty code list for the replay header
EMPTY_LIST_AT = 0x80005620
EXTEND_PLAYER_BLOCK = 0x800679BC


def words_of(data):
    return [struct.unpack(">II", data[i:i + 8]) for i in range(0, len(data) - len(data) % 8, 8)]


def codes(words):
    """Splits a Gecko list into (address, words) per code; stops at the F0 terminator."""
    out, i = [], 0
    while i < len(words):
        a, b = words[i]
        t = (a >> 24) & 0xFE
        if t == 0xF0:
            break
        n = 1 + (b if t in (0xC0, 0xC2) else (b + 7) // 8 if t == 0x06 else 0)
        out.append((0x80000000 | (a & 0x01FFFFFF), t, words[i:i + n]))
        i += n
    return out


def written(code):
    addr, t, ws = code
    return (addr, addr + (ws[0][1] if t == 0x06 else 4))


def recording_codes(ini, skip=()):
    lines = open(ini).read().splitlines()
    gecko = lines.index("[Gecko]")
    start = next(i for i, l in enumerate(lines) if i > gecko and l.startswith(SECTION))
    out, label, keep = [], "", True
    for l in lines[start + 1:]:
        if l.startswith("$") or l.startswith("["):
            break
        m = re.match(r"^([0-9A-Fa-f]{8}) ([0-9A-Fa-f]{8})(?:\s*#(.*))?$", l.strip())
        if not m:
            continue
        if m.group(3):
            label = m.group(3).strip()
            keep = not any(s in label for s in SKIP + tuple(skip))
        if keep:
            out.append((int(m.group(1), 16), int(m.group(2), 16)))
    return out


def always_record():
    """ShouldRecord returns true in every scene: TM-CE's events are not the versus scenes Slippi checks for."""
    return [(0xC2000000 | (SHOULD_RECORD & 0x01FFFFFF), 2), (0x38600001, 0x4E800020), (0x60000000, 0)]


def empty_list():
    return [(0x06000000 | (EMPTY_LIST_AT & 0x01FFFFFF), 16), (0x00D0C0DE, 0x00D0C0DE), (0xF0000000, 0),
            (0x04000000 | (GECKO_HEAP_PTR & 0x01FFFFFF), EMPTY_LIST_AT)]


def gc_fst():
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bin")
    name = "gc_fst_macos_arm64" if platform.system() == "Darwin" and platform.machine() == "arm64" else \
        "gc_fst.exe" if platform.system() == "Windows" else "gc_fst"
    return os.path.join(root, name)


def main():
    args, skip = sys.argv[1:], []
    while args[:1] == ["--skip"] and len(args) > 1:
        skip.append(args[1])
        args = args[2:]
    if len(args) < 2:
        sys.exit(__doc__)
    iso, out, sysdir = args[0], args[1], args[2] if len(args) > 2 else DEFAULT_SYS
    tmp = tempfile.mkdtemp()
    gct = os.path.join(tmp, "codes.gct")
    subprocess.run([gc_fst(), "read", iso, "codes.gct", gct], check=True)
    data = open(gct, "rb").read()
    assert data[:8] == bytes.fromhex("00D0C0DE00D0C0DE"), "codes.gct has no Gecko header"
    tm = codes(words_of(data[8:]))

    boot = [c for c in codes(words_of(open(os.path.join(sysdir, "bootloader.gct"), "rb").read()[8:]))
            if c[0] in BOOTLOADER_FUNCTIONS]
    assert len(boot) == len(BOOTLOADER_FUNCTIONS), "bootloader.gct lacks EXITransferBuffer or ProcessGecko"
    rec = [c for c in codes(recording_codes(os.path.join(sysdir, "GameSettings", "GALE01r2.ini"), skip)) if c[0] != SHOULD_RECORD]
    added = boot + rec + codes(always_record()) + codes(empty_list())

    # TM-CE's player block (0x2530) fits in Slippi's (0x2600); Slippi's own field is at 0x25FF, past TM-CE's
    tm = [c for c in tm if c[0] != EXTEND_PLAYER_BLOCK]
    clashes = [(hex(a[0]), hex(b[0])) for a in added for b in tm
               if written(a)[0] < written(b)[1] and written(b)[0] < written(a)[1]]
    if clashes:
        sys.exit(f"Slippi and TM-CE codes write the same memory: {clashes}")

    words = [w for c in tm + added for w in c[2]] + [(0xF0000000, 0)]
    with open(gct, "wb") as f:
        f.write(bytes.fromhex("00D0C0DE00D0C0DE") + b"".join(struct.pack(">II", *w) for w in words))
    shutil.copyfile(iso, out)
    subprocess.run([gc_fst(), "fs", out, "insert", "codes.gct", gct], check=True)
    shutil.rmtree(tmp)
    print(f"{out}: {len(added)} Slippi codes added ({sum(len(c[2]) for c in added) * 8} bytes)")


if __name__ == "__main__":
    main()
