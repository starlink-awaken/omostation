---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-10-03
type: ssot
name: zsh-split-audit
description: "事后审计会话转写，量化 Agent 是否违反 zsh 分词纪律（`VAR=\"a b c\"; for x in $VAR` 在 zsh 下只迭代 1 次且 $x 是整串）。含假零断言与噪声判别，把「无法事前拦截」的教训变成可测指标。"
---

# zsh Split Audit

## 1. 何时使用

- 想**量化**「zsh 分词纪律」是否被遵守（`AGENTS.md` §7 首条）；
- 复盘某次「批量删除前的逐项安全检查」是否因**静默塌缩**而失效（四列都有值、却描述了不存在的路径）；
- 怀疑某段时间的批量脚本「少迭代 / 只处理了一个目标」但查不出原因。

## 2. 为什么需要这个技能

zsh **对参数展开不做 word splitting**（只有**命令替换**会）⇒ `VAR="a b c"; for x in $VAR` 只迭代 **1 次**、`$x` 是**整串**。危险之处是它**不报错**，输出看着还正常。

它只发生在 **Agent 临时写的一次性 Bash 命令**里 —— 不进仓、不过 hook ⇒ **事前无法拦截**（没有可加的 gate）。但每条命令都落在**会话转写**里 ⇒ **事后可以审计**。本技能就是那件审计工具。

> 背景实证（2026-10-02）：该陷阱**早已记入 memory**（含 4 个变体），我在「批量删前安全检查」里**明知已记录仍照踩** ⇒ 结论「记住了 ≠ 防线」。加固分三层：memory ✅ / `AGENTS.md` §7（协议层，PR #4600）✅ / **本技能（可度量层）**。

## 3. 怎么做

```bash
# 默认: 取当前项目目录下最新的会话转写
python3 .agents/skills/zsh-split-audit/zsh_split_audit.py

# 指定转写 / 多份
python3 .agents/skills/zsh-split-audit/zsh_split_audit.py <a.jsonl> [<b.jsonl> …]

# 机器可读
python3 .agents/skills/zsh-split-audit/zsh_split_audit.py --json
```

**读输出**：`真候选` 才是需要人工定夺的违规；`bash-destined` / `python 内嵌 bash` / `self-test` 三类**免责**。

## 4. 判据

```python
SCAN = re.compile(r'\bfor\s+(\w+)\s+in\s+\$\{?(\w+)\}?(?=[\s;|&)\]])')
```

命中后两道排除：① 同命令内存在 `VAR=(` ⇒ 数组（安全形式之一），跳过；② 同命令内**没有** `VAR=` 赋值 ⇒ 不是本模式，跳过。

`$( … )` 命令替换与 `${=VAR}`（zsh 显式分词）**天然不匹配**该正则，无需额外排除。

### 噪声判别（不做这一步，命中数没有意义）

| 类别 | 判别特征 | 处置 |
|---|---|---|
| `bash-destined` | 命令体是 `cat > *.sh <<'BASH_EOF'` 一类 heredoc，写出的 `.sh` 由 **bash** 执行 | 免责（bash 下 `for x in $VAR` 正确分词） |
| `python 内嵌 bash` | `python3 - <<'PYEOF'` 里作为**字符串**存在的 bash 片段（常用来自动改写 shell 测试） | 免责（最终仍由 bash 跑） |
| `self-test` | 审计/验证命令自己在构造反例（含 `expect=5 got=` 之类） | 免责 |
| `真候选` | 其余，尤其变量来自 `VAR="a b c"` 或 `VAR=$(…)` 且**就在当前 shell 里循环** | **需人工定夺** |

## 5. 四个必须知道的坑

1. **命令不在顶层 `"command"` 键**。真实结构是 `.providerData.arguments` —— 一个**二次编码的 JSON 字符串** `{"command": "..."}`；`.providerData.argumentsDisplayText` 是同样内容的展示副本。
   首版审计器只找 `'"command"'` ⇒ **命中 0**，是**假零**（差点据此宣布「零违规」）。
2. **必须带假零断言**：扫到 0 条命令就**非零退出**。否则「扫错键名 ⇒ 0 命中 ⇒ 看起来完全合规」这种**假绿**无法察觉。
3. **同一命令在多个记录里重复出现**（`arguments` / `argumentsDisplayText` / 回显），必须按 `(md5(命令), 变量名)` 去重，否则命中数虚高。
4. **命令里可能含「字面 `\n`」（转义换行）** ⇒ `\bfor` 会因前面是 `n`（词字符）而**失配 ⇒ 漏报**。
   实测样本：`python 内嵌 bash` 片段常以 `src += '\nfor s in $VAR'` 形式存储。脚本已做 `cmd.replace("\\n", "\n")` 归一化
   —— **这一处是自证时发现的**：不归一化会静默少报一类。

> 另：默认的转写探测按「cwd 逐级祖先 → 全部项目目录取最新」两级回退；因为项目目录是按 **workspace 根** slug 的，
> 只按 cwd 一级在 **worktree**（`~/ws-<session>`）里会直接报「未找到转写」（实测踩到）。

## 6. 基线与验收口径

2026-10-03 全量运行（单个长会话，转写 792 MB）：

```
扫描到命令/参数串: 14576
去重后唯一「可疑命令×变量」组合: 19
  ── 真候选: 3  ($EVENTS / $WS / $DIRS)
  ── bash-destined(免): 9
  ── python 内嵌 bash(免): 6
  ── self-test(免): 1
```

（`$DIRS` 就是当天那次「批量删前安全检查」塌缩。）

⇒ **验收口径**：跑一次审计，看 `真候选` 是否归零。这把「下次会不会再犯」从**凭印象**变成**可测**。
⚠️ 但注意：审计是**事后**的，不能替代事前纪律 —— 它只回答「有没有犯」，不阻止「正在犯」。
