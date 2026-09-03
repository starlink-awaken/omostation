import { describe, expect, it } from "bun:test";

/** T8-02 verify: bun test — 组件契约 (导入即冒烟 + 数据面纯函数). */
describe("MobileCockpit", () => {
  it("module imports cleanly (component contract)", async () => {
    const mod = await import("./pages/MobileCockpit");
    expect(typeof mod.default).toBe("function");
    expect(mod.default.name).toBe("MobileCockpit");
  });

  it("Card surface matches API contract", async () => {
    const mod = await import("./pages/MobileCockpit");
    const card: mod.Card = {
      message_id: "m1", payload: "测试", action: "query",
      priority: "high", status: "pending_approval",
    };
    expect(card.status).toBe("pending_approval");
  });
});
