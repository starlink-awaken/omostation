import { useState, useEffect } from 'react';
import './App.css';

interface Quest {
  id: number;
  title: string;
  type: string;
  reward: number;
  completed: boolean;
  assignee: string;
}

interface Profile {
  name: string;
  role: string;
  level?: number;
  wisdomPoints: number;
  responsibilityPoints: number;
  inventory: string[];
}

const API_URL = 'http://localhost:3001/api';

function App() {
  const [role, setRole] = useState<'child' | 'parent'>('child');
  const [profile, setProfile] = useState<Profile | null>(null);
  const [quests, setQuests] = useState<Quest[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [aiMessage, setAiMessage] = useState("Hi! I'm your AI Mentor. Let's load your dashboard!");
  const [blindBox, setBlindBox] = useState<string | null>(null);
  const [report, setReport] = useState<string | null>(null);
  const [isReportLoading, setIsReportLoading] = useState(false);

  const fetchDashboard = async (currentRole: string) => {
    try {
      const res = await fetch(`${API_URL}/dashboard?role=${currentRole}`);
      const data = await res.json();
      setProfile(data.profile);
      setQuests(data.quests);
      setLogs(data.recentLogs);
      setAiMessage(`Welcome back, ${data.profile.name}!`);
    } catch (err) {
      console.error(err);
      setAiMessage("Could not connect to the backend server. Make sure it is running on port 3001.");
    }
  };

  const fetchReport = async () => {
    setIsReportLoading(true);
    try {
      const res = await fetch(`${API_URL}/report?role=${role}`);
      const data = await res.json();
      if (data.success) {
        setReport(data.report);
      }
    } catch (err) {
      console.error(err);
      setAiMessage("Could not generate report.");
    } finally {
      setIsReportLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard(role);
  }, [role]);

  const toggleTask = async (id: number, currentCompleted: boolean) => {
    if (currentCompleted) return; // For MVP, only support marking as complete

    try {
      const res = await fetch(`${API_URL}/quests/${id}/complete`, {
        method: 'POST'
      });
      const data = await res.json();
      
      if (data.success) {
        setProfile(data.profile);
        setQuests(quests.map(q => q.id === id ? data.quest : q));
        setAiMessage(data.message);
        if (data.blindBoxDrop) {
          setBlindBox(data.blindBoxDrop);
          setTimeout(() => setBlindBox(null), 5000);
        }
        // Refresh logs
        fetchDashboard(role);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const addTask = async () => {
    const title = prompt("What's the new quest?");
    if (!title) return;
    const type = prompt("Type? (wisdom/responsibility)") || 'wisdom';
    const reward = prompt("Points reward?") || '10';
    // If parent is adding, maybe they assign to child. For simplicity, assign to opposite role.
    const assignee = role === 'parent' ? 'child' : 'parent';
    
    try {
      const res = await fetch(`${API_URL}/quests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, type, reward, assignee })
      });
      const data = await res.json();
      if (data.success) {
        setAiMessage(`New quest added for ${assignee}!`);
        // We added it for the other role, so it won't show on our dashboard immediately.
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="app-container">
      <header className="hero-header">
        <h1>Family Hub 🌟</h1>
        <div className="role-switcher">
          <button className={role === 'child' ? 'active' : ''} onClick={() => setRole('child')}>Child View</button>
          <button className={role === 'parent' ? 'active' : ''} onClick={() => setRole('parent')}>Parent View</button>
        </div>
      </header>

      {profile && (
        <div className="profile-bar">
          <div className="profile-info">
            <h2>{profile.name} {profile.level ? `(Lv.${profile.level})` : ''}</h2>
            <div className="stats">
              <span className="stat-pill wisdom">🧠 {profile.wisdomPoints} pts</span>
              <span className="stat-pill resp">🛡️ {profile.responsibilityPoints} pts</span>
            </div>
          </div>
          <div className="inventory">
            <h3>Inventory</h3>
            {profile.inventory.length === 0 ? <span className="empty">Empty</span> : profile.inventory.map((item, i) => <span key={i} className="inv-item">🎁 {item}</span>)}
          </div>
        </div>
      )}

      {blindBox && (
        <div className="blind-box-modal">
          <div className="blind-box-content popIn">
            <h2>🎉 BLIND BOX DROP! 🎉</h2>
            <p>You got: <strong>{blindBox}</strong></p>
          </div>
        </div>
      )}

      <div className="ai-mentor">
        <div className="ai-avatar float">🤖</div>
        <div className="ai-bubble">
          <p>{aiMessage}</p>
          <button className="report-btn" onClick={fetchReport} disabled={isReportLoading}>
            {isReportLoading ? "⏳ Generating..." : "📊 Generate Weekly AI Report"}
          </button>
        </div>
      </div>

      {report && (
        <div className="blind-box-modal" onClick={() => setReport(null)}>
          <div className="report-content popIn" onClick={e => e.stopPropagation()}>
            <div dangerouslySetInnerHTML={{ __html: report.replace(/\n/g, '<br/>') }} />
            <button className="add-btn" onClick={() => setReport(null)} style={{marginTop: '2rem'}}>Close</button>
          </div>
        </div>
      )}

      <main className="board-main">
        <div className="board-header">
          <h2>My Quests</h2>
          <button className="add-btn" onClick={addTask}>+ Assign Quest</button>
        </div>
        <div className="task-list">
          {quests.map(task => (
            <div 
              key={task.id} 
              className={`task-card ${task.completed ? 'completed' : ''} type-${task.type}`}
              onClick={() => toggleTask(task.id, task.completed)}
            >
              <div className="task-info">
                <h3>{task.title}</h3>
                <span className="task-points">+{task.reward} {task.type}</span>
              </div>
              <div className={`checkbox ${task.completed ? 'checked' : ''}`}>
                {task.completed && '✓'}
              </div>
            </div>
          ))}
          {quests.length === 0 && <p className="empty-state">No quests assigned. Enjoy your day!</p>}
        </div>

        {logs.length > 0 && (
          <div className="logs-section">
            <h3>Family Activity</h3>
            <ul>
              {logs.map((log, i) => <li key={i}>{log}</li>)}
            </ul>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
