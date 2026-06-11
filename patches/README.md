# KEMS v7 修复补丁包

> 目标路径: `~/Documents/@学习进化/`
> 拷贝命令: `cp -r ~/Workspace/patches/* ~/Documents/@学习进化/_patches/`

---

## P0 — README 实现状态标注

**源文件**: `_knowledge/10-systems/KEMS/README.md`
**补丁**: `KEMS-README-v7-reconcile.md`

当前 README 被 daemon 覆盖为 v7.0，但声明的 6 契约/8 门禁/38 规则等未实现。
补丁添加了"实现状态"列 (✅/📋/❌)，真实反映：
- ✅ 已实现: 信号总线、l4-kernel、跨域7/7、PIPE-INGEST
- 📋 待实现: 6契约、8门禁、Verifier

**操作**: 用补丁替换 `_knowledge/10-systems/KEMS/README.md`

---

## P1 — Write Contract (首份KEMS协议)

**目标路径**: `_knowledge/10-systems/KEMS/.kems/_protocol/01-write-contract.md`
**补丁**: `KEMS-write-contract.md`

四份子契约：
1. 控制面→事实面: 可溯源的 facts 写入
2. 事实面→知识面: 指针引用而非复制
3. 资料面→控制面: 变更信号通知
4. 跨域写入: source_domain 标记

**操作**: 拷贝到 `.kems/_protocol/01-write-contract.md`

---

## P1 — l4-kernel 5门禁扩展

**目标路径**: `_control/l4-kernel.sh`
**当前**: 1项门禁 (frontmatter完整性)
**扩展到5项**:

| 门禁 | 当前 | 扩展后 |
|------|:----:|:------:|
| ① frontmatter 完整性 | ✅ | ✅ |
| ② 跨域引用有效性 | ❌ | 添加: grep 断裂 [[wikilink]] |
| ③ facts.md 可溯源性 | ❌ | 添加: 每条 fact 有来源? |
| ④ signals 噪音率监控 | ❌ | 添加: real/total < 10% 报警 |
| ⑤ 控制规则完整性 | ✅ CR01-CR03 | ✅ |

**操作**: 修改 `_control/l4-kernel.sh` 的 check 段

---

## 补丁安装

```bash
# 1. 拷贝补丁
cp ~/Workspace/patches/KEMS-README-v7-reconcile.md \
   ~/Documents/@学习进化/_knowledge/10-systems/KEMS/README.md

cp ~/Workspace/patches/KEMS-write-contract.md \
   ~/Documents/@学习进化/_knowledge/10-systems/KEMS/.kems/_protocol/01-write-contract.md

# 2. Git 提交
cd ~/Documents/@学习进化
git add _knowledge/10-systems/KEMS/README.md \
       _knowledge/10-systems/KEMS/.kems/_protocol/01-write-contract.md
git commit -m "docs: KEMS README v7实现状态标注 + 首份Write Contract"

# 3. l4-kernel 5门禁: 手动编辑 _control/l4-kernel.sh check段
#    在 frontmatter 检查后追加 ②-④ 三项检查
```
