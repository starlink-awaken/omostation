import express from 'express';
import cors from 'cors';
import { Database } from 'bun:sqlite';
import { exec } from 'child_process';

const app = express();
app.use(cors());
app.use(express.json());

// Initialize SQLite database
const db = new Database('family_hub.db');

// Setup tables
db.exec(`
  CREATE TABLE IF NOT EXISTS profiles (
    role TEXT PRIMARY KEY,
    name TEXT,
    level INTEGER,
    wisdomPoints INTEGER,
    responsibilityPoints INTEGER,
    inventory TEXT
  );
  
  CREATE TABLE IF NOT EXISTS quests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    type TEXT,
    reward INTEGER,
    completed BOOLEAN,
    assignee TEXT
  );

  CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT,
    type TEXT,
    timestamp TEXT
  );
`);

// Seed data if empty
const count = db.prepare('SELECT COUNT(*) as count FROM profiles').get() as { count: number };
if (count.count === 0) {
  const insertProfile = db.prepare('INSERT INTO profiles (role, name, level, wisdomPoints, responsibilityPoints, inventory) VALUES (?, ?, ?, ?, ?, ?)');
  insertProfile.run('child', '小明', 3, 120, 80, JSON.stringify(['1小时动画券']));
  insertProfile.run('parent', '爸爸', 1, 0, 0, JSON.stringify([]));

  const insertQuest = db.prepare('INSERT INTO quests (title, type, reward, completed, assignee) VALUES (?, ?, ?, ?, ?)');
  insertQuest.run('阅读课外书30分钟', 'wisdom', 10, 0, 'child');
  insertQuest.run('自己整理书桌', 'responsibility', 15, 0, 'child');
  insertQuest.run('陪小明拼乐高30分钟', 'responsibility', 20, 0, 'parent');
}

// Helper to parse profile
const getProfile = (role: string) => {
  const p = db.prepare('SELECT * FROM profiles WHERE role = ?').get(role) as any;
  if (!p) return null;
  return { ...p, inventory: JSON.parse(p.inventory), completed: !!p.completed };
};

// API: Get profile and quests based on role
app.get('/api/dashboard', (req, res) => {
  const role = req.query.role as string || 'child';
  const profile = getProfile(role);
  
  const quests = db.prepare('SELECT * FROM quests WHERE assignee = ?').all(role).map((q: any) => ({
    ...q, completed: !!q.completed
  }));
  
  const recentLogs = db.prepare('SELECT message FROM logs ORDER BY id DESC LIMIT 5').all().map((l: any) => l.message);
  
  res.json({
    profile,
    quests,
    recentLogs
  });
});

// API: Complete a quest and trigger blind box
app.post('/api/quests/:id/complete', (req, res) => {
  const questId = parseInt(req.params.id);
  const quest = db.prepare('SELECT * FROM quests WHERE id = ?').get(questId) as any;
  
  if (!quest || quest.completed) {
    return res.status(400).json({ error: 'Quest not found or already completed.' });
  }

  // Mark as completed
  db.prepare('UPDATE quests SET completed = 1 WHERE id = ?').run(questId);
  
  // MCP sync
  try {
    const dbUrl = "postgresql://gbrain:Dsirl1Y0H6MTmo54ULeKZ21RJToe5RyB@127.0.0.1:5433/brain";
    const gbrainCmd = `GBRAIN_DATABASE_URL=${dbUrl} bun run /Users/xiamingxing/Workspace/projects/gbrain/src/cli.ts put quest-${quest.id} --text "${quest.title} completed by ${quest.assignee}"`;
    exec(gbrainCmd, (err) => {
      if (err) console.error("gbrain persistence error:", err.message);
    });
  } catch (err) {
    console.error("Failed to sync to MCP / gbrain", err);
  }

  const role = quest.assignee;
  const profile = getProfile(role);
  if (!profile) return res.status(400).json({ error: 'Profile not found' });

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

  // Update profile
  db.prepare('UPDATE profiles SET wisdomPoints = ?, responsibilityPoints = ?, inventory = ? WHERE role = ?')
    .run(profile.wisdomPoints, profile.responsibilityPoints, JSON.stringify(profile.inventory), role);

  // Log it
  const logMessage = `[${new Date().toLocaleTimeString()}] ${profile.name} 完成了: ${quest.title}`;
  db.prepare('INSERT INTO logs (message, type, timestamp) VALUES (?, ?, ?)').run(logMessage, quest.type, new Date().toISOString());

  res.json({
    success: true,
    profile,
    quest: { ...quest, completed: true },
    blindBoxDrop: blindBoxItem,
    message: blindBoxItem ? `太棒了！触发了随机盲盒奖励：${blindBoxItem}！` : '任务完成，干得好！'
  });
});

// API: Add a new quest
app.post('/api/quests', (req, res) => {
  const { title, type, reward, assignee } = req.body;
  const r = parseInt(reward) || 10;
  
  const info = db.prepare('INSERT INTO quests (title, type, reward, completed, assignee) VALUES (?, ?, ?, ?, ?)')
    .run(title, type, r, 0, assignee);
    
  res.json({ 
    success: true, 
    quest: { id: info.lastInsertRowid, title, type, reward: r, completed: false, assignee } 
  });
});

// API: Generate Weekly AI Mentor Report
app.get('/api/report', (req, res) => {
  const role = req.query.role as string || 'child';
  const profile = getProfile(role);
  if (!profile) return res.status(404).json({ error: 'Profile not found' });
  
  setTimeout(() => {
    let report = "";
    if (role === 'child') {
      report = `### 🌟 本周AI导师成长报告：${profile.name}\n\n**总评**：本周表现非常棒！你累积了 **${profile.wisdomPoints}** 点智慧值和 **${profile.responsibilityPoints}** 点责任感。\n\n**闪光点**：\n- 任务完成度很高，特别是责任感相关的任务（如整理书桌），展示了你强大的自我管理能力。\n\n**导师建议**：\n- 下周可以尝试挑战更多的“智慧”任务，比如阅读一本新的科普读物。\n- 背包里还有 **${profile.inventory.length}** 个盲盒奖励（${profile.inventory.join(', ')}），记得在周末和爸爸妈妈一起兑换使用哦！`;
    } else {
      report = `### 🎯 本周家庭共建报告：${profile.name}\n\n**总评**：作为家庭的顶梁柱，本周你在陪伴与互动上投入了精力。\n\n**观察反馈**：\n- 你陪伴小明完成了多项互动，这极大地增加了亲子羁绊（Responsibility Points: ${profile.responsibilityPoints}）。\n- 小明本周自理能力有所提升，这与你设定的激励机制密不可分。\n\n**下一步建议**：\n- 可以尝试在下周给小明布置一个稍微带有挑战性的“协作型”任务，进一步引导他主动探索。`;
    }

    res.json({ success: true, report });
  }, 1500);
});

const PORT = 3001;
app.listen(PORT, () => {
  console.log(`Backend API Server running on http://localhost:${PORT}`);
});
