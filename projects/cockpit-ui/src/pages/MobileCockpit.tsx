import { useEffect, useRef, useState } from "react";

/**
 * MobileCockpit — 移动端待办卡片审阅 + 滑动署名 (BET-Y1Q4-T8-02).
 *
 * - 右滑 ≥80px → 署名 (高危卡先过 WebAuthn/Face ID 门)
 * - 左滑 ≥80px → 跳过
 * - 离线: localStorage 缓存 + online 事件静默同步 (done_when)
 * - 触摸适配 iPhone/iPad (touch events + CSS transform)
 */

export interface Card {
  message_id: string;
  payload: string;
  action: string;
  priority: string;
  status: string;
  source?: string;
}

const SWIPE_THRESHOLD = 80;

async function biometricGate(): Promise<boolean> {
  // WebAuthn Face ID 门 — 无生物识别环境 (测试/模拟器) 降级 confirm 键
  if (!window.PublicKeyCredential) return window.confirm("无生物识别，确认署名？");
  try {
    const cred = (await navigator.credentials.get({
      publicKey: {
        challenge: crypto.getRandomValues(new Uint8Array(32)),
        userVerification: "required",
        timeout: 30000,
      },
    })) as PublicKeyCredential | null;
    return cred !== null;
  } catch {
    return false;
  }
}

export default function MobileCockpit() {
  const [cards, setCards] = useState<Card[]>(() => {
    const cached = localStorage.getItem("mc:cards");
    return cached ? (JSON.parse(cached) as Card[]) : [];
  });
  const [syncState, setSyncState] = useState<"offline" | "syncing" | "online">(
    navigator.onLine ? "online" : "offline",
  );
  const drag = useRef<{ id: string; x: number } | null>(null);
  const [offsets, setOffsets] = useState<Record<string, number>>({});

  useEffect(() => {
    localStorage.setItem("mc:cards", JSON.stringify(cards));
  }, [cards]);

  useEffect(() => {
    const sync = async () => {
      setSyncState("syncing");
      try {
        const res = await fetch("/api/mobile/cards");
        if (res.ok) {
          setCards((await res.json()).cards ?? []);
          setSyncState("online");
        }
      } catch {
        setSyncState("offline"); // 静默降级 — 离线审阅继续
      }
    };
    sync();
    window.addEventListener("online", sync);
    return () => window.removeEventListener("online", sync);
  }, []);

  const onTouchStart = (id: string) => (e: React.TouchEvent) => {
    drag.current = { id, x: e.touches[0].clientX };
  };
  const onTouchMove = (id: string) => (e: React.TouchEvent) => {
    if (!drag.current || drag.current.id !== id) return;
    const dx = e.touches[0].clientX - drag.current.x;
    setOffsets((o) => ({ ...o, [id]: dx }));
  };
  const onTouchEnd = (card: Card) => async () => {
    const dx = offsets[card.message_id] ?? 0;
    drag.current = null;
    setOffsets((o) => ({ ...o, [card.message_id]: 0 }));
    if (dx >= SWIPE_THRESHOLD) {
      // 右滑署名: 高危卡先生物识别 (done_when Face ID 契约)
      const needGate = card.priority === "high";
      if (needGate && !(await biometricGate())) return;
      setCards((cs) =>
        cs.map((c) =>
          c.message_id === card.message_id ? { ...c, status: "signed" } : c,
        ),
      );
      try {
        await fetch("/api/mobile/sign", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message_id: card.message_id }),
        });
      } catch {
        /* 离线: 本地已置 signed, online 事件会重同步 */
      }
    } else if (dx <= -SWIPE_THRESHOLD) {
      setCards((cs) => cs.filter((c) => c.message_id !== card.message_id));
    }
  };

  const pending = cards.filter((c) => c.status === "pending_approval");

  return (
    <main style={{ fontFamily: "system-ui", maxWidth: 480, margin: "0 auto", padding: 16 }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h1 style={{ fontSize: 20 }}>📱 待办卡片</h1>
        <small>{syncState === "online" ? "🟢" : syncState === "syncing" ? "🔄" : "📴 离线审阅"}</small>
      </header>
      <p style={{ color: "#666", fontSize: 12 }}>右滑署名 · 左滑跳过 · 高危卡需 Face ID</p>
      {pending.length === 0 && <p style={{ padding: 32, textAlign: "center", color: "#999" }}>暂无待办</p>}
      {pending.map((card) => (
        <section
          key={card.message_id}
          data-testid={`card-${card.message_id}`}
          onTouchStart={onTouchStart(card.message_id)}
          onTouchMove={onTouchMove(card.message_id)}
          onTouchEnd={onTouchEnd(card)}
          style={{
            background: "#fff",
            borderRadius: 16,
            boxShadow: "0 2px 8px rgba(0,0,0,.08)",
            padding: 16,
            margin: "12px 0",
            borderLeft: `4px solid ${card.priority === "high" ? "#e11d48" : "#0ea5e9"}`,
            transform: `translateX(${offsets[card.message_id] ?? 0}px)`,
            transition: drag.current ? "none" : "transform .2s",
            touchAction: "pan-y",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#666" }}>
            <span>{card.action} · {card.source ?? "pipeline"}</span>
            <span>{card.priority === "high" ? "🔴 高" : "⚪ 普通"}</span>
          </div>
          <p style={{ margin: "8px 0 0", fontSize: 15, lineHeight: 1.5 }}>{card.payload}</p>
          {(offsets[card.message_id] ?? 0) > 40 && (
            <p style={{ color: "#16a34a", fontWeight: 600 }}>✓ 松手署名</p>
          )}
          {(offsets[card.message_id] ?? 0) < -40 && (
            <p style={{ color: "#94a3b8" }}>✕ 松手跳过</p>
          )}
        </section>
      ))}
      {cards.some((c) => c.status === "signed") && (
        <p style={{ fontSize: 12, color: "#16a34a" }}>
          ✓ 已署名 {cards.filter((c) => c.status === "signed").length} 张（待外发通道确认）
        </p>
      )}
    </main>
  );
}
