import { useState, useEffect } from 'react';
import './App.css';

interface Task {
  id: string;
  title: string;
  points: number;
  completed: boolean;
  type: 'learning' | 'chore' | 'fun';
}

function App() {
  const [tasks, setTasks] = useState<Task[]>(() => {
    const saved = localStorage.getItem('family-hub-tasks');
    if (saved) {
      return JSON.parse(saved);
    }
    return [
      { id: '1', title: 'Read a book for 20 mins 📚', points: 50, completed: false, type: 'learning' },
      { id: '2', title: 'Clean up the toy box 🧸', points: 30, completed: false, type: 'chore' },
      { id: '3', title: 'Draw a family portrait 🎨', points: 40, completed: false, type: 'fun' },
    ];
  });

  const [score, setScore] = useState(() => {
    const saved = localStorage.getItem('family-hub-score');
    return saved ? parseInt(saved, 10) : 0;
  });

  const [aiMessage, setAiMessage] = useState("Hi! I'm your AI Mentor. Let's complete some quests today!");

  useEffect(() => {
    localStorage.setItem('family-hub-tasks', JSON.stringify(tasks));
  }, [tasks]);

  useEffect(() => {
    localStorage.setItem('family-hub-score', score.toString());
  }, [score]);

  const toggleTask = (id: string) => {
    setTasks(tasks.map(t => {
      if (t.id === id) {
        const isCompleting = !t.completed;
        if (isCompleting) {
          setScore(s => s + t.points);
          setAiMessage(`Great job completing "${t.title}"! You earned ${t.points} points. 🌟`);
        } else {
          setScore(s => s - t.points);
          setAiMessage("Quest unmarked. Keep going!");
        }
        return { ...t, completed: isCompleting };
      }
      return t;
    }));
  };

  const addTask = () => {
    const title = prompt("What's the new quest?");
    if (!title) return;
    const type = prompt("Type? (learning/chore/fun)") as 'learning' | 'chore' | 'fun';
    if (!['learning', 'chore', 'fun'].includes(type)) return;
    
    const newTask: Task = {
      id: Date.now().toString(),
      title,
      points: Math.floor(Math.random() * 30) + 10,
      completed: false,
      type
    };
    setTasks([...tasks, newTask]);
    setAiMessage(`New quest added! You can earn ${newTask.points} points.`);
  };

  return (
    <div className="app-container">
      <header className="hero-header">
        <h1>Family Hub 🌟</h1>
        <div className="score-badge">
          <span className="star-icon">⭐</span>
          <span className="score-text">{score} Points</span>
        </div>
      </header>

      <div className="ai-mentor">
        <div className="ai-avatar">🤖</div>
        <div className="ai-bubble">{aiMessage}</div>
      </div>

      <main className="board-main">
        <div className="board-header">
          <h2>Today's Quests</h2>
          <button className="add-btn" onClick={addTask}>+ Add</button>
        </div>
        <div className="task-list">
          {tasks.map(task => (
            <div 
              key={task.id} 
              className={`task-card ${task.completed ? 'completed' : ''} type-${task.type}`}
              onClick={() => toggleTask(task.id)}
            >
              <div className="task-info">
                <h3>{task.title}</h3>
                <span className="task-points">+{task.points} pts</span>
              </div>
              <div className={`checkbox ${task.completed ? 'checked' : ''}`}>
                {task.completed && '✓'}
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}

export default App;
