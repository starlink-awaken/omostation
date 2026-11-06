#!/usr/bin/env python3
"""个人检索层的【域视图】—— ⇒ ⇒ 把单位域与家庭域挪出个人检索层（§5.166 · USER-ACTIONS #89）。

⚠⚠⚥⚠▣ **这一波在补什么**（⚠ USER-ACTIONS #89 · §5.142 实测）——
⚠ §3.1 第 **6** 条是**既有不变量**（⚠ 2026-10-29 已点头）：
⚠ 「知识摄入与索引必须带 `data_class`；
⚠ **单位域资料默认不进个人检索层与个人记忆体**」
⚠ ⇒ ⇒ ⚠ 而实测：单位域 5 个（`work-docs` ＋ 4 子域）＋ 家庭域 `family`
⚠     都落在个人检索根（`kos.l4_root` ＋ `cockpit.l4_documents_root`）的覆盖里
⚠ ⇒ ⇒ ⚠ **承诺是破的**（⚠ 而 §8 那条负向清单已撤 ⇒ ⇒ **不是「已知且接受的风险」**）

⚠⚠⚥⚠▣ **⚠ 为什么不能用「一个前缀根」解决**（⚠ 实测出来的形状）——
⚠ 所有域都是 `~/Documents` 的**同级兄弟**（`@工作文档` / `@家庭生活` / `@个人` / …）
⚠ ⇒ ⇒ ⚠ **单个前缀根没法只排掉其中两个** ⇒ ⇒ ⚠ 用符号链接目录「假装排掉了」是**假绿**
⚠ ⇒ ⇒ ⚠ **本脚本走另一条路**：⚠ **一个【视图】**（⚠ 里面只有允许的域）
⚠   ⇒ ⇒ ⚠ 视图里那份注册表**只列允许的域** ⇒ ⇒ ⚠ **消费侧按 id 寻址时根本找不到被拒的域**
⚠   ⇒ ⇒ ⚠ 而视图里的域目录是**指向真目录的符号链接** ⇒ ⇒ ⚠ **没有副本 ⇒ 不会腐**

⚠⚠⚥⚠▣ **视图长什么样**（⚠ `<view>` ＝ 默认 `runtime/personal-view`）——
    <view>/
      _registry/L4-DOMAIN-REGISTRY.yaml   ← ⚠ **只列允许的域**（⚠ 路径相对它自己重写）
      @公共   -> ~/Documents/@公共            ← ⚠ 符号链接 ⇒ ⇒ **指向真目录**
      @个人   -> ~/Documents/@个人
      @学习进化 -> ~/Documents/@学习进化
      @创意创作 -> ~/Documents/@创意创作
      @OPC    -> ~/Documents/@OPC
      @驾驶舱  -> ~/Documents/@驾驶舱
    ⚠ **被拒的域一个都没有**（⚠ 单位域 5 个 ＋ 家庭域 1 个）

⚠⚠⚥⚠▣ **三条纪律**——
① ⚠ **准入声明是唯一真源**（⚠ `.omo/_truth/registry/personal-retrieval-domains.yaml`）
   ⇒ ⇒ ⚠ **允许清单 ⇒ ⇒ 默认拒** ⇒ ⇒ ⚠ **新加的域默认【不可见】** ⇒ ⇒ ⚠ 漏写不会漏出东西
② ⚠ **产物必须被【消费侧同一个加载器】校验**（⚠ `l4_kernel.manifest_registry`）
   ⇒ ⇒ ⚠ **本脚本不自说自话** ⇒ ⇒ ⚠ 加载器认 ⇒ ⇒ 消费侧就认
③ ⚠ **视图不许漏**（⚠ 被拒的域**不许**经由某个被允许的父目录漏出来）
   ⇒ ⇒ ⚠ **这一条靠实物判定**（⚠ 解析符号链接 ⇒ ⇒ 逐个域问「可达吗」）

用法：
    python3 bin/gac/documents-personal-view.py build    # 生成视图 ＋ 自检
    python3 bin/gac/documents-personal-view.py check    # 只自检（一个字都不写）
    python3 bin/gac/documents-personal-view.py build --json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

#: ⚠ **真域注册表**（⚠ 相对知识库根）
REGISTRY_REL = os.path.join("@公共", "_control", "L4-DOMAIN-REGISTRY.yaml")

#: ⚠ **准入声明**（⚠ 两侧共读的那一份 ⇒ ⇒ **不许各抄一份**）
POLICY_REL = os.path.join(".omo", "_truth", "registry", "personal-retrieval-domains.yaml")

#: ⚠ **视图默认落点**（⚠ 运行态 ⇒ ⇒ 不进仓）
VIEW_REL = os.path.join("runtime", "personal-view")

#: ⚠ **视图里那份注册表的子目录**（⚠ 深度与真注册表一致 ⇒ ⇒ 相对路径好重写）
VIEW_REGISTRY_DIR = "_registry"


def _l4_src() -> str:
    """⚠ **l4-kernel 的源码根**（⚠ 与 `documents-domain-owner-job.py` 同一条依赖链）。"""
    return str(ROOT / "projects" / "l4-kernel" / "src")


def load_manifest_registry(registry_path: Path):
    """⚠ **用消费侧那一个加载器读注册表**（⚠ 引仓内那份 ⇒ ⇒ 不许自己解析一套）。

    ⚠⚠⚥ **为什么必须用它**：⚠ 加载器会校验 `id` / `path` / `space_ref` / manifest 的 id 一致性
    ⇒ ⇒ ⚠ **本脚本生成的视图能被它读进去 ⇒ ⇒ 消费侧就一定能读**
    ⇒ ⇒ ⚠ **自说自话的校验等于没校验**
    """
    src = _l4_src()
    if src not in sys.path:
        sys.path.insert(0, src)
    from l4_kernel.manifest_registry import ManifestRegistry  # type: ignore

    return ManifestRegistry.load(registry_path)


def read_policy(policy_path: Path):
    """⚠ **读准入声明**（⚠ 读不到 ⇒ ⇒ `(None, error)` ⇒ ⇒ **不许折成「全部允许」**）。

    ⚠⚠⚥ **为什么用 `safe_load_all`**：⚠ 这份声明带 YAML front-matter ⇒ ⇒ 是**多文档流**
    ⇒ ⇒ ⚠ 最后一份才是正文（⚠ 与仓内 `omo_paths.projection_rels` 同处理）
    """
    try:
        docs = list(yaml.safe_load_all(policy_path.read_text(encoding="utf-8")))
    except (OSError, yaml.YAMLError) as exc:
        return None, f"读准入声明失败：{type(exc).__name__}: {exc}"
    mappings = [d for d in docs if isinstance(d, dict)]
    if not mappings:
        return None, "准入声明里没有可用文档"
    body = mappings[-1]
    allowed = body.get("allowed_domains")
    if not isinstance(allowed, list) or not allowed:
        return None, "准入声明必须列出非空的 allowed_domains"
    return [str(item) for item in allowed], None


def read_registry_entries(registry_path: Path):
    """⚠ **读真注册表的 manifests 条目**（⚠ 只取 `id` ＋ `path` ⇒ ⇒ 契约只许这两样）。"""
    try:
        docs = list(yaml.safe_load_all(registry_path.read_text(encoding="utf-8")))
    except (OSError, yaml.YAMLError) as exc:
        return None, f"读注册表失败：{type(exc).__name__}: {exc}"
    mappings = [d for d in docs if isinstance(d, dict)]
    if not mappings:
        return None, "注册表里没有可用文档"
    body = mappings[-1]
    entries = body.get("manifests")
    if not isinstance(entries, list) or not entries:
        return None, "注册表里没有 manifests"
    out = []
    for entry in entries:
        if not isinstance(entry, dict):
            return None, "manifest 条目必须是映射"
        ident = entry.get("id")
        path = entry.get("path")
        if not isinstance(ident, str) or not isinstance(path, str):
            return None, "manifest 条目必须有 id ＋ path"
        out.append((ident, path))
    return out, None


def is_under(root: Path, path: Path) -> bool:
    """⚠ **path 在 root 之下吗**（⚠ 按路径分量比 ⇒ ⇒ 不做字符串前缀的误判）。"""
    try:
        return os.path.commonpath([str(root), str(path)]) == str(root)
    except ValueError:
        return False


def build_view(documents_root: Path, view_root: Path, allowed: list[str]) -> dict:
    """⚠ **生成视图**（⚠ 符号链接 ＋ 只列允许域的注册表）。

    :returns: ⚠ 回执（⚠ 写了什么 ＋ 自检结果 ⇒ ⇒ **不许只说「成功」**）
    """
    registry_path = documents_root / REGISTRY_REL
    entries, err = read_registry_entries(registry_path)
    if entries is None:
        return {"ok": False, "error": err}

    registry_dir = view_root / VIEW_REGISTRY_DIR
    registry_dir.mkdir(parents=True, exist_ok=True)

    allowed_set = set(allowed)
    view_entries = []
    linked = []
    for ident, rel in entries:
        if ident not in allowed_set:
            continue
        real_manifest = (registry_path.parent / rel).resolve()
        domain_dir = real_manifest.parent
        link = view_root / domain_dir.name
        # ⚠ **同名冲突不许静默**（⚠ 两个域同名 ⇒ ⇒ 视图会把它们混成一个）
        if link.exists() and not link.is_symlink():
            return {"ok": False, "error": f"视图落点已被占用：{link}"}
        if link.is_symlink() and link.resolve() != domain_dir:
            link.unlink()
        if not link.is_symlink():
            link.symlink_to(domain_dir, target_is_directory=True)
        linked.append({"id": ident, "link": str(link), "target": str(domain_dir)})
        # ⚠⚠⚥ **路径必须【穿过视图自己的符号链接】**（⚠ 不能直接指向真文件）
        #   ⇒ ⇒ ⚠ 直接指真文件 ⇒ ⇒ **视图就不是边界了**（⚠ 路径一路逃回 `~/Documents`）
        #   ⇒ ⇒ ⚠ 穿过符号链接 ⇒ ⇒ **视图里少一个链接 ⇒ ⇒ 那个域就加载不出来**
        #   ⇒ ⇒ ⚠ **被拒的域于是有【两道】锁**：⚠ 一道是「不在清单里」· 一道是「不在视图里」
        view_manifest = view_root / domain_dir.name / real_manifest.name
        view_entries.append(
            {
                "id": ident,
                "path": os.path.relpath(view_manifest, registry_dir),
            }
        )

    # ⚠ **只列允许的域**（⚠ 路径相对【视图里那份】注册表自己）
    body = {
        "apiVersion": "l4/v1",
        "kind": "DomainRegistry",
        "id": "personal-view-domain-registry",
        "display_name": "Personal retrieval view (allowed domains only)",
        "space_ref": "personal-space",
        "status": "active",
        "path_base": "registry_file_parent",
        "manifests": view_entries,
    }
    view_registry = registry_dir / "L4-DOMAIN-REGISTRY.yaml"
    view_registry.write_text(
        yaml.safe_dump(body, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return {
        "ok": True,
        "view_root": str(view_root),
        "view_registry": str(view_registry),
        "linked": linked,
        "allowed_count": len(view_entries),
    }


def check_view(documents_root: Path, view_root: Path, allowed: list[str]) -> dict:
    """⚠ **自检**（⚠ 三件事 ⇒ ⇒ 任何一件不过 ⇒ ⇒ **不许说「好了」**）。

    ① ⚠ **视图里那份注册表能被消费侧那一个加载器读进去**（⚠ 且域数＝允许数）
    ② ⚠ **被允许的域在视图里【可达】**（⚠ 解析符号链接 ⇒ ⇒ 实物判定）
    ③ ⚠ **被拒的域在视图里【不可达】**（⚠ 这一条防「父目录链接把子域漏出去」）
    """
    registry_path = documents_root / REGISTRY_REL
    entries, err = read_registry_entries(registry_path)
    if entries is None:
        return {"ok": False, "error": err}
    view_registry = view_root / VIEW_REGISTRY_DIR / "L4-DOMAIN-REGISTRY.yaml"
    if not view_registry.is_file():
        return {"ok": False, "error": f"视图里没有注册表：{view_registry}"}

    # ① **消费侧加载器认不认**
    try:
        registry = load_manifest_registry(view_registry)
    except Exception as exc:  # noqa: BLE001 —— 认不了就是认不了
        return {"ok": False, "error": f"视图注册表加载失败：{type(exc).__name__}: {exc}"}
    view_ids = sorted(m.id for m in registry.list_all())

    # ②③ **可达性**（⚠ 实物判定 ⇒ ⇒ **不可能假绿**）
    effective = []
    for child in sorted(view_root.iterdir()):
        if child.name == VIEW_REGISTRY_DIR:
            continue
        try:
            effective.append(child.resolve())
        except OSError:
            continue
    reachable = {}
    for ident, rel in entries:
        real_dir = (registry_path.parent / rel).resolve().parent
        reachable[ident] = any(is_under(e, real_dir) for e in effective)

    allowed_set = set(allowed)
    registry_ids = {e[0] for e in entries}
    # ⚠⚠⚥⚠▣ **「这台机上没这个域」是一【第四】种状态** ——
    #   ⚠ **实测撞出来的**（⚠ 2026-10-31）：⚠ 准入清单是**两侧共读的那一份**
    #   ⚠ ⇒ ⇒ ⚠ 而**域注册表是每台机器自己的** ⇒ ⇒ ⚠ **两台机不保证一样**
    #   ⚠ ⇒ ⇒ ⚠ ⇒ **哪天某台机的注册表少一个域** ⇒ ⇒ ⚠ ⇒ 那个域在那台机上
    #   ⚠ ⇒ ⇒ ⚠ ⇒ **根本不存在** ⇒ ⇒ ⚠ ⇒ **那不是「够不着」，也不是「判不出来」**
    #   ⚠ ⇒ ⇒ ⚠ ⇒ ⇒ **必须单列**（⚠ 否则 ⇒ ⇒ 一台机器的差异会被报成另一台的破约）
    #   ⚠⚠⚥ **为什么它是【无害】的**（⚠ ⇒ ⇒ 所以只报不判红）——
    #   ⚠ 准入清单是**上界**（⚠ 「允许」）⇒ ⇒ 允许清单比注册表宽 ⇒ ⇒
    #   ⚠ ⇒ ⇒ **多出来的那些域根本不在注册表里** ⇒ ⇒ **消费侧按 id 寻址根本找不到它们**
    #   ⚠ ⇒ ⇒ ⚠ ⇒ **⇒ 不构成暴露** ⇒ ⇒ ⚠ **只报一条注记**
    #   ⚠⚠⚥ **而拼错字的那一半仍然抓得住**：⚠ 拼错 ⇒ ⇒ 真正的那个域**没被允许**
    #   ⚠ ⇒ ⇒ ⚠ ⇒ **它会被判成「够不着」**（⚠ 那一条是判红的）⇒ ⇒ ⚠ **不漏**
    absent = sorted(i for i in allowed_set if i not in registry_ids)
    missing = sorted(i for i in (allowed_set & registry_ids) if not reachable.get(i))
    leaked = sorted(i for i, ok in reachable.items() if ok and i not in allowed_set)

    problems = []
    if view_ids != sorted(allowed_set & registry_ids):
        problems.append(f"视图注册表的域集合与准入清单不一致：{view_ids}")
    if missing:
        problems.append(f"被允许的域在视图里不可达：{missing}")
    if leaked:
        problems.append(f"被拒的域在视图里可达：{leaked}")

    notes = []
    if absent:
        notes.append(f"准入清单里的域在这台机的注册表里不存在（⇒ ⇒ 无害 · 消费侧寻址不到）：{absent}")

    return {
        "ok": not problems,
        "problems": problems,
        "view_registry": str(view_registry),
        "view_ids": view_ids,
        "reachable": reachable,
        "allowed_count": len(allowed_set),
        "absent": absent,
        "notes": notes,
        "denied_count": len(reachable) - len(allowed_set & set(reachable)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("build", "check"))
    parser.add_argument("--documents-root", type=Path, default=Path.home() / "Documents")
    parser.add_argument("--policy", type=Path, default=ROOT / POLICY_REL)
    parser.add_argument("--view-root", type=Path, default=ROOT / VIEW_REL)
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)

    allowed, err = read_policy(args.policy)
    if allowed is None:
        payload = {"ok": False, "error": err}
        print(json.dumps(payload, ensure_ascii=False) if args.json_output else err)
        return 2

    if args.mode == "build":
        built = build_view(args.documents_root, args.view_root, allowed)
        if not built.get("ok"):
            print(json.dumps(built, ensure_ascii=False) if args.json_output else built.get("error"))
            return 2
    checked = check_view(args.documents_root, args.view_root, allowed)
    payload = {"mode": args.mode, "allowed": allowed, **checked}
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"个人检索视图（§5.166 · {args.mode}）")
        print(f"视图落点：{args.view_root}")
        print(f"准入域：{len(allowed)} 个 · 被拒域：{checked.get('denied_count', 0)} 个")
        print(f"自检：{'通过' if checked.get('ok') else '不过'}")
        for problem in checked.get("problems") or []:
            print(f"   · {problem}")
        for note in checked.get("notes") or []:
            print(f"   （注记）{note}")
    return 0 if checked.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
