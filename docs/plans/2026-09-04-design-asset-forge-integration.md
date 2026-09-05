# 2026-09-04 Design Asset Forge Integration

## 结论

`awesome-design-md` 应作为只读设计资产源接入 forge / aetherforge，而不是接入 `L4` 自治层或主控制面。

- `L4` 负责 self-governance / domain registry / governed state
- `I0` 负责 route / MCP / externals
- `X` 扩展层（aetherforge / forge）负责 style matching、prompt assembly、asset orchestration
- `awesome-design-md` 仅提供设计语义和视觉样本，不承担运行时状态管理

## 正确落点

```
omostation
├─ L4: l4-kernel
│  └─ self-governance / registry
├─ I0: agora
│  └─ route / MCP / tool bridge
├─ X: aetherforge + forge
│  ├─ design_asset_adapter
│  ├─ asset_registry
│  ├─ style_matcher
│  ├─ prompt_builder
│  └─ ui_generation_orchestrator
└─ external assets: awesome-design-md (read-only corpus)
```

## 设计原则

1. 只读接入：不得更改外部 repo 产物；只扫描和提炼 metadata。
2. forge 承担召回与注入：在生成链路中使用匹配结果，但不接管 governance。
3. omostation 保持 control-plane 归属：最终输出仍受工作流、审计与验收约束。
4. asset registry 只提供元数据，不充当执行器；运行时状态仍写入 governance 配置面。

## 接入步骤

### Phase A：注册备选资产

- 扫描 `DESIGN.md` 文件
- 抽取 `brand`, `title`, `style_family`, `palette_tokens`, `tags`, `layout_pattern`
- 将结果写入 `docs/design-assets/awesome-design-manifest.yaml`

### Phase B：forge 集成

- 让 forge/
  aetherforge 能在生成任务中调度 `design_asset_adapter`
- 通过文本或图像匹配，选择最接近的 design references
- 将 style metadata 注入 UI prompt，而不是改写 main governance flow

### Phase C：验证与收敛

- 确认所有输出都通过 omostation 的标准 review / acceptance 流程
- 保持设计资产是输入源，而不是另一个控制平面

## 结论

这种结构与当前 repo 的 `L4 / I0 / X` 分层契约保持一致，并保留了外部设计资产在 AI 生成链路中的价值，而不破坏 omostation 的单一控制平面。 
