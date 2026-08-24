# 场景激活手册 (Scene Activation Playbook)

> 目标: 将场景激活率从 25% (2/8) 提升到 70% (6/8)
> 当前阻碍: 7/10 场景卡在 `pending_business_confirmation`

---

## 一、场景激活状态总览

| 场景 | 阶段 | 激活 | 审批 | 阻碍 | 可安全激活 |
|------|------|------|------|------|-----------|
| agora-bos-gateway | routine | active | approved | - | ✅ 已激活 |
| knowledge-ingest (v2) | assisted | allowed | confirmed | - | ✅ 已激活 |
| document-review | shadow | allowed | confirmed | 需 30 样本 + 校准 | 🟡 数据积累中 |
| engineering-delivery-dogfood | shadow | allowed | confirmed | OMO 准入证据 | 🟡 工具依赖 |
| **project-supervision (v2)** | shadow | preview | pending | 无 | ✅ **可激活** |
| **periodic-reporting (v2)** | shadow | preview | pending | 无 | ✅ **可激活** |
| **meeting-supervision (v2)** | shadow | preview | pending | 无 | ✅ **可激活** |
| research-pipeline (v2) | shadow | preview | pending | 无 | ✅ 可激活 |
| knowledge-curation | shadow | preview | pending | 无 | ✅ 可激活 |
| unified-inbox | shadow | preview | pending | 无 | ✅ 可激活 |

---

## 二、优先激活场景 (内部管道, 低风险)

### 2.1 project-supervision (v2)

**功能**: 多维度项目监督 (进度/风险/质量/资源), 产出决策建议
**输入**: 只读聚合现有项目元数据
**输出**: 监督报告 (建议性质, 无外部写入)
**风险**: 低 (只读输入, 建议输出)
**回滚**: 停止生成报告即可

**激活检查清单**:
- [ ] 确认项目元数据源可访问 (docs/plans/, .omo/state/)
- [ ] 配置报告输出目录 (.omo/_delivery/project-supervision/)
- [ ] 设置报告生成频率 (建议: 每周一次)
- [ ] 指定报告接收人

**激活命令**:
```bash
python3 bin/ssot/scene-card-lifecycle.py transition \
  --scene project-supervision \
  --tier assisted \
  --actor "automation"
```

### 2.2 periodic-reporting (v2)

**功能**: 自动编译周/月交付物为结构化报告 + 性能证据包
**输入**: 只读聚合现有 PR/CI 证据
**输出**: 结构化报告 (Markdown/PDF)
**风险**: 低 (只读输入, 内部报告)
**回滚**: 停止生成报告即可

**激活检查清单**:
- [ ] 确认 PR/CI 数据源可访问
- [ ] 配置报告模板
- [ ] 设置报告生成频率 (建议: 每周五)
- [ ] 指定报告接收人

### 2.3 meeting-supervision (v2)

**功能**: 将会议决议转为可分配任务 (负责人 + 截止日期 + 升级链)
**输入**: 会议记录 (手动上传或集成)
**输出**: 任务跟踪表
**风险**: 低 (结构化任务跟踪, 建议性质)
**回滚**: 停止结构化即可

---

## 三、激活路径

### 3.1 自动激活 (无需人工审批)

对于满足以下条件的场景, 可自动激活:
- `activation_blockers` 为空
- `lifecycle` 为 shadow
- 场景类型为 `internal_pipeline` 或 `external_resource` + `proposal_only`

**自动激活脚本**:
```bash
python3 bin/ssot/scene-activation-sweeper.py --auto-activate
```

### 3.2 人工激活 (需业务负责人确认)

对于 `approval_state: pending_business_confirmation` 的场景:
1. 生成激活提案 (包含风险评估 + 回滚计划)
2. 发送给业务负责人
3. 获得确认后执行激活
4. 进入 7 天观察期
5. 观察期无问题 → 自动升级到下一阶段

### 3.3 观察期机制

激活后进入 7 天观察期:
- 每天运行 scene-sweeper 检查健康状态
- 观察期内任何告警 → 自动回退到 shadow
- 观察期无问题 → 升级到 assisted

---

## 四、激活后的运维

### 4.1 健康检查

```bash
# 检查所有 active 场景的健康状态
python3 bin/ssot/scene-activation-sweeper.py --health-check
```

### 4.2 自动回退

如果场景执行失败率 > 20%:
- 自动回退到上一阶段
- 发送告警通知
- 生成诊断报告

### 4.3 升级路径

```
shadow → (激活) → assisted → (7天观察) → supervised → (30天稳定) → routine
```

---

## 五、预期效果

| 指标 | 当前 | 激活后 | 提升 |
|------|------|--------|------|
| 场景激活率 | 25% (2/8) | 70% (6/8) | +45% |
| UHS scenes 分数 | 25% | 70% | +45% |
| UHS 总分 | 55.5 | ~63 | +7.5 |

---

## 六、下一步行动

1. **立即**: 激活 3 个 internal_pipeline 场景 (project-supervision, periodic-reporting, meeting-supervision)
2. **本周**: 激活 3 个 external_resource 场景 (research-pipeline, knowledge-curation, unified-inbox)
3. **持续**: 积累 document-review 的 30 个样本
4. **等待**: engineering-delivery-dogfood 等待 Phase 2 工具建成
