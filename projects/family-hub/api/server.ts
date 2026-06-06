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

const PORT = 3001;
app.listen(PORT, () => {
  console.log(`Backend API Server running on http://localhost:${PORT}`);
});
