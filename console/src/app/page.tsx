'use client';

import React, { useState, useEffect, useRef } from 'react';
import { QRCodeSVG } from 'qrcode.react';

// Define the steps and their attributes
interface StepMetrics {
  q: number;
  cost: number;
  latency: number;
}

interface StepNode {
  name: string;
  agentId: string;
  cloud: string;
  metrics: StepMetrics;
  status: 'healthy' | 'fault' | 'warn';
}

const REASONING_LINES = [
  "[12:05:12] [detector] EWMA alarm tripped on causal_estimation (z-score = 4.82).",
  "[12:05:13] [triage-agent] Initializing localization routing trace...",
  "[12:05:14] [triage-agent] Querying dependency graph: data_prep -> causal_estimation -> readout.",
  "[12:05:15] [triage-agent] Analyzing step causal_estimation:",
  "           - Out-of-bounds check failed (ATE = 48.5%, bounds = [0.0%, 10.0%]).",
  "           - McNemar paired test p-value: 0.0001 (significant regression).",
  "           - Credit assignment score: 1.0 (highest attribution).",
  "[12:05:17] [triage-agent] Analyzing step readout:",
  "           - Output classification: Low Confidence recommendation.",
  "           - Trace analysis: Readout inputs matched causal_estimation outputs.",
  "           - Credit assignment score: 0.0 (propagated contamination).",
  "[12:05:18] [triage-agent] VERDICT: Root cause isolated to causal_estimation. Readout is a downstream symptom.",
  "[12:05:19] [triage-agent] Generating validation test tasks for causal_estimation...",
  "[12:05:20] [triage-agent] Drafted 3 evaluation scenarios matching failure patterns.",
  "[12:05:21] [triage-agent] Triage complete. Awaiting human approval to run validation & deploy spare."
];

export default function Home() {
  const [activeTab, setActiveTab] = useState<'pipeline' | 'triage' | 'pareto' | 'signals' | 'router' | 'end'>('pipeline');
  const [simState, setSimState] = useState<'healthy' | 'degraded' | 'triaging' | 'awaiting_approval' | 'rescoring' | 'recovered'>('healthy');
  
  const [dbData, setDbData] = useState<any>(null);
  const [activeClusterId, setActiveClusterId] = useState<string>('');
  
  // Triage streaming state
  const [visibleLogs, setVisibleLogs] = useState<string[]>([]);
  const [triageLogIndex, setTriageLogIndex] = useState(0);
  
  // Pareto animation
  const [paretoProgress, setParetoProgress] = useState(0);

  // Recovery effect estimate moving number slider animation
  const [effectEstimate, setEffectEstimate] = useState(2.4);

  // Fetch telemetry/data from DB
  const fetchData = async () => {
    try {
      const res = await fetch('/api/data');
      if (res.ok) {
        const data = await res.json();
        setDbData(data);
        
        // Auto-detect proposed cluster
        const proposedCluster = data.triage_clusters?.find((c: any) => c.status === 'proposed');
        if (proposedCluster && simState === 'healthy') {
          setActiveClusterId(proposedCluster.cluster_id);
          setSimState('degraded');
        }
      }
    } catch (err) {
      console.error('Error fetching DB telemetry:', err);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 8000);
    return () => clearInterval(interval);
  }, [simState]);

  // Handle streaming log effect when triaging
  useEffect(() => {
    if (simState === 'triaging') {
      setVisibleLogs([]);
      setTriageLogIndex(0);
      setActiveTab('triage');
    }
  }, [simState]);

  useEffect(() => {
    if (simState === 'triaging' && triageLogIndex < REASONING_LINES.length) {
      const timeout = setTimeout(() => {
        setVisibleLogs(prev => [...prev, REASONING_LINES[triageLogIndex]]);
        setTriageLogIndex(prev => prev + 1);
      }, 350);
      return () => clearTimeout(timeout);
    } else if (simState === 'triaging' && triageLogIndex === REASONING_LINES.length) {
      setSimState('awaiting_approval');
    }
  }, [simState, triageLogIndex]);

  // Handle effect estimate animation during transitions
  useEffect(() => {
    let interval: any;
    if (simState === 'degraded' || simState === 'triaging' || simState === 'awaiting_approval') {
      // Degraded state value
      setEffectEstimate(48.5);
    } else if (simState === 'rescoring') {
      // Animate counting down from 48.5 to 2.4
      let current = 48.5;
      interval = setInterval(() => {
        current -= 2.5;
        if (current <= 2.4) {
          current = 2.4;
          clearInterval(interval);
        }
        setEffectEstimate(parseFloat(current.toFixed(1)));
      }, 50);
    } else {
      setEffectEstimate(2.4);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [simState]);

  // Trigger Pareto line animation on selection
  useEffect(() => {
    if (activeTab === 'pareto') {
      setParetoProgress(0);
      const interval = setInterval(() => {
        setParetoProgress(prev => {
          if (prev >= 100) {
            clearInterval(interval);
            return 100;
          }
          return prev + 5;
        });
      }, 30);
      return () => clearInterval(interval);
    }
  }, [activeTab]);

  const triggerFailure = async () => {
    try {
      setSimState('degraded');
      setEffectEstimate(48.5);
      setActiveTab('pipeline');
      
      const res = await fetch('/api/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'trigger_failure' })
      });
      const data = await res.json();
      
      // Auto transition to triage thinking view after 2.5s
      setTimeout(() => {
        setSimState('triaging');
      }, 2500);
      
    } catch (err) {
      console.error(err);
    }
  };

  const approveTriage = async () => {
    try {
      setSimState('rescoring');
      setActiveTab('pipeline');

      // Call API
      const clusterId = activeClusterId || (dbData?.triage_clusters?.[0]?.cluster_id) || 'cluster-mock-123';
      await fetch('/api/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'approve', clusterId })
      });

      // Show loop transitioning: re-scoring -> recovered
      setTimeout(() => {
        setSimState('recovered');
      }, 3000);
    } catch (err) {
      console.error(err);
    }
  };

  const resetState = () => {
    setSimState('healthy');
    setEffectEstimate(2.4);
    setActiveTab('pipeline');
  };

  // Helper values for current loop state label
  const getLoopStateText = () => {
    switch (simState) {
      case 'healthy': return 'idle';
      case 'degraded': return 'detecting';
      case 'triaging': return 'localizing';
      case 'awaiting_approval': return 'awaiting approval';
      case 'rescoring': return 're-scoring';
      case 'recovered': return 'recovered';
    }
  };

  const isDegraded = simState === 'degraded' || simState === 'triaging' || simState === 'awaiting_approval';

  // Metrics configurations depending on states
  const getMetrics = (step: string): StepMetrics => {
    if (step === 'data-prep') {
      return { q: 0.98, cost: 0.002, latency: 120 };
    }
    if (step === 'causal') {
      if (isDegraded) return { q: 0.18, cost: 0.011, latency: 450 };
      if (simState === 'rescoring') return { q: 0.55, cost: 0.012, latency: 320 };
      if (simState === 'recovered') return { q: 0.93, cost: 0.012, latency: 290 };
      return { q: 0.91, cost: 0.011, latency: 280 };
    }
    // Readout metrics
    if (isDegraded) return { q: 0.42, cost: 0.004, latency: 150 };
    return { q: 0.94, cost: 0.004, latency: 150 };
  };

  return (
    <div className="flex flex-col flex-1 h-screen overflow-hidden select-none bg-surface-0 font-sans">
      
      {/* 1. Header / Status Bar */}
      <header className="flex items-center justify-between h-16 px-6 border-b border-line bg-surface-1">
        <div className="flex items-center gap-3">
          <div className="font-sans font-bold text-lg tracking-tight text-ink-hi">
            AgentLab <span className="text-ink-mid text-xs font-normal font-sans ml-1">mesh router panel</span>
          </div>
          <span className="w-1.5 h-1.5 rounded-full bg-ok" />
        </div>

        {/* Global health pill */}
        <div className="flex items-center">
          {simState === 'healthy' || simState === 'recovered' ? (
            <div className="flex items-center gap-2 px-3 py-1 rounded bg-[#3DD68C]/10 border border-[#3DD68C]/30 text-ok text-xs font-sans font-bold tracking-normal">
              <span className="w-2.5 h-2.5 rounded-full bg-ok" />
              PIPELINE HEALTHY
            </div>
          ) : simState === 'rescoring' ? (
            <div className="flex items-center gap-2 px-3 py-1 rounded bg-[#F2B544]/10 border border-[#F2B544]/30 text-warn text-xs font-sans font-bold tracking-normal animate-pulse">
              <span className="w-2.5 h-2.5 rounded-full bg-warn" />
              DEGRADATION DETECTED (RESOLVING)
            </div>
          ) : (
            <div className="flex items-center gap-2 px-3 py-1 rounded bg-[#F2555A]/10 border border-[#F2555A]/30 text-fault text-xs font-sans font-bold tracking-normal animate-pulse">
              <span className="w-0.5 h-0.5 border-l-4 border-r-4 border-b-8 border-transparent border-b-fault mb-0.5" />
              DEGRADATION DETECTED
            </div>
          )}
        </div>

        {/* Loop state indicator */}
        <div className="flex items-center gap-2 font-sans text-xs text-ink-lo bg-surface-2 px-3 py-1 rounded border border-line">
          <span>loopState:</span>
          <span className="text-info font-semibold font-mono tracking-wide">{getLoopStateText()}</span>
        </div>
      </header>

      {/* Main Container */}
      <div className="flex flex-1 overflow-hidden">
        
        {/* 2. Left Rail Sidebar */}
        <aside className="w-64 border-r border-line bg-surface-1 flex flex-col justify-between p-4">
          <nav className="space-y-2">
            {[
              { id: 'pipeline', label: 'Pipeline', icon: 'M4 6h16M4 12h16M4 18h16' },
              { id: 'triage', label: 'Triage', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01' },
              { id: 'pareto', label: 'Pareto', icon: 'M7 12l3-3 3 3 4-4M8 21h12a2 2 0 002-2V7a2 2 0 00-2-2H8a2 2 0 00-2 2v12a2 2 0 002 2z' },
              { id: 'signals', label: 'Signals', icon: 'M13 10V3L4 14h7v7l9-11h-7z' },
              { id: 'router', label: 'Router', icon: 'M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z' },
              { id: 'end', label: 'End Card', icon: 'M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z' },
            ].map(tab => {
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`flex items-center w-full gap-2 px-4 py-2 text-sm rounded-md font-medium transition-colors relative group ${
                    active ? 'text-ink-hi bg-surface-2' : 'text-ink-mid hover:text-ink-hi hover:bg-surface-2/50'
                  }`}
                >
                  {active && <span className="absolute left-0 top-1 bottom-1 w-1 bg-ok rounded-r-md" />}
                  <svg className={`w-4 h-4 transition-colors ${active ? 'text-ok' : 'text-ink-lo group-hover:text-ink-mid'}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d={tab.icon} />
                  </svg>
                  {tab.label}
                  {tab.id === 'triage' && isDegraded && (
                    <span className="ml-auto w-2 h-2 rounded-full bg-fault animate-ping" />
                  )}
                </button>
              );
             })}
          </nav>

          {/* Floating Demo Control Panel inside Sidebar */}
          <div className="p-4 rounded-xl border border-line bg-surface-0/60 space-y-4 shadow-inner">
            <div className="font-sans text-[10px] text-ink-lo uppercase tracking-normal font-bold">
              Simulation Deck
            </div>
            
            <button
              onClick={triggerFailure}
              disabled={isDegraded}
              className={`w-full text-xs font-sans py-2.5 px-4 rounded-md border font-semibold transition-all ${
                isDegraded
                  ? 'border-line text-ink-lo cursor-not-allowed bg-surface-1'
                  : 'border-fault/40 text-fault bg-fault/5 hover:bg-fault/20 hover:border-fault'
              }`}
            >
              Trigger Pipeline Fault
            </button>

            <button
              onClick={resetState}
              className="w-full text-xs font-sans py-2.5 px-4 rounded-md border border-line text-ink-mid hover:text-ink-hi hover:bg-surface-3 transition-all"
            >
              Force Reset System
            </button>
          </div>

          {/* Tiny Footer QR Link */}
          <div className="mt-4 text-center">
            <button
              onClick={() => setActiveTab('end')}
              className="text-[9px] font-sans text-ink-lo hover:text-ink-mid transition-colors uppercase tracking-normal cursor-pointer"
            >
              ➔ Scan Repo QR Code
            </button>
          </div>
        </aside>

        {/* 3. Main Workspace Area */}
        <main className="flex-1 relative overflow-hidden bg-surface-0">
          
          {/* TAB 1: PIPELINE VIEW */}
          <div className={`absolute inset-0 p-8 overflow-y-auto transition-all duration-300 ease-out flex flex-col items-center justify-start ${
            activeTab === 'pipeline' ? 'opacity-100 translate-y-0 z-10 visible' : 'opacity-0 translate-y-4 pointer-events-none z-0 invisible'
          }`}>
            <div className="w-full max-w-4xl mb-6">
              <h2 className="text-xl font-sans font-bold text-ink-hi flex items-center gap-2 tracking-tight">
                <span>Routing Flow Architecture</span>
                <span className="text-xs text-ink-lo font-sans font-normal border border-line px-1.5 py-0.5 rounded-md uppercase">Live Topology</span>
              </h2>
              <p className="text-xs text-ink-mid mt-1 font-sans">
                Visualization of distributed workflow nodes. Warning edges represent data pollution propagation.
              </p>
            </div>

            {/* Node diagram workspace */}
            <div className="w-[896px] h-[480px] relative border border-line bg-surface-1/40 rounded-xl overflow-hidden p-6 shadow-2xl flex-shrink-0">
              {/* SVG Connecting Flow Lines */}
              <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 0 }}>
                <defs>
                  <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="var(--line)" />
                  </marker>
                  <marker id="arrow-warn" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="var(--warn)" />
                  </marker>
                </defs>

                {/* Flow 1: Data Prep to Causal */}
                <path
                  d="M 249 112 L 329 112"
                  stroke="var(--line)"
                  strokeWidth="2.5"
                  fill="none"
                  markerEnd="url(#arrow)"
                />

                {/* Flow 2: Causal to Readout */}
                <path
                  d="M 561 112 L 641 112"
                  stroke={isDegraded ? 'var(--warn)' : simState === 'rescoring' ? 'var(--warn)' : 'var(--line)'}
                  strokeWidth="3.5"
                  fill="none"
                  className={isDegraded || simState === 'rescoring' ? 'animate-flow-edge' : ''}
                  markerEnd={isDegraded || simState === 'rescoring' ? 'url(#arrow-warn)' : 'url(#arrow)'}
                />
              </svg>

              {/* Node 1: DATA PREP */}
              <div className="absolute left-[24px] top-[24px] w-[224px] h-[192px] bg-surface-2 border border-line rounded-xl p-5 shadow-lg soft-elevation flex flex-col justify-between transition-all duration-500">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-sans font-bold text-xs tracking-normal text-ink-hi">DATA PREP</span>
                    <span className="text-[10px] text-ok font-mono border border-ok/20 bg-ok/5 px-1.5 py-0.5 rounded-md font-semibold uppercase">● GCP</span>
                  </div>
                  <div className="flex justify-between items-center text-[10px] font-sans mb-2">
                    <span className="text-ink-lo">agent:</span>
                    <span className="text-ink-mid font-semibold">data-prep</span>
                  </div>
                  <div className="h-11 mb-2" /> {/* spacer to align metrics perfectly */}
                </div>
                
                {/* Mini-metrics */}
                <div className="grid grid-cols-3 gap-4 border-t border-line/45 pt-3 font-mono">
                  <div className="text-center">
                    <div className="text-[10px] text-ink-mid font-sans font-medium">passRate</div>
                    <div className="text-xs text-ok font-semibold tabular-nums mt-0.5">{getMetrics('data-prep').q.toFixed(2)}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-ink-mid font-sans font-medium">queryCost</div>
                    <div className="text-xs text-ink-mid tabular-nums mt-0.5">${getMetrics('data-prep').cost.toFixed(3)}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-ink-mid font-sans font-medium">latency</div>
                    <div className="text-xs text-ink-mid tabular-nums mt-0.5">{getMetrics('data-prep').latency}ms</div>
                  </div>
                </div>
              </div>

              {/* Node 2: CAUSAL ESTIMATION (THE CAUSE) */}
              <div className={`absolute left-[336px] top-[24px] w-[224px] h-[192px] bg-surface-2 border rounded-xl p-5 shadow-lg soft-elevation flex flex-col justify-between transition-all duration-500 ${
                isDegraded 
                  ? 'border-fault animate-fault-glow'
                  : simState === 'rescoring'
                  ? 'border-warn animate-warn-glow'
                  : 'border-line'
              }`}>
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-sans font-bold text-xs tracking-normal text-ink-hi">CAUSAL EST.</span>
                    <span className={`text-[10px] font-mono border px-1.5 py-0.5 rounded-md font-semibold uppercase transition-all duration-500 ${
                      simState === 'recovered'
                        ? 'text-ok border-ok/20 bg-ok/5'
                        : isDegraded
                        ? 'text-fault border-fault/20 bg-fault/5'
                        : 'text-info border-info/20 bg-info/5'
                    }`}>
                      {simState === 'recovered' ? '● AWS Spare' : '● AWS'}
                    </span>
                  </div>
                  
                  <div className="flex justify-between items-center text-[10px] font-sans mb-2">
                    <span className="text-ink-lo">agent:</span>
                    <span className={`font-semibold transition-colors duration-500 ${simState === 'recovered' ? 'text-ok' : isDegraded ? 'text-fault' : 'text-ink-mid'}`}>
                      {simState === 'recovered' ? 'causal-estimation-spare' : 'causal-estimation'}
                    </span>
                  </div>

                  {isDegraded ? (
                    <div className="mb-2 text-[9px] font-sans font-bold px-2 py-0.5 rounded-md bg-fault/10 text-fault border border-fault/20 tracking-normal text-center uppercase animate-pulse">
                      out of bounds ATE
                    </div>
                  ) : simState === 'rescoring' ? (
                    <div className="mb-2 text-[9px] font-sans font-bold px-2 py-0.5 rounded-md bg-warn/10 text-warn border border-warn/20 tracking-normal text-center uppercase animate-pulse">
                      eval re-scoring
                    </div>
                  ) : (
                    <div className="h-11 mb-2" />
                  )}
                </div>

                {/* Mini-metrics */}
                <div className="grid grid-cols-3 gap-4 border-t border-line/45 pt-3 font-mono">
                  <div className="text-center">
                    <div className="text-[10px] text-ink-mid font-sans font-medium">passRate</div>
                    <div className={`text-xs font-semibold tabular-nums mt-0.5 ${isDegraded ? 'text-fault' : simState === 'rescoring' ? 'text-warn' : 'text-ok'}`}>
                      {getMetrics('causal').q.toFixed(2)}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-ink-mid font-sans font-medium">queryCost</div>
                    <div className="text-xs text-ink-mid tabular-nums mt-0.5">${getMetrics('causal').cost.toFixed(3)}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-ink-mid font-sans font-medium">latency</div>
                    <div className="text-xs text-ink-mid tabular-nums mt-0.5">{getMetrics('causal').latency}ms</div>
                  </div>
                </div>
              </div>

              {/* Node 3: READOUT (THE SYMPTOM) */}
              <div className={`absolute left-[648px] top-[24px] w-[224px] h-[192px] bg-surface-2 border rounded-xl p-5 shadow-lg soft-elevation flex flex-col justify-between transition-all duration-500 ${
                isDegraded 
                  ? 'border-warn animate-warn-glow'
                  : 'border-line'
              }`}>
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-sans font-bold text-xs tracking-normal text-ink-hi">READOUT</span>
                    <span className="text-[10px] text-info font-mono border border-info/20 bg-info/5 px-1.5 py-0.5 rounded-md font-semibold uppercase">● Azure</span>
                  </div>
                  <div className="flex justify-between items-center text-[10px] font-sans mb-2">
                    <span className="text-ink-lo">agent:</span>
                    <span className="text-ink-mid font-semibold">readout</span>
                  </div>

                  {isDegraded ? (
                    <div className="mb-2 text-[9px] font-sans font-bold px-2 py-0.5 rounded-md bg-warn/10 text-warn border border-warn/20 tracking-normal text-center uppercase">
                      input from CAUSAL ↑
                    </div>
                  ) : (
                    <div className="h-11 mb-2" />
                  )}
                </div>

                {/* Mini-metrics */}
                <div className="grid grid-cols-3 gap-4 border-t border-line/45 pt-3 font-mono">
                  <div className="text-center">
                    <div className="text-[10px] text-ink-mid font-sans font-medium">passRate</div>
                    <div className={`text-xs font-semibold tabular-nums mt-0.5 ${isDegraded ? 'text-warn' : 'text-ok'}`}>
                      {getMetrics('readout').q.toFixed(2)}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-ink-mid font-sans font-medium">queryCost</div>
                    <div className="text-xs text-ink-mid tabular-nums mt-0.5">${getMetrics('readout').cost.toFixed(3)}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-ink-mid font-sans font-medium">latency</div>
                    <div className="text-xs text-ink-mid tabular-nums mt-0.5">{getMetrics('readout').latency}ms</div>
                  </div>
                </div>
              </div>

              {/* Persistent Causal Lift Slider widget in bottom rail */}
              <div className="absolute left-[24px] bottom-[24px] right-[24px] bg-surface-2 border border-line rounded-xl p-5 flex flex-col gap-3 shadow-lg soft-elevation">
                {/* Row 1: Labels */}
                <div className="flex justify-between items-center">
                  <span className="font-sans font-bold text-[10px] tracking-normal text-ink-mid">
                    ATE EFFECT ESTIMATE MONITOR
                  </span>
                  <div className="font-sans text-xs text-ink-lo flex items-center gap-1.5">
                    <span>bounds constraint:</span>
                    <span className="text-ok font-semibold font-mono border border-ok/20 bg-ok/5 px-1.5 py-0.5 rounded-md">[0.0%, 10.0%]</span>
                  </div>
                </div>

                {/* Row 2: The Bar */}
                <div className="relative w-full h-5 bg-surface-0 border border-line rounded-md overflow-hidden flex items-center">
                  {/* Healthy region background block */}
                  <div className="absolute left-0 top-0 bottom-0 w-[20%] bg-[#3DD68C]/5 border-r border-[#3DD68C]/20" />
                  
                  {/* Scale markers */}
                  <div className="absolute left-[20%] top-0 bottom-0 border-l border-dashed border-ink-lo/30 pointer-events-none" />
                  <div className="absolute left-[50%] top-0 bottom-0 border-l border-dashed border-ink-lo/30 pointer-events-none" />
                  <div className="absolute left-[80%] top-0 bottom-0 border-l border-dashed border-ink-lo/30 pointer-events-none" />

                  {/* Estimate cursor dot */}
                  <div 
                    className="absolute transition-all duration-[1200ms] ease-out w-3.5 h-3.5 rounded-full border shadow flex items-center justify-center transform -translate-x-1.5"
                    style={{ 
                      left: `${Math.min(97, Math.max(3, (effectEstimate / 50) * 100))}%`,
                      backgroundColor: effectEstimate > 10 ? 'var(--fault)' : 'var(--ok)',
                      borderColor: '#FFF',
                      boxShadow: effectEstimate > 10 ? '0 0 10px var(--fault)' : '0 0 10px var(--ok)'
                    }}
                  />
                </div>

                {/* Row 3: Axis Ticks */}
                <div className="flex justify-between text-[9px] font-mono text-ink-lo px-1">
                  <span>0% (no-effect)</span>
                  <span className="text-ok">10% (max threshold)</span>
                  <span>25%</span>
                  <span>50%</span>
                </div>

                {/* Row 4: Readout */}
                <div className="flex items-center gap-3 border-t border-line/45 pt-2.5">
                  <span className="font-sans text-xs text-ink-lo">current estimate:</span>
                  <span 
                    className={`font-mono text-xl font-bold tabular-nums tracking-tight transition-colors duration-500 ${
                      effectEstimate > 10 ? 'text-fault' : 'text-ok'
                    }`}
                  >
                    {effectEstimate >= 0 ? `+${effectEstimate.toFixed(1)}%` : `${effectEstimate.toFixed(1)}%`}
                  </span>
                  <span 
                    className={`text-[10px] font-sans font-bold px-2 py-0.5 rounded-md tracking-normal uppercase transition-all duration-500 ${
                      effectEstimate > 10 
                        ? 'bg-fault/10 text-fault border border-fault/20 animate-pulse' 
                        : 'bg-ok/10 text-ok border border-ok/20'
                    }`}
                  >
                    ● {effectEstimate > 10 ? 'out of bounds' : 'within bounds'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* TAB 2: TRIAGE VIEW */}
          <div className={`absolute inset-0 p-8 overflow-y-auto transition-all duration-300 ease-out ${
            activeTab === 'triage' ? 'opacity-100 translate-y-0 z-10 visible' : 'opacity-0 translate-y-4 pointer-events-none z-0 invisible'
          }`}>
            <div className="space-y-6 max-w-4xl mx-auto w-full">
              <h2 className="text-xl font-sans font-bold text-ink-hi flex items-center gap-2 tracking-tight">
                <span>Autonomous Triage Workspace</span>
                <span className="text-xs text-ink-lo font-sans font-normal border border-line px-1.5 py-0.5 rounded-md uppercase">Reasoning & Action</span>
              </h2>

              {/* Streaming Terminal */}
              <div className="bg-black/40 border border-line rounded-xl overflow-hidden shadow-2xl soft-elevation flex flex-col">
                <div className="flex items-center justify-between bg-surface-2 border-b border-line px-4 py-2.5">
                  <div className="flex items-center">
                    <span className="font-sans text-xs font-semibold text-ink-mid uppercase tracking-wider">Triage Logging Monitor</span>
                  </div>
                  <span className="font-mono text-[10px] text-ink-lo">SYSTEM: ONLINE</span>
                </div>

                <div className="p-4 font-mono text-xs space-y-1.5 h-[240px] overflow-y-auto bg-[#06080C] text-[#A6B2C8]">
                  {visibleLogs.length === 0 ? (
                    <div className="text-ink-lo italic flex items-center justify-center h-full">
                      {simState === 'healthy' 
                        ? 'No active fault localization logs. System is stable.'
                        : 'Fault detected. Initializing localization tracing...'
                      }
                    </div>
                  ) : (
                    visibleLogs.map((log, i) => (
                      <div key={i} className="whitespace-pre-wrap leading-relaxed animate-fade-in">
                        {log.includes('VERDICT:') ? (
                          <span className="text-fault font-semibold">{log}</span>
                        ) : log.includes('bounds check') || log.includes('McNemar') ? (
                          <span className="text-warn">{log}</span>
                        ) : log.includes('[detector]') || log.includes('Triage complete') ? (
                          <span className="text-ok">{log}</span>
                        ) : log.includes('[triage-agent]') ? (
                          <span className="text-info">{log}</span>
                        ) : (
                          log
                        )}
                      </div>
                    ))
                  )}
                  {simState === 'triaging' && (
                    <span className="inline-block w-1.5 h-4 bg-ink-hi animate-pulse ml-0.5" />
                  )}
                </div>
              </div>

              {/* Verdict Card */}
              {isDegraded && (simState === 'awaiting_approval' || simState === 'triaging') && (
                <div className="border border-fault bg-fault/5 rounded-xl p-6 space-y-4 shadow-xl soft-elevation animate-fade-in">
                  <div className="flex items-center justify-between border-b border-fault/20 pb-3">
                    <span className="font-sans font-bold text-sm tracking-normal text-fault uppercase">
                      ▲ FAULT LOCALIZED & ISOLATED
                    </span>
                    <span className="text-[10px] font-mono text-ink-lo bg-surface-2 px-2 py-0.5 rounded-md border border-line">
                      run: {dbData?.triage_clusters?.[0]?.cluster_id || 'cluster-4a8f9c'}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-6 py-2">
                    <div className="flex items-center gap-4 bg-surface-1 border border-line rounded-xl p-4">
                      <span className="text-xs font-sans text-ink-lo w-16">CAUSE:</span>
                      <div className="flex flex-col">
                        <span className="font-sans font-bold text-sm text-fault">CAUSAL ESTIMATION</span>
                        <span className="text-[10px] text-ink-mid font-mono">pass_rate: 0.18</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-4 bg-surface-1 border border-line rounded-xl p-4">
                      <span className="text-xs font-sans text-ink-lo w-16">SYMPTOM:</span>
                      <div className="flex flex-col">
                        <span className="font-sans font-bold text-sm text-warn">READOUT</span>
                        <span className="text-[10px] text-ink-mid font-mono">pass_rate: 0.42</span>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2 font-sans text-xs border-t border-line/30 pt-4">
                    <div className="flex gap-4">
                      <span className="text-ink-lo w-24 flex-shrink-0">root cause:</span>
                      <span className="text-ink-hi leading-relaxed">
                        Effect estimates fall outside plausible bounds (<span className="font-mono">+48.5%</span> observed ATE vs <span className="font-mono">[0.0%, 10.0%]</span> threshold) after causal model update. Downstream readout faithfully propagated this contaminated input, causing secondary failures.
                      </span>
                    </div>
                    <div className="flex gap-4">
                      <span className="text-ink-lo w-24 flex-shrink-0">confidence:</span>
                      <span className="text-info font-semibold">out-of-bounds oracle — provable</span>
                    </div>
                  </div>

                  {/* Actions / Approve Tasks */}
                  <div className="bg-surface-2 border border-line rounded-xl p-4 mt-4 space-y-4 soft-elevation">
                    <div className="flex items-center justify-between border-b border-line/45 pb-3">
                      <div className="flex flex-col">
                        <span className="font-sans font-bold text-xs tracking-normal text-ink-hi">
                          PROPOSED EVALUATION SCENARIOS
                        </span>
                        <span className="text-[10px] text-ink-lo font-sans">
                          human review required — triage proposes, you dispose
                        </span>
                      </div>
                      <span className="text-[9px] font-mono bg-info/10 text-info border border-info/20 px-2 py-0.5 rounded-md tracking-wide font-bold uppercase">
                        3 Drafted
                      </span>
                    </div>

                    <div className="space-y-2">
                      {[
                        { title: 'ATE Bounds Check', desc: 'Validates synthetic lift boundaries and triggers warnings on values > 10.0%' },
                        { title: 'Covariate Covariance Variance', desc: 'Verifies CUPED adjustment does not introduce variance regressions' },
                        { title: 'Readout Contamination Filter', desc: 'Evaluates memo agent behavior when presented with out-of-bound inputs' }
                      ].map((t, idx) => (
                        <div key={idx} className="flex items-start gap-3 bg-surface-1/40 p-4 rounded-xl border border-line/40 text-xs">
                          <span className="font-mono text-info font-semibold">0{idx+1}.</span>
                          <div>
                            <div className="font-bold text-ink-hi">{t.title}</div>
                            <div className="text-[10px] text-ink-mid mt-0.5">{t.desc}</div>
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className="flex justify-end gap-3 pt-3">
                      <button 
                        onClick={approveTriage}
                        className="font-sans text-xs font-bold text-surface-0 bg-ok hover:bg-[#2fc47d] border border-ok px-6 py-2.5 rounded-md transition-all shadow-lg active:scale-95 cursor-pointer"
                      >
                        Approve & Rollout Tasks
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Safe state summary if healthy */}
              {!isDegraded && (
                <div className="border border-line bg-surface-1/30 rounded-xl p-12 text-center space-y-3 soft-elevation">
                  <div className="w-12 h-12 rounded-full bg-ok/10 border border-ok/30 flex items-center justify-center mx-auto text-ok font-bold text-lg">
                    ✓
                  </div>
                  <h3 className="font-sans font-bold text-sm text-ink-hi">System Stable</h3>
                  <p className="text-xs text-ink-mid max-w-sm mx-auto font-sans">
                    All components are within statistical control thresholds. Autonomous triage is idle.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* TAB 3: PARETO VIEW */}
          <div className={`absolute inset-0 p-8 overflow-y-auto transition-all duration-300 ease-out ${
            activeTab === 'pareto' ? 'opacity-100 translate-y-0 z-10 visible' : 'opacity-0 translate-y-4 pointer-events-none z-0 invisible'
          }`}>
            <div className="space-y-6 max-w-4xl mx-auto w-full">
              <div className="flex justify-between items-start">
                <div>
                  <h2 className="text-xl font-sans font-bold text-ink-hi flex items-center gap-2 tracking-tight">
                    <span>Multi-Agent Pareto Optimization</span>
                    <span className="text-xs text-ink-lo font-sans font-normal border border-line px-1.5 py-0.5 rounded-md uppercase">Efficiency Frontier</span>
                  </h2>
                  <p className="text-xs text-ink-mid mt-1 font-sans">
                    Comparative trade-off curves showing cost vs execution quality across baseline and learned router policies.
                  </p>
                </div>
                
                <div className="bg-surface-2 border border-line px-3 py-1.5 rounded-md flex items-center gap-4 text-xs font-sans">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2.5 h-0.5 bg-ink-mid inline-block border-t border-dashed" />
                    <span className="text-ink-lo font-sans">Baseline</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-3.5 h-1 bg-ok inline-block rounded-md" />
                    <span className="text-ok font-bold font-sans">Learned Router</span>
                  </div>
                </div>
              </div>

              {/* SVG Curve Chart */}
              <div className="bg-surface-1 border border-line rounded-xl p-6 shadow-2xl relative soft-elevation">
                <svg viewBox="0 0 600 360" className="w-full h-auto">
                  {/* Grid Lines */}
                  <line x1="60" y1="40" x2="560" y2="40" stroke="var(--line)" strokeWidth="0.5" strokeDasharray="4 4" />
                  <line x1="60" y1="100" x2="560" y2="100" stroke="var(--line)" strokeWidth="0.5" strokeDasharray="4 4" />
                  <line x1="60" y1="160" x2="560" y2="160" stroke="var(--line)" strokeWidth="0.5" strokeDasharray="4 4" />
                  <line x1="60" y1="220" x2="560" y2="220" stroke="var(--line)" strokeWidth="0.5" strokeDasharray="4 4" />
                  <line x1="60" y1="280" x2="560" y2="280" stroke="var(--line)" strokeWidth="0.5" strokeDasharray="4 4" />

                  {/* Vertical Axis line */}
                  <line x1="60" y1="20" x2="60" y2="300" stroke="var(--line)" strokeWidth="1.5" />
                  {/* Horizontal Axis line */}
                  <line x1="60" y1="300" x2="580" y2="300" stroke="var(--line)" strokeWidth="1.5" />

                  {/* Y-Axis labels (Quality Pass Rate) */}
                  <text x="48" y="44" fill="var(--ink-lo)" className="font-mono text-[9px]" textAnchor="end">1.00</text>
                  <text x="48" y="104" fill="var(--ink-lo)" className="font-mono text-[9px]" textAnchor="end">0.90</text>
                  <text x="48" y="164" fill="var(--ink-lo)" className="font-mono text-[9px]" textAnchor="end">0.80</text>
                  <text x="48" y="224" fill="var(--ink-lo)" className="font-mono text-[9px]" textAnchor="end">0.70</text>
                  <text x="48" y="284" fill="var(--ink-lo)" className="font-mono text-[9px]" textAnchor="end">0.60</text>
                  <text x="48" y="304" fill="var(--ink-lo)" className="font-mono text-[9px]" textAnchor="end">0.50</text>
                  <text x="15" y="170" fill="var(--ink-mid)" className="font-sans text-[10px] tracking-wider uppercase font-bold" transform="rotate(-90 15 170)" textAnchor="middle">Quality (Pass Rate)</text>

                  {/* X-Axis labels (Query Cost) */}
                  <text x="140" y="318" fill="var(--ink-lo)" className="font-mono text-[9px]" textAnchor="middle">$0.005</text>
                  <text x="240" y="318" fill="var(--ink-lo)" className="font-mono text-[9px]" textAnchor="middle">$0.010</text>
                  <text x="340" y="318" fill="var(--ink-lo)" className="font-mono text-[9px]" textAnchor="middle">$0.015</text>
                  <text x="440" y="318" fill="var(--ink-lo)" className="font-mono text-[9px]" textAnchor="middle">$0.020</text>
                  <text x="540" y="318" fill="var(--ink-lo)" className="font-mono text-[9px]" textAnchor="middle">$0.028</text>
                  <text x="310" y="340" fill="var(--ink-mid)" className="font-sans text-[10px] tracking-wider uppercase font-bold" textAnchor="middle">API Query Cost per Request ($)</text>

                  {/* Baseline Curve (Dashed, Muted Ink) */}
                  <path
                    d="M 140 228 L 240 172 L 340 124 L 440 100 L 520 82"
                    fill="none"
                    stroke="var(--ink-lo)"
                    strokeWidth="1.5"
                    strokeDasharray="4 4"
                  />
                  {/* Baseline curve points */}
                  <circle cx="140" cy="228" r="3.5" fill="var(--ink-lo)" />
                  <circle cx="240" cy="172" r="3.5" fill="var(--ink-lo)" />
                  <circle cx="340" cy="124" r="3.5" fill="var(--ink-lo)" />
                  <circle cx="440" cy="100" r="3.5" fill="var(--ink-lo)" />
                  <circle cx="520" cy="82" r="3.5" fill="var(--ink-lo)" />

                  {/* Learned Curve (Green, Glowing, Animated) */}
                  <path
                    d="M 100 172 L 160 94 L 240 70 L 340 58 L 480 52"
                    fill="none"
                    stroke="var(--ok)"
                    strokeWidth="3"
                    strokeDasharray="1000"
                    strokeDashoffset={1000 - (paretoProgress * 10)}
                    style={{ filter: 'drop-shadow(0px 0px 4px rgba(61, 214, 140, 0.5))' }}
                  />

                  {/* Learned curve points */}
                  {paretoProgress >= 20 && <circle cx="100" cy="172" r="4.5" fill="var(--ok)" />}
                  {paretoProgress >= 40 && <circle cx="160" cy="94" r="4.5" fill="var(--ok)" />}
                  {paretoProgress >= 60 && <circle cx="240" cy="70" r="4.5" fill="var(--ok)" />}
                  {paretoProgress >= 80 && <circle cx="340" cy="58" r="4.5" fill="var(--ok)" />}
                  {paretoProgress >= 100 && <circle cx="480" cy="52" r="4.5" fill="var(--ok)" />}

                  {/* Callout box and annotation */}
                  {paretoProgress >= 90 && (
                    <g className="animate-fade-in">
                      {/* Connection line from callout */}
                      <path d="M 160 94 L 210 130 L 260 130" fill="none" stroke="var(--info)" strokeWidth="1" />
                      <circle cx="160" cy="94" r="7" fill="none" stroke="var(--info)" strokeWidth="1" className="animate-ping" />
                      
                      {/* Callout Tag */}
                      <rect x="260" y="115" width="220" height="30" rx="6" fill="var(--surface-3)" stroke="var(--line)" />
                      <text x="270" y="133" fill="var(--ink-hi)" className="font-sans text-[9px] font-bold">
                        LEARNED ROUTER: same quality, ~40% less cost
                      </text>
                    </g>
                  )}
                </svg>
              </div>
            </div>
          </div>

          {/* TAB 4: SIGNALS VIEW */}
          <div className={`absolute inset-0 p-8 overflow-y-auto transition-all duration-300 ease-out ${
            activeTab === 'signals' ? 'opacity-100 translate-y-0 z-10 visible' : 'opacity-0 translate-y-4 pointer-events-none z-0 invisible'
          }`}>
            <div className="space-y-6 max-w-4xl mx-auto w-full">
              <h2 className="text-xl font-sans font-bold text-ink-hi flex items-center gap-2 tracking-tight">
                <span>Real-Time Signal Telemetry</span>
                <span className="text-xs text-ink-lo font-sans font-normal border border-line px-1.5 py-0.5 rounded-md uppercase">Signal Channels</span>
              </h2>

              <div className="grid grid-cols-2 gap-4">
                {[
                  {
                    title: 'Out of Bounds Lift Ratio',
                    desc: 'Flags causal estimates violating configured threshold limits (0 = Normal, 1 = Triggered).',
                    points: isDegraded ? '0,45 20,45 40,45 60,45 80,45 100,45 120,45 140,5' : '0,45 20,45 40,45 60,45 80,45 100,45 120,45 140,45',
                    triggered: isDegraded,
                    unit: 'state'
                  },
                  {
                    title: 'System Latency Spike (Causal Estimation)',
                    desc: 'Execution duration tracking. Slower response profiles represent degradation.',
                    points: isDegraded ? '0,35 20,38 40,32 60,34 80,36 100,32 120,35 140,8' : '0,35 20,38 40,32 60,34 80,36 100,32 120,35 140,33',
                    triggered: isDegraded,
                    unit: 'ms'
                  },
                  {
                    title: 'Low Confidence Output (Readout Classifier)',
                    desc: 'Model outputs classified for downstream logical contradictions and SRM anomalies.',
                    points: isDegraded ? '0,45 20,45 40,45 60,45 80,45 100,45 120,45 140,10' : '0,45 20,45 40,45 60,45 80,45 100,45 120,45 140,45',
                    triggered: isDegraded,
                    unit: 'state'
                  },
                  {
                    title: 'Tool Invocation Errors',
                    desc: 'Failure rates of APIs, DB connections, or intermediate pipeline tasks.',
                    points: '0,40 20,42 40,38 60,43 80,39 100,41 120,40 140,38',
                    triggered: false,
                    unit: 'rate'
                  }
                ].map((sig, i) => (
                  <div key={i} className={`p-5 rounded-xl bg-surface-2 border transition-all duration-500 soft-elevation ${
                    sig.triggered ? 'border-fault/40 bg-fault/5' : 'border-line'
                  }`}>
                    <div className="flex justify-between items-start mb-2">
                      <h3 className="text-xs font-sans font-bold text-ink-hi">{sig.title}</h3>
                      <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded-md uppercase ${
                        sig.triggered ? 'bg-fault/15 text-fault' : 'bg-ok/15 text-ok'
                      }`}>
                        {sig.triggered ? 'ALARM' : 'STABLE'}
                      </span>
                    </div>

                    <p className="text-[10px] text-ink-mid mb-4 h-8 font-sans">{sig.desc}</p>

                    {/* Sparkline block */}
                    <div className="flex items-center gap-4">
                      <div className="h-14 w-44 bg-surface-0 border border-line/45 rounded-md p-1">
                        <svg viewBox="0 0 140 50" className="w-full h-full">
                          <polyline
                            fill="none"
                            stroke={sig.triggered ? 'var(--fault)' : 'var(--ok)'}
                            strokeWidth="2"
                            points={sig.points}
                          />
                        </svg>
                      </div>
                      <div className="font-mono text-xs text-ink-lo">
                        <div>current:</div>
                        <div className={`text-base font-bold tabular-nums ${sig.triggered ? 'text-fault' : 'text-ink-hi'}`}>
                          {sig.unit === 'state' 
                            ? (sig.triggered ? '1.0' : '0.0') 
                            : sig.unit === 'ms' 
                            ? (sig.triggered ? '450ms' : '280ms') 
                            : '0.00'}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* TAB 5: ROUTER VIEW */}
          <div className={`absolute inset-0 p-8 overflow-y-auto transition-all duration-300 ease-out ${
            activeTab === 'router' ? 'opacity-100 translate-y-0 z-10 visible' : 'opacity-0 translate-y-4 pointer-events-none z-0 invisible'
          }`}>
            <div className="space-y-6 max-w-4xl mx-auto w-full">
              <h2 className="text-xl font-sans font-bold text-ink-hi flex items-center gap-2 tracking-tight">
                <span>Decentralized Router Decision log</span>
                <span className="text-xs text-ink-lo font-sans font-normal border border-line px-1.5 py-0.5 rounded-md uppercase">Decision Feed</span>
              </h2>

              <div className="bg-surface-2 border border-line rounded-xl overflow-hidden shadow-2xl p-4 soft-elevation">
                <table className="w-full text-left font-mono text-xs border-collapse">
                  <thead>
                    <tr className="bg-surface-1 border-b border-line text-ink-lo font-sans font-bold">
                      <th className="p-4">REQUEST ID</th>
                      <th className="p-4">STEP</th>
                      <th className="p-4">ROUTING TARGET</th>
                      <th className="p-4 text-right">P(SUCCESS)</th>
                      <th className="p-4 text-right">COST</th>
                      <th className="p-4">RATIONALE</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line/30">
                    {simState === 'recovered' && (
                      <tr className="bg-ok/5 animate-fade-in text-ink-hi">
                        <td className="p-4 font-semibold">req-7f89ac</td>
                        <td className="p-4 text-info">causal_estimation</td>
                        <td className="p-4"><span className="text-ok border border-ok/20 bg-ok/5 px-2 py-0.5 rounded-md">causal-estimation-spare</span></td>
                        <td className="p-4 text-right tabular-nums">0.94</td>
                        <td className="p-4 text-right tabular-nums">$0.012</td>
                        <td className="p-4 text-ink-mid">Rerouted to spare after active fault isolation verified ATE constraints on model.</td>
                      </tr>
                    )}
                    
                    {[
                      { req: 'req-3a21bc', step: 'readout', target: 'readout', p: '0.94', cost: '$0.004', rat: 'Stable route match on Azure OpenAI client configuration.' },
                      { req: 'req-9e12cd', step: 'data_prep', target: 'data-prep', p: '0.98', cost: '$0.002', rat: 'Matched baseline specs. Negligible variance.' },
                      { req: 'req-4c91ff', step: 'causal_estimation', target: 'causal-estimation', p: isDegraded ? '0.18' : '0.91', cost: '$0.011', rat: isDegraded ? 'Extreme variance detected. High statistical degradation risk.' : 'Routed to AWS Bedrock. Matches performance metrics.' },
                      { req: 'req-2a118e', step: 'readout', target: 'readout', p: '0.94', cost: '$0.004', rat: 'Matched Azure spare parameters successfully.' }
                    ].map((row, idx) => (
                      <tr key={idx} className="hover:bg-surface-3/30 transition-colors text-ink-mid">
                        <td className="p-4 font-semibold text-ink-hi">{row.req}</td>
                        <td className="p-4 text-info">{row.step}</td>
                        <td className="p-4">
                          <span className={`px-2 py-0.5 rounded-md border ${
                            row.p === '0.18' 
                              ? 'text-fault border-fault/20 bg-fault/5' 
                              : 'text-ink-hi border-line bg-surface-1'
                          }`}>
                            {row.target}
                          </span>
                        </td>
                        <td className={`p-4 text-right tabular-nums font-bold ${row.p === '0.18' ? 'text-fault' : 'text-ink-hi'}`}>{row.p}</td>
                        <td className="p-4 text-right tabular-nums">{row.cost}</td>
                        <td className="p-4 text-ink-lo max-w-[280px] truncate">{row.rat}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* TAB 6: END CARD VIEW */}
          <div className={`absolute inset-0 p-8 overflow-y-auto transition-all duration-300 ease-out flex flex-col items-center justify-center ${
            activeTab === 'end' ? 'opacity-100 translate-y-0 z-10 visible' : 'opacity-0 translate-y-4 pointer-events-none z-0 invisible'
          }`}>
            <div className="flex flex-col items-center justify-center max-w-xl mx-auto space-y-8 text-center">
              {/* Header */}
              <div>
                <h1 className="font-sans font-bold text-4xl tracking-tight text-ink-hi uppercase">
                  AgentLab
                </h1>
                <p className="font-sans text-xs text-ink-mid mt-2 tracking-wide">
                  step-level fault localization for multi-agent pipelines
                </p>
              </div>

              {/* QR Code Container */}
              <div className="bg-surface-2 border border-line rounded-xl p-6 shadow-2xl flex flex-col items-center justify-center gap-3 soft-elevation">
                <div className="bg-white p-2 rounded-lg">
                  <QRCodeSVG
                    value="https://github.com/apoorv-shrivastav/agentlab-mesh-router"
                    size={180}
                    bgColor="#FFFFFF"
                    fgColor="#0B0E14"
                    level="M"
                    marginSize={2}
                  />
                </div>
                <span className="font-sans text-[10px] text-ink-mid tracking-normal uppercase mt-1">
                  scan for the source ➔
                </span>
              </div>

              {/* Closing Quote */}
              <div className="space-y-3">
                <blockquote className="font-sans italic text-sm text-ink-hi leading-relaxed max-w-md mx-auto">
                  "When an agent pipeline gives you a confident wrong answer, the question that matters is which step, and how do you know."
                </blockquote>
                <p className="font-sans text-[10px] text-ink-lo tracking-normal uppercase">
                  Apoorv Shrivastav · Senior Data Scientist
                </p>
              </div>
            </div>
          </div>

        </main>
      </div>
      
    </div>
  );
}
