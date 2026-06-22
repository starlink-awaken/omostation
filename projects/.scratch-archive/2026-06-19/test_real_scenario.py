import sqlite3
from mcp_server import get_profiles, create_quest, complete_quest, get_active_quests, get_health, DB_PATH

def init_db():
    print("🧹 [1/5] Initializing Database for Real Scenario...")
    if DB_PATH.exists():
        DB_PATH.unlink()
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE profiles (
            role TEXT PRIMARY KEY,
            name TEXT,
            level INTEGER DEFAULT 1,
            wisdomPoints INTEGER DEFAULT 0,
            responsibilityPoints INTEGER DEFAULT 0,
            inventory TEXT DEFAULT '[]'
        )
    ''')
    conn.execute('''
        CREATE TABLE quests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            type TEXT,
            reward INTEGER,
            completed INTEGER DEFAULT 0,
            assignee TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT,
            type TEXT,
            timestamp TEXT
        )
    ''')
    # Insert real family members
    conn.execute("INSERT INTO profiles (role, name, level) VALUES ('dad', '爸爸', 10)")
    conn.execute("INSERT INTO profiles (role, name, level) VALUES ('mom', '妈妈', 10)")
    conn.execute("INSERT INTO profiles (role, name, level) VALUES ('kid', '宝宝', 1)")
    conn.commit()
    conn.close()
    print("✅ Database initialized with Mom, Dad, and Kid.")

def run_scenario():
    print("\n🔍 [2/5] Checking Health...")
    health = get_health()
    print(f"Health status: {health}")

    print("\n📜 [3/5] Creating Quests for the day...")
    q1 = create_quest("读一本英文绘本", "wisdom", 50, "kid")
    q2 = create_quest("帮妈妈收拾碗筷", "responsibility", 60, "kid")
    print(f"Created Quest 1: {q1}")
    print(f"Created Quest 2: {q2}")

    active = get_active_quests()
    print(f"Active Quests currently: {len(active)}")
    for q in active:
        print(f"  - [{q['id']}] {q['title']} (Reward: {q['reward']} pts)")

    print("\n🎮 [4/5] Kid completes the quests!")
    res1 = complete_quest(q1['id'])
    print(f"Completion 1 Result: {res1}")
    res2 = complete_quest(q2['id'])
    print(f"Completion 2 Result: {res2}")

    print("\n🏆 [5/5] Checking Profiles & Level Up...")
    profiles = get_profiles()
    for p in profiles:
        if p['role'] == 'kid':
            print(f"👉 【宝宝的最终状态】 等级: Lv.{p['level']} | 智慧: {p['wisdomPoints']} | 责任: {p['responsibilityPoints']}")
            assert p['wisdomPoints'] == 50, "Wisdom points mismatch"
            assert p['responsibilityPoints'] == 60, "Responsibility points mismatch"
            assert p['level'] == 2, "Level computation mismatch (should be 1 + 110/100 = 2)"
            print("✅ 验证通过：经验值正确累加，等级顺利突破 Lv.2！")

if __name__ == "__main__":
    init_db()
    run_scenario()
