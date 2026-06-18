import fs from 'fs';
import path from 'path';
import yaml from 'js-yaml';
import { Activity, ShieldAlert, Cpu, Network } from 'lucide-react';

async function getSystemState() {
  try {
    const omoPath = path.join(process.cwd(), '../..', '.omo', 'state', 'system.yaml');
    if (fs.existsSync(omoPath)) {
      const fileContents = fs.readFileSync(omoPath, 'utf8');
      return yaml.load(fileContents) as any;
    }
    return { health_score: 0, status: 'offline', active_phase: 'Unknown' };
  } catch (e) {
    console.error('Error reading system state:', e);
    return { health_score: 0, status: 'error', active_phase: 'Error' };
  }
}

export default async function Dashboard() {
  const state = await getSystemState();
  const health = state?.health_score || 0;
  
  return (
    <div className="min-h-screen bg-black text-green-400 font-mono p-8 relative overflow-hidden">
      {/* Cyberpunk Grid Background */}
      <div className="absolute inset-0 z-0 bg-[linear-gradient(rgba(0,255,0,0.1)_1px,transparent_1px),linear-gradient(90deg,rgba(0,255,0,0.1)_1px,transparent_1px)] bg-[size:40px_40px] pointer-events-none opacity-20"></div>
      
      {/* Scanline Effect */}
      <div className="absolute inset-0 z-0 pointer-events-none bg-[linear-gradient(rgba(0,0,0,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))] bg-[length:100%_4px,3px_100%] opacity-30"></div>

      <div className="max-w-6xl mx-auto relative z-10">
        <header className="mb-12 border-b-2 border-green-500/50 pb-6 flex items-end justify-between">
          <div>
            <h1 className="text-5xl font-black tracking-tighter text-transparent bg-clip-text bg-gradient-to-r from-green-400 to-emerald-600 uppercase glitch-effect" data-text="AGORA // NEXUS">
              AGORA // NEXUS
            </h1>
            <p className="mt-2 text-green-500/70 text-sm tracking-widest">eCOS v5 WORKSPACE OBSERVATORY</p>
          </div>
          <div className="text-right">
            <div className="flex items-center space-x-2 text-sm bg-green-900/20 px-3 py-1 rounded border border-green-500/30">
              <span className={`w-2 h-2 rounded-full animate-pulse ${health > 80 ? 'bg-green-500' : 'bg-red-500'}`}></span>
              <span>SYS.STATUS: {health > 80 ? 'OPTIMAL' : 'DEGRADED'}</span>
            </div>
          </div>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
          {/* Health Score Card */}
          <div className="bg-black/50 border border-green-500/30 p-6 backdrop-blur-sm relative group hover:border-green-400 transition-colors">
            <div className="absolute top-0 left-0 w-2 h-2 border-t-2 border-l-2 border-green-400"></div>
            <div className="absolute bottom-0 right-0 w-2 h-2 border-b-2 border-r-2 border-green-400"></div>
            <div className="flex items-center space-x-4 mb-4">
              <Activity className="text-green-400 w-8 h-8" />
              <h2 className="text-lg font-bold tracking-wider">HEALTH_SCORE</h2>
            </div>
            <div className="text-5xl font-black text-white">{health}</div>
            <div className="w-full bg-gray-900 h-1 mt-4">
              <div className="bg-green-400 h-1" style={{ width: `${health}%` }}></div>
            </div>
          </div>

          {/* Active Phase Card */}
          <div className="bg-black/50 border border-green-500/30 p-6 backdrop-blur-sm relative group hover:border-green-400 transition-colors">
            <div className="absolute top-0 left-0 w-2 h-2 border-t-2 border-l-2 border-green-400"></div>
            <div className="absolute bottom-0 right-0 w-2 h-2 border-b-2 border-r-2 border-green-400"></div>
            <div className="flex items-center space-x-4 mb-4">
              <Cpu className="text-green-400 w-8 h-8" />
              <h2 className="text-lg font-bold tracking-wider">ACTIVE_PHASE</h2>
            </div>
            <div className="text-3xl font-black text-white truncate">{state?.active_phase || 'P6'}</div>
            <p className="mt-2 text-xs text-green-500/60 uppercase">Current Evolution Loop</p>
          </div>

          {/* Debt Metrics Card */}
          <div className="bg-black/50 border border-green-500/30 p-6 backdrop-blur-sm relative group hover:border-green-400 transition-colors">
            <div className="absolute top-0 left-0 w-2 h-2 border-t-2 border-l-2 border-green-400"></div>
            <div className="absolute bottom-0 right-0 w-2 h-2 border-b-2 border-r-2 border-green-400"></div>
            <div className="flex items-center space-x-4 mb-4">
              <ShieldAlert className="text-green-400 w-8 h-8" />
              <h2 className="text-lg font-bold tracking-wider">SYS_DEBT</h2>
            </div>
            <div className="text-3xl font-black text-white">{state?.debt_metrics?.debt_health || 100}%</div>
            <p className="mt-2 text-xs text-green-500/60 uppercase">Governance Adherence</p>
          </div>

          {/* Network Nodes */}
          <div className="bg-black/50 border border-green-500/30 p-6 backdrop-blur-sm relative group hover:border-green-400 transition-colors">
            <div className="absolute top-0 left-0 w-2 h-2 border-t-2 border-l-2 border-green-400"></div>
            <div className="absolute bottom-0 right-0 w-2 h-2 border-b-2 border-r-2 border-green-400"></div>
            <div className="flex items-center space-x-4 mb-4">
              <Network className="text-green-400 w-8 h-8" />
              <h2 className="text-lg font-bold tracking-wider">ACTIVE_NODES</h2>
            </div>
            <div className="text-3xl font-black text-white">4 / 5</div>
            <p className="mt-2 text-xs text-green-500/60 uppercase">L0-L4 Layers Configured</p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="border border-green-500/30 bg-black/80 backdrop-blur-md p-6">
            <h3 className="text-xl font-bold border-b border-green-500/30 pb-2 mb-4 uppercase tracking-widest text-green-300">
              Terminal Output // Raw State
            </h3>
            <pre className="text-xs text-green-500/80 overflow-x-auto p-4 bg-black border border-green-900 rounded">
              {JSON.stringify(state, null, 2)}
            </pre>
          </div>

          <div className="border border-green-500/30 bg-black/80 backdrop-blur-md p-6 flex flex-col justify-center items-center text-center">
            <div className="animate-spin-slow mb-6">
              <Network className="w-24 h-24 text-green-500/40" />
            </div>
            <h3 className="text-2xl font-black uppercase text-green-400 mb-2">Agora Mesh Proxy</h3>
            <p className="text-sm text-green-500/60 mb-6 max-w-md">
              Monitoring cross-layer traffic via bos:// protocols. eCOS v5 integration active.
            </p>
            <button className="px-6 py-2 border-2 border-green-500 text-green-400 hover:bg-green-500 hover:text-black font-bold uppercase tracking-widest transition-colors shadow-[0_0_15px_rgba(0,255,0,0.3)] hover:shadow-[0_0_25px_rgba(0,255,0,0.6)]">
              Initiate Sync
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
