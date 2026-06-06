import express from 'express';
import cors from 'cors';

const app = express();
app.use(cors());
app.use(express.json());

// In-memory mock database
const db = {
  profiles: {
    child: {
      name: '小明',
      role: 'child',
      level: 3,
      wisdomPoints: 120,
      responsibilityPoints: 80,
      inventory: ['1小时动画券'],
    },
    parent: {
      name: '爸爸',
      role: 'parent',
      wisdomPoints: 0,
      responsibilityPoints: 0,
      inventory: [],
    }
  },
  quests: [
    { id: 1, title: '阅读课外书30分钟', type: 'wisdom', reward: 10, completed: false, assignee: 'child' },
    { id: 2, title: '自己整理书桌', type: 'responsibility', reward: 15, completed: false, assignee: 'child' },
    { id: 3, title: '陪小明拼乐高30分钟', type: 'responsibility', reward: 20, completed: false, assignee: 'parent' }
  ],
  logs: []
};

// API: Get profile and quests based on role
app.get('/api/dashboard', (req, res) => {
  const role = req.query.role as string || 'child';
  const profile = db.profiles[role as keyof typeof db.profiles];
  const quests = db.quests.filter(q => q.assignee === role);
  
  res.json({
    profile,
    quests,
    recentLogs: db.logs.slice(0, 5)
  });
});

// API: Complete a quest and trigger blind box
app.post('/api/quests/:id/complete', (req, res) => {
  const questId = parseInt(req.params.id);
  const quest = db.quests.find(q => q.id === questId);
  
  if (!quest || quest.completed) {
    return res.status(400).json({ error: 'Quest not found or already completed.' });
  }

  quest.completed = true;
  
  // A: 将目前模拟的后端逻辑，通过 agora MCP 服务，持久化写入我们的 gbrain 数据库
  try {
    const { exec } = require('child_process');
    const dbUrl = "postgresql://gbrain:Dsirl1Y0H6MTmo54ULeKZ21RJToe5RyB@127.0.0.1:5433/brain";
    
    // Approach 1: Directly using gbrain CLI for persistence
    const gbrainCmd = `GBRAIN_DATABASE_URL=${dbUrl} bun run /Users/xiamingxing/Workspace/projects/gbrain/src/cli.ts put quest-${quest.id} --text "${quest.title} completed by ${quest.assignee}"`;
    
    // Approach 2: Using Agora MCP routing (Simulated execution for Agora Hub)
    const agoraCmd = `uv run agora run "Save family-hub task '${quest.title}' to gbrain"`;

    exec(gbrainCmd, (err, stdout, stderr) => {
      if (err) console.error("gbrain persistence error:", err);
      else console.log("gbrain persistence success:", stdout);
    });
  } catch (err) {
    console.error("Failed to sync to MCP / gbrain:", err);
  }

  const role = quest.assignee;
  const profile = db.profiles[role as keyof typeof db.profiles];

  // Add points
  if (quest.type === 'wisdom') profile.wisdomPoints += quest.reward;
  if (quest.type === 'responsibility') profile.responsibilityPoints += quest.reward;

  // Blind Box Logic (20% chance)
  let blindBoxItem = null;
  if (Math.random() < 0.2) {
    const items = ['神秘玩具盲盒', '周末选片权', '全家游乐园一次'];
    blindBoxItem = items[Math.floor(Math.random() * items.length)];
    profile.inventory.push(blindBoxItem);
  }

  // Log it
  db.logs.unshift(`[${new Date().toLocaleTimeString()}] ${profile.name} 完成了: ${quest.title}`);

  res.json({
    success: true,
    profile,
    quest,
    blindBoxDrop: blindBoxItem,
    message: blindBoxItem ? `太棒了！触发了随机盲盒奖励：${blindBoxItem}！` : '任务完成，干得好！'
  });
});

// API: Add a new quest (Parent can add for child, child can add for parent)
app.post('/api/quests', (req, res) => {
  const { title, type, reward, assignee } = req.body;
  const newQuest = {
    id: db.quests.length + 1,
    title,
    type,
    reward: parseInt(reward) || 10,
    completed: false,
    assignee
  };
  db.quests.push(newQuest);
  res.json({ success: true, quest: newQuest });
});

// API: Generate Weekly AI Mentor Report
app.get('/api/report', (req, res) => {
  const role = req.query.role as string || 'child';
  const profile = db.profiles[role as keyof typeof db.profiles];
  
  // Simulate LLM evaluation delay
  setTimeout(() => {
    let report = "";
    if (role === 'child') {
      report = `### 🌟 本周AI导师成长报告：${profile.name}\n\n**总评**：本周表现非常棒！你累积了 **${profile.wisdomPoints}** 点智慧值和 **${profile.responsibilityPoints}** 点责任感。\n\n**闪光点**：\n- 任务完成度很高，特别是责任感相关的任务（如整理书桌），展示了你强大的自我管理能力。\n\n**导师建议**：\n- 下周可以尝试挑战更多的“智慧”任务，比如阅读一本新的科普读物。\n- 背包里还有 **${profile.inventory.length}** 个盲盒奖励（${profile.inventory.join(', ')}），记得在周末和爸爸妈妈一起兑换使用哦！`;
    } else {
      report = `### 🎯 本周家庭共建报告：${profile.name}\n\n**总评**：作为家庭的顶梁柱，本周你在陪伴与互动上投入了精力。\n\n**观察反馈**：\n- 你陪伴小明完成了多项互动，这极大地增加了亲子羁绊（Responsibility Points: ${profile.responsibilityPoints}）。\n- 小明本周自理能力有所提升，这与你设定的激励机制密不可分。\n\n**下一步建议**：\n- 可以尝试在下周给小明布置一个稍微带有挑战性的“协作型”任务，进一步引导他主动探索。`;
    }

    res.json({ success: true, report });
  }, 1500); // 1.5s delay to simulate thinking
});

const PORT = 3001;
app.listen(PORT, () => {
  console.log(`Backend API Server running on http://localhost:${PORT}`);
});
