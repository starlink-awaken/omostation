"""bin/ops/launchd/ 下所有 plist 必须能被 plistlib 解析 (T16-01 C2).

XML 规范禁止注释内出现连续两个半角连字符。踩过的坑:
  - com.omostation.expiry-radar        注释含 strict 档命令行与目录权限串
  - com.omostation.zhixing-host-drift  注释含目录权限串
  - com.omostation.omo-health-refresh 注释含命令行 dry-run 参数

后果是不对称的: plutil 与 launchd 的解析器更宽容会放过, 作业照常运行; 但
bin/gac/meta-doctor.py 的 plistlib 读取包在 `except Exception: continue` 里, 该 plist
会被**静默跳过**出 M2 引用/活性校验 —— 即「装了但治理看不见」, 极难察觉。

故本测试以 plistlib 为准 (T16-01 shadow 的 C2 检查项同源)。
"""

from __future__ import annotations

import plistlib
from pathlib import Path

LAUNCHD_DIR = Path(__file__).resolve().parents[2] / "bin" / "ops" / "launchd"
PLISTS = sorted(LAUNCHD_DIR.glob("*.plist"))


def test_launchd_dir_is_populated() -> None:
    assert PLISTS, "未找到任何 plist —— 测试前提不成立, 视为空转"


def test_every_launchd_plist_parses_with_plistlib() -> None:
    broken: list[str] = []
    for p in PLISTS:
        try:
            plistlib.loads(p.read_bytes())
        except Exception as exc:  # noqa: BLE001 — 汇总报错优于首错即停
            broken.append(f"{p.name}: {type(exc).__name__}: {exc}")
    assert not broken, "以下 plist 无法被 plistlib 解析 (会被 meta-doctor 静默跳过):\n" + "\n".join(broken)


def test_plist_comments_contain_no_double_hyphen() -> None:
    """直接指出病因, 比只报 ExpatError 更有可操作性。"""
    offenders: list[str] = []
    for p in PLISTS:
        for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
            if "<!DOCTYPE" in line:
                break
            stripped = line.strip()
            if stripped in ("<!--", "-->"):
                continue
            if "--" in stripped:
                offenders.append(f"{p.name}:{lineno}: {stripped[:70]}")
    assert not offenders, "以下 plist 注释含连续两个半角连字符 (XML 规范禁止):\n" + "\n".join(offenders)


def test_plist_values_have_no_bare_ampersand() -> None:
    """`<string>` 值里的裸 & 非法 (须写成 &amp;), 否则 plistlib 解析失败.

    实测踩过: com.omostation.arch-health-weekly.plist 的 ProgramArguments 写成
    `cd ... && bash ...`, 而同目录其他 plist 都正确写作 `&amp;&amp;`。
    该文件从未安装到宿主, 故 T16-01 C2 (只扫 ~/Library/LaunchAgents) 一直看不到它
    —— 是本测试的全目录覆盖才把它翻出来。
    """
    import re

    bare = re.compile(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9A-Fa-f]+);)")
    offenders: list[str] = []
    for p in PLISTS:
        for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
            if bare.search(line):
                offenders.append(f"{p.name}:{lineno}: {line.strip()[:70]}")
    assert not offenders, "以下行含裸 & (应转义为 &amp;):\n" + "\n".join(offenders)
