import React, { useState, useEffect } from 'react';
import { Activity, Server, Cpu, Database, CheckCircle, AlertTriangle, XCircle, Search, Settings, Terminal } from 'lucide-react';
import SandboxTerminal from './SandboxTerminal';
import MemoryInjector from './MemoryInjector';
import EnginesView from './EnginesView';
import SettingsView from './SettingsView';
import './Dashboard.css';

interface Service {
  id: string;
  name: string;
  status: 'online' | 'offline' | 'degraded';
  uptime: string;
  latency: string;
}

const mockServices: Service[] = [
  { id: '1', name: 'Agora Mesh', status: 'online', uptime: '99.9%', latency: '12ms' },
  { id: '2', name: 'Minerva Research', status: 'online', uptime: '99.5%', latency: '45ms' },
  { id: '3', name: 'SharedBrain Bridge', status: 'offline', uptime: '0%', latency: '-' },
  { id: '4', name: 'LLM Gateway', status: 'degraded', uptime: '98.2%', latency: '850ms' },
  { id: '5', name: 'KOS Substrate', status: 'online', uptime: '100%', latency: '2ms' },
];

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState('Overview');
  const [services, setServices] = useState<Service[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch real data from Agora API
    const fetchServices = async () => {
      try {
        const response = await fetch('/api/services');
        if (response.ok) {
          const data = await response.json();
          // Transform data format to match UI expected props
          const formattedServices: Service[] = data.map((item: any) => ({
            id: item.name,
            name: item.name,
            status: item.circuit === '断路' ? 'offline' : item.circuit === '半开' ? 'degraded' : 'online',
            uptime: item.uptime || 'N/A',
            latency: item.latency || '-',
          }));
          setServices(formattedServices.length > 0 ? formattedServices : mockServices);
        } else {
          setServices(mockServices);
        }
      } catch (error) {
        console.error('Failed to fetch services:', error);
        setServices(mockServices);
      } finally {
        setLoading(false);
      }
    };
    
    fetchServices();
    // Poll every 5 seconds
    const interval = setInterval(fetchServices, 5000);
    return () => clearInterval(interval);
  }, []);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'online': return <CheckCircle size={16} className="text-success" />;
      case 'offline': return <XCircle size={16} className="text-danger" />;
      case 'degraded': return <AlertTriangle size={16} className="text-warning" />;
      default: return null;
    }
  };

  return (
    <div className="dashboard-container">
      {/* Sidebar */}
      <aside className="sidebar glass-panel animate-fade-in">
        <div className="sidebar-header">
          <div className="logo-box">
            <Activity size={24} color="var(--color-accent)" />
          </div>
          <h2>Cockpit</h2>
        </div>
        
        <nav className="sidebar-nav">
          <button 
            className={`nav-item ${activeTab === 'Overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('Overview')}
          >
            <Server size={18} />
            <span>概览</span>
          </button>
          <button 
            className={`nav-item ${activeTab === 'Engines' ? 'active' : ''}`}
            onClick={() => setActiveTab('Engines')}
          >
            <Cpu size={18} />
            <span>引擎调度</span>
          </button>
          <button 
            className={`nav-item ${activeTab === 'Knowledge' ? 'active' : ''}`}
            onClick={() => setActiveTab('Knowledge')}
          >
            <Database size={18} />
            <span>知识中枢</span>
          </button>
          <button 
            className={`nav-item ${activeTab === 'Sandbox' ? 'active' : ''}`}
            onClick={() => setActiveTab('Sandbox')}
          >
            <Terminal size={18} />
            <span>隔离沙箱</span>
          </button>
          <button 
            className={`nav-item ${activeTab === 'Settings' ? 'active' : ''}`}
            onClick={() => setActiveTab('Settings')}
          >
            <Settings size={18} />
            <span>系统设置</span>
          </button>
        </nav>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        <header className="topbar animate-fade-in" style={{ animationDelay: '0.1s' }}>
          <div className="search-bar glass-panel">
            <Search size={18} className="text-muted" />
            <input type="text" placeholder="搜索服务、模型、智能体..." />
          </div>
          <div className="user-profile glass-panel">
            <div className="avatar">AD</div>
            <span>管理员</span>
          </div>
        </header>

        <div className="content-area">
          <div className="hero-section animate-fade-in" style={{ animationDelay: '0.2s' }}>
            <h1 className="hero-title">系统全局概览</h1>
            <p className="hero-subtitle">实时监控 eCOS v5 微服务环境，掌握集群全貌。</p>
          </div>

          {activeTab === 'Overview' && (
            <>
              <div className="stats-grid">
                <div className="stat-card glass-panel animate-fade-in" style={{ animationDelay: '0.3s' }}>
                  <div className="stat-icon-wrapper pulse-success">
                    <Server size={24} />
                  </div>
                  <div className="stat-info">
                    <h3>活跃服务数</h3>
                    <p className="stat-value">24 / 28</p>
                  </div>
                </div>
                
                <div className="stat-card glass-panel animate-fade-in" style={{ animationDelay: '0.4s' }}>
                  <div className="stat-icon-wrapper pulse-accent">
                    <Cpu size={24} />
                  </div>
                  <div className="stat-info">
                    <h3>大模型请求数</h3>
                    <p className="stat-value">12.4k</p>
                  </div>
                </div>
              </div>

              <div className="services-section animate-fade-in" style={{ animationDelay: '0.5s' }}>
                <div className="section-header">
                  <h2>核心服务节点</h2>
                  <button className="btn-glass">查看全部</button>
                </div>
                
                <div className="services-list glass-panel">
                  {loading ? (
                    <div className="loading-state">
                      <div className="spinner"></div>
                      <p>正在连接 Agora 服务网格...</p>
                    </div>
                  ) : (
                    <table className="services-table">
                      <thead>
                        <tr>
                          <th>服务名称</th>
                          <th>运行状态</th>
                          <th>正常运行时间</th>
                          <th>响应延迟</th>
                        </tr>
                      </thead>
                      <tbody>
                        {services.map(svc => (
                          <tr key={svc.id} className="service-row">
                            <td className="font-medium">{svc.name}</td>
                            <td>
                              <span className={`status-badge ${svc.status}`}>
                                {getStatusIcon(svc.status)}
                                {svc.status}
                              </span>
                            </td>
                            <td className="text-muted">{svc.uptime}</td>
                            <td className="text-muted">{svc.latency}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            </>
          )}
          {activeTab === 'Engines' && (
            <EnginesView />
          )}

          {activeTab === 'Knowledge' && (
            <MemoryInjector />
          )}

          {activeTab === 'Sandbox' && (
            <SandboxTerminal />
          )}

          {activeTab === 'Settings' && (
            <SettingsView />
          )}
        </div>
      </main>
    </div>
  );
}
