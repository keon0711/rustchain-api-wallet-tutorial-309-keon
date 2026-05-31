#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import re
import shlex
import shutil
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
RUSTCHAIN = Path("/Users/keon/workspace/projects/Rustchain")
WALLET = "RTC1410e82d545ce0b3ffd21ca83e2465a8f2c3a64e"
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
TITLE = "RustChain API and Wallet Tutorial: Live Checks Without Secrets"
VIDEO = "rustchain-api-wallet-tutorial-309.mp4"


PY_WARN = "ignore:Unverified HTTPS request"
UV_DEPS = ["uv", "run", "--with", "requests", "--with", "cryptography", "--with", "mnemonic"]


COMMANDS = [
    {
        "name": "Check live node health",
        "cmd": [
            "python3",
            "-c",
            "import json,urllib.request; print(json.dumps(json.load(urllib.request.urlopen('https://rustchain.org/health', timeout=15)), indent=2))",
        ],
    },
    {
        "name": "Inspect wallet CLI commands",
        "cmd": [*UV_DEPS, "python", "tools/rustchain_wallet_cli.py", "--help"],
    },
    {
        "name": "Read current epoch",
        "cmd": [*UV_DEPS, "python", "tools/rustchain_wallet_cli.py", "epoch"],
        "env": {"PYTHONWARNINGS": PY_WARN},
    },
    {
        "name": "Summarize active miners",
        "cmd": [
            "bash",
            "-lc",
            "PYTHONWARNINGS='ignore:Unverified HTTPS request' uv run --with requests --with cryptography --with mnemonic python tools/rustchain_wallet_cli.py miners | python3 -c 'import sys,json; data=json.load(sys.stdin); miners=data.get(\"miners\", data if isinstance(data,list) else data.get(\"items\", [])); print(\"active_miners\", len(miners)); print(json.dumps(miners[:3], indent=2))'",
        ],
    },
    {
        "name": "Check receiving wallet balance",
        "cmd": [*UV_DEPS, "python", "tools/rustchain_wallet_cli.py", "balance", WALLET],
        "env": {"PYTHONWARNINGS": PY_WARN},
    },
    {
        "name": "Check public wallet history",
        "cmd": [
            "python3",
            "-c",
            f"import json,urllib.request; print(json.dumps(json.load(urllib.request.urlopen('https://rustchain.org/wallet/history?miner_id={WALLET}', timeout=15)), indent=2))",
        ],
    },
    {
        "name": "Check mining lottery eligibility",
        "cmd": [
            "python3",
            "-c",
            f"import json,urllib.request; print(json.dumps(json.load(urllib.request.urlopen('https://rustchain.org/lottery/eligibility?miner_id={WALLET}', timeout=15)), indent=2))",
        ],
    },
]


NARRATION = """
This RustChain tutorial shows how to inspect the live network and a receiving
wallet without exposing private keys.

The first check is the public health endpoint. It proves that the node is
responding, that the database is writable, and which RustChain version is live.

Next, the RustChain wallet command line tool is opened in an isolated uv
environment. The help output shows the available commands for wallet creation,
balance checks, signed transfers, transaction history, miner listing, and epoch
status. In this tutorial we only use read-only commands.

The epoch command gives the current network slot, enrolled miner count, epoch
pot, and total supply. Then the miners command lists active miner attestations.
This is useful for checking whether the network has recent real participants
before you try to mine or monitor rewards.

The wallet balance command queries a receiving wallet by miner id. It does not
need a private key because it only reads public ledger state. The history call
shows the same wallet's visible transactions, and the lottery eligibility call
explains whether that wallet is currently scheduled to produce a slot.

The safe operator pattern is simple: use public API checks for health, epoch,
miners, balance, history, and eligibility; keep private keys out of recordings;
only use signed transfer commands when you are intentionally sending RTC from a
local keystore.
"""


ANSI = re.compile(r"\x1b\[[0-9;]*m")


def run(spec: dict) -> str:
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    if spec.get("env"):
        env = {**os.environ.copy(), **spec["env"]}
        env.pop("VIRTUAL_ENV", None)
    result = subprocess.run(
        spec["cmd"],
        cwd=RUSTCHAIN,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
    )
    output = ANSI.sub("", result.stdout)
    return f"$ {shlex.join(spec['cmd'])}\n{output}".strip()


def capture() -> list[dict[str, str]]:
    captured = []
    for spec in COMMANDS:
        output = run(spec)
        captured.append({"name": spec["name"], "cmd": spec["cmd"], "output": output})
    (ROOT / "captured_outputs.json").write_text(json.dumps(captured, indent=2) + "\n", encoding="utf-8")
    return captured


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        if not raw:
            lines.append("")
            continue
        words = raw.split()
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if draw.textbbox((0, 0), candidate, font=font)[2] <= width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


def clamp_output(text: str, max_lines: int = 20) -> str:
    lines = []
    for line in text.splitlines():
        if ROOT.as_posix() in line:
            line = line.replace(ROOT.as_posix(), ".")
        if len(line) > 108:
            line = line[:105] + "..."
        lines.append(line)
    if len(lines) <= max_lines:
        return "\n".join(lines)
    return "\n".join(lines[: max_lines - 2] + ["...", lines[-1]])


def render_frames(captured: list[dict[str, str]]) -> int:
    frames_dir = ROOT / "frames"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(exist_ok=True)

    title_font = ImageFont.truetype(BOLD, 27)
    heading_font = ImageFont.truetype(BOLD, 23)
    body_font = ImageFont.truetype(FONT, 19)
    mono_font = ImageFont.truetype(FONT, 14)
    small_font = ImageFont.truetype(FONT, 15)

    scenes = [
        {
            "duration": 14,
            "heading": "Read-only RustChain checks",
            "body": "This walkthrough uses live RustChain endpoints and the local wallet CLI. It shows health, epoch, miners, wallet balance, history, and eligibility without revealing private keys.",
            "terminal": "$ curl https://rustchain.org/health\n$ rustchain-wallet epoch\n$ rustchain-wallet balance RTC...",
        }
    ]
    for item in captured:
        scenes.append(
            {
                "duration": 16,
                "heading": item["name"],
                "body": "Actual command output captured locally for this tutorial.",
                "terminal": clamp_output(item["output"]),
            }
        )
    scenes.append(
        {
            "duration": 16,
            "heading": "Safe wallet rule",
            "body": "Public reads are safe to record. Private keys, seed phrases, and signed transfer commands should stay out of videos unless you are intentionally sending funds.",
            "terminal": "$ rustchain-wallet balance YOUR_WALLET\n$ rustchain-wallet history YOUR_WALLET\n# no seed phrase, no private key, no transfer here",
        }
    )

    fps = 2
    frame_index = 0
    total_duration = sum(scene["duration"] for scene in scenes)
    total_frames = total_duration * fps

    for scene_index, scene in enumerate(scenes):
        for _ in range(scene["duration"] * fps):
            second = frame_index / fps
            img = Image.new("RGB", (960, 540), (8, 18, 20))
            draw = ImageDraw.Draw(img)

            for y in range(540):
                t = y / 539
                color = (
                    int(8 + 18 * t),
                    int(18 + 22 * t),
                    int(20 + 24 * t),
                )
                draw.line((0, y, 960, y), fill=color)

            grid_offset = int(second * 18) % 48
            for x in range(-48 + grid_offset, 960, 48):
                draw.line((x, 0, x + 220, 540), fill=(18, 44, 48), width=1)
            for y in range(-48 + grid_offset, 540, 48):
                draw.line((0, y, 960, y), fill=(17, 36, 39), width=1)

            draw.text((34, 27), TITLE, fill=(245, 250, 250), font=title_font)
            draw.text((40, 86), scene["heading"], fill=(45, 212, 191), font=heading_font)
            y = 124
            for line in wrap_text(draw, scene["body"], body_font, 870)[:4]:
                draw.text((42, y), line, fill=(226, 232, 240), font=body_font)
                y += 26

            draw.rounded_rectangle((38, 222, 922, 494), radius=8, fill=(4, 12, 14), outline=(45, 212, 191), width=2)
            draw.rounded_rectangle((38, 222, 922, 252), radius=8, fill=(16, 34, 37))
            draw.text((56, 230), "terminal capture", fill=(203, 213, 225), font=small_font)
            term_y = 264
            for line in scene["terminal"].splitlines()[:22]:
                color = (134, 239, 172) if line.startswith("$") else (226, 232, 240)
                if line.startswith("#"):
                    color = (148, 163, 184)
                draw.text((58, term_y), line, fill=color, font=mono_font)
                term_y += 16

            progress = int(884 * (frame_index / max(1, total_frames - 1)))
            draw.rounded_rectangle((38, 512, 922, 523), radius=5, fill=(15, 23, 42))
            draw.rounded_rectangle((38, 512, 38 + progress, 523), radius=5, fill=(45, 212, 191))
            img.save(frames_dir / f"frame_{frame_index:04d}.png")
            frame_index += 1

    return total_duration


def write_page(duration: int) -> None:
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(TITLE)}</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background: #081214; color: #e5f4f3; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 32px 20px 48px; }}
    h1 {{ font-size: 34px; margin: 0 0 12px; }}
    p, li {{ line-height: 1.55; color: #cbd5e1; }}
    video {{ width: 100%; aspect-ratio: 16 / 9; background: #000; border: 1px solid #2dd4bf; }}
    code {{ color: #99f6e4; }}
    a {{ color: #5eead4; }}
  </style>
</head>
<body>
<main>
  <h1>{html.escape(TITLE)}</h1>
  <p>Submission artifact for RustChain issue #309. Duration: {duration} seconds.</p>
  <video controls preload="metadata" src="{VIDEO}"></video>
  <h2>What this demonstrates</h2>
  <ul>
    <li>Live RustChain node health and epoch checks.</li>
    <li>Actual <code>tools/rustchain_wallet_cli.py</code> usage.</li>
    <li>Active miner summary from the public API.</li>
    <li>Read-only balance, history, and eligibility checks for the receiving wallet.</li>
    <li>No private keys, seed phrases, or signed transfers are shown.</li>
  </ul>
  <p>Direct MP4: <a href="{VIDEO}">{VIDEO}</a></p>
</main>
</body>
</html>
"""
    (ROOT / "index.html").write_text(page, encoding="utf-8")


def main() -> None:
    captured = capture()
    duration = render_frames(captured)
    (ROOT / "narration.txt").write_text(textwrap.dedent(NARRATION).strip() + "\n", encoding="utf-8")
    subprocess.run(["say", "-r", "153", "-o", "narration.aiff", "-f", "narration.txt"], cwd=ROOT, check=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-framerate",
            "2",
            "-i",
            "frames/frame_%04d.png",
            "-i",
            "narration.aiff",
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "29",
            "-r",
            "24",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "48k",
            "-movflags",
            "+faststart",
            VIDEO,
        ],
        cwd=ROOT,
        check=True,
    )
    write_page(duration)
    (ROOT / "metadata.json").write_text(
        json.dumps(
            {
                "title": TITLE,
                "duration_sec": duration,
                "bounty": "RustChain issue #309",
                "wallet": WALLET,
                "source": "Actual RustChain API and wallet CLI command captures plus generated narration.",
                "safety": "Read-only public API calls only; no private keys or signed transfers.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
