import React, { useState, useEffect, useRef } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'
import {
  LayoutDashboard, Binary, BookOpen, Layers, Type, Percent, Cpu,
  Flame, Sliders, Play, Square, Terminal, ShieldAlert, Sparkles,
  Download, ArrowRight, Eye, ChevronRight, Settings as SettingsIcon,
  Search, RefreshCw, MessageSquare, Upload, Trash2, Send, Bot, User,
  FileText, CheckCircle2, AlertCircle
} from 'lucide-react'
import { useStore } from './store/useStore'
import type { DashboardStats, SystemSettings, LossData, ValLossData } from './store/useStore'
import { api } from './services/api'

// Simple Toast implementation
interface Toast {
  id: string
  msg: string
  type: 'success' | 'error' | 'info'
}

export default function App() {
  const {
    activeTab, setActiveTab, wsConnected, setWsConnected,
    isTraining, stats, updateStats, settings, updateSettings,
    logs, addLog, losses, setLosses, valLosses, setValLosses
  } = useStore()

  // Local component states
  const [toasts, setToasts] = useState<Toast[]>([])
  const [consoleCollapsed, setConsoleCollapsed] = useState(false)
  const [selectedTensor, setSelectedTensor] = useState<{
    name: string
    id: number
    shape: number[]
    vector: number[]
    mean: number
    std: number
    min: number
    max: number
  } | null>(null)

  // API states

  // 1. Toast Helpers
  const showToast = (msg: string, type: 'success' | 'error' | 'info' = 'info') => {
    const id = Math.random().toString(36).substring(2, 9)
    setToasts(prev => [...prev, { id, msg, type }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 4000)
  }

  // 2. Poll Dashboard Stats and settings
  const fetchStats = async () => {
    try {
      const info = await api.getDashboard()
      updateStats(info)
    } catch (err: any) {
      console.error(err)
    }
  }

  const fetchSettings = async () => {
    try {
      const cfg = await api.getSettings()
      updateSettings(cfg.settings)
    } catch (err: any) {
      console.error(err)
    }
  }

  useEffect(() => {
    fetchStats()
    fetchSettings()
    const interval = setInterval(fetchStats, 3000)
    return () => clearInterval(interval)
  }, [])

  // 3. WebSockets Training Stream handler
  useEffect(() => {
    let ws: WebSocket | null = null
    const connectWS = () => {
      if (ws) {
        try {
          ws.close()
        } catch (e) {}
      }
      ws = new WebSocket('ws://127.0.0.1:8000/ws/training')
      
      ws.onopen = () => {
        setWsConnected(true)
        showToast('WebSocket connected to live training feed.', 'success')
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          // Bulk update stats
          updateStats({
            is_training: data.is_training,
            current_epoch: data.current_epoch,
            current_step: data.current_step
          })
          
          if (data.new_losses && data.new_losses.length > 0) {
            // Append new losses dynamically using getState to avoid stale closure references
            const currentLosses = useStore.getState().losses
            setLosses([...currentLosses, ...data.new_losses])
          }
          if (data.val_losses) {
            setValLosses(data.val_losses)
          }
          if (data.logs && data.logs.length > 0) {
            data.logs.forEach((logLine: string) => addLog(logLine))
          }
        } catch (err) {
          console.error('WS parse error:', err)
        }
      }

      ws.onclose = () => {
        setWsConnected(false)
        // Retry after 5s
        setTimeout(connectWS, 5000)
      }

      ws.onerror = () => {
        setWsConnected(false)
      }
    }

    connectWS()
    return () => {
      if (ws) ws.close()
    }
  }, [])

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-gray-950 text-gray-100 font-sans selection:bg-indigo-500 selection:text-white relative">
      
      {/* Dynamic Glowing Spot for visual design */}
      <div className="glow-spot top-10 left-1/4" />
      <div className="glow-spot bottom-10 right-1/4" />

      {/* 1. Header component */}
      <header className="flex items-center justify-between px-6 py-4 glass-panel border-b border-gray-800 z-10 shrink-0">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 bg-gradient-to-tr from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Sparkles className="h-5 w-5 text-white animate-pulse" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
              MyGPT Studio
              <span className="text-xs bg-indigo-500/20 text-indigo-400 font-semibold px-2 py-0.5 rounded-full border border-indigo-500/30">v2.0</span>
            </h1>
            <p className="text-xs text-gray-400">Deep Learning Model Laboratory</p>
          </div>
        </div>

        <div className="flex items-center gap-5">
          {/* GPU Status Badge */}
          <div className="flex items-center gap-2 text-xs bg-gray-900 border border-gray-800 rounded-lg px-3 py-1.5">
            <Cpu className={`h-4 w-4 ${stats?.device.includes('cuda') ? 'text-green-400 animate-pulse' : 'text-gray-400'}`} />
            <span className="text-gray-400">Device:</span>
            <span className="font-semibold text-gray-200 uppercase">{stats?.device || 'CPU'}</span>
          </div>

          {/* WS Status badge */}
          <div className="flex items-center gap-2 text-xs bg-gray-900 border border-gray-800 rounded-lg px-3 py-1.5">
            <span className={`h-2 w-2 rounded-full ${wsConnected ? 'bg-green-400' : 'bg-red-400 animate-ping'}`} />
            <span className="text-gray-400">WebSocket:</span>
            <span className="font-semibold text-gray-200">{wsConnected ? 'Connected' : 'Offline'}</span>
          </div>

          {/* Model active status */}
          {stats?.is_training && (
            <div className="flex items-center gap-2 bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs px-3 py-1.5 rounded-lg animate-pulse">
              <Flame className="h-4 w-4" />
              <span>Training Model...</span>
            </div>
          )}
        </div>
      </header>

      {/* Workspace Frame */}
      <div className="flex flex-1 overflow-hidden">
        
        {/* 2. Left Sidebar Navigation */}
        <aside className="w-64 glass-panel border-r border-gray-800 flex flex-col justify-between p-4 z-10 shrink-0">
          <nav className="flex flex-col gap-1.5">
            <SidebarItem
              icon={<LayoutDashboard />}
              label="Dashboard"
              active={activeTab === 'dashboard'}
              onClick={() => setActiveTab('dashboard')}
            />
            <SidebarItem
              icon={<Binary />}
              label="BPE Tokenizer"
              active={activeTab === 'tokenizer'}
              onClick={() => setActiveTab('tokenizer')}
            />
            <SidebarItem
              icon={<BookOpen />}
              label="Vocabulary"
              active={activeTab === 'vocab'}
              onClick={() => setActiveTab('vocab')}
            />
            <SidebarItem
              icon={<Layers />}
              label="Dataset Viewer"
              active={activeTab === 'dataset'}
              onClick={() => setActiveTab('dataset')}
            />
            <SidebarItem
              icon={<Type />}
              label="Embedding Layer"
              active={activeTab === 'embeddings'}
              onClick={() => setActiveTab('embeddings')}
            />
            <SidebarItem
              icon={<Percent />}
              label="Positional Encoding"
              active={activeTab === 'positional'}
              onClick={() => setActiveTab('positional')}
            />
            <SidebarItem
              icon={<Eye />}
              label="Attention Weights"
              active={activeTab === 'attention'}
              onClick={() => setActiveTab('attention')}
            />
            <SidebarItem
              icon={<ChevronRight />}
              label="Transformer Blocks"
              active={activeTab === 'transformer'}
              onClick={() => setActiveTab('transformer')}
            />
            <SidebarItem
              icon={<Flame />}
              label="Training Control"
              active={activeTab === 'training'}
              onClick={() => setActiveTab('training')}
            />
            <SidebarItem
              icon={<Play />}
              label="Inference Playground"
              active={activeTab === 'playground'}
              onClick={() => setActiveTab('playground')}
            />
            <SidebarItem
              icon={<MessageSquare />}
              label="Document Chat"
              active={activeTab === 'chat'}
              onClick={() => setActiveTab('chat')}
            />
            <SidebarItem
              icon={<Download />}
              label="Checkpoints"
              active={activeTab === 'checkpoints'}
              onClick={() => setActiveTab('checkpoints')}
            />
            <SidebarItem
              icon={<SettingsIcon />}
              label="Settings"
              active={activeTab === 'settings'}
              onClick={() => setActiveTab('settings')}
            />
          </nav>

          {/* Quick specs at bottom of sidebar */}
          <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-3 text-xs flex flex-col gap-1">
            <span className="text-gray-400 font-semibold uppercase tracking-wider text-[10px]">Model Architecture</span>
            <div className="flex justify-between text-gray-300">
              <span>Layers:</span>
              <span className="font-bold">{stats?.num_layers || 0}</span>
            </div>
            <div className="flex justify-between text-gray-300">
              <span>Heads:</span>
              <span className="font-bold">{stats?.num_heads || 0}</span>
            </div>
            <div className="flex justify-between text-gray-300">
              <span>Embedding Dim:</span>
              <span className="font-bold">{stats?.embedding_dim || 0}</span>
            </div>
          </div>
        </aside>

        {/* 3. Main Workspace Panel */}
        <main className="flex-1 flex flex-col overflow-hidden bg-gray-950/20 relative">
          
          {/* Main dynamic Tab content viewport */}
          <div className="flex-1 overflow-y-auto p-6">
            {activeTab === 'dashboard' && <DashboardView stats={stats} />}
            {activeTab === 'tokenizer' && <TokenizerView showToast={showToast} setSelectedTensor={setSelectedTensor} />}
            {activeTab === 'vocab' && <VocabView showToast={showToast} />}
            {activeTab === 'dataset' && <DatasetView showToast={showToast} />}
            {activeTab === 'embeddings' && <EmbeddingView showToast={showToast} setSelectedTensor={setSelectedTensor} />}
            {activeTab === 'positional' && <PositionalView showToast={showToast} />}
            {activeTab === 'attention' && <AttentionView showToast={showToast} />}
            {activeTab === 'transformer' && <TransformerView stats={stats} />}
            {activeTab === 'training' && <TrainingView losses={losses} valLosses={valLosses} settings={settings} isTraining={isTraining} showToast={showToast} />}
            {activeTab === 'playground' && <PlaygroundView showToast={showToast} />}
            {activeTab === 'chat' && <DocumentChatView showToast={showToast} />}
            {activeTab === 'checkpoints' && <CheckpointsView showToast={showToast} />}
            {activeTab === 'settings' && <SettingsView settings={settings} fetchSettings={fetchSettings} showToast={showToast} />}
          </div>

          {/* 4. Bottom Console Panel */}
          <div className={`glass-panel border-t border-gray-800 flex flex-col z-10 shrink-0 ${consoleCollapsed ? 'h-10' : 'h-48'}`}>
            <div className="flex justify-between items-center px-4 py-2 border-b border-gray-800 bg-gray-900/50">
              <div className="flex items-center gap-2 text-xs font-semibold text-gray-300">
                <Terminal className="h-4 w-4 text-indigo-400" />
                <span>Background Execution Console</span>
              </div>
              <button
                onClick={() => setConsoleCollapsed(!consoleCollapsed)}
                className="text-xs text-gray-400 hover:text-gray-200 px-2 py-0.5 rounded hover:bg-gray-800 transition-all"
              >
                {consoleCollapsed ? 'Expand' : 'Collapse'}
              </button>
            </div>
            
            {!consoleCollapsed && (
              <div className="flex-1 p-3 overflow-y-auto font-mono text-[11px] text-green-400 flex flex-col gap-1 bg-gray-950/80">
                {logs.length === 0 ? (
                  <span className="text-gray-500">No output logs received. Start training or run inference to inspect...</span>
                ) : (
                  logs.map((logLine, idx) => (
                    <div key={idx} className="leading-5">
                      <span className="text-gray-500 select-none">$&nbsp;</span>
                      {logLine}
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </main>

        {/* 5. Right Tensor Inspector Panel */}
        <aside className="w-80 glass-panel border-l border-gray-800 p-5 flex flex-col justify-between z-10 shrink-0">
          <div className="flex flex-col gap-5">
            <div className="flex items-center gap-2 border-b border-gray-800 pb-3">
              <Layers className="h-5 w-5 text-indigo-400" />
              <h2 className="font-bold text-sm tracking-tight text-white uppercase">Tensor Inspector</h2>
            </div>

            {selectedTensor ? (
              <div className="flex flex-col gap-4 text-xs">
                <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-4 flex flex-col gap-3">
                  <div>
                    <span className="text-gray-400 block font-semibold text-[10px] uppercase">Selected Element</span>
                    <span className="text-lg font-bold text-indigo-300 font-mono">"{selectedTensor.name}"</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    <div>
                      <span className="text-gray-400 block">Vocab ID</span>
                      <span className="font-bold text-gray-200 font-mono">{selectedTensor.id}</span>
                    </div>
                    <div>
                      <span className="text-gray-400 block">Tensor Shape</span>
                      <span className="font-bold text-gray-200 font-mono">[{selectedTensor.shape.join(', ')}]</span>
                    </div>
                  </div>
                </div>

                <div className="flex flex-col gap-2">
                  <span className="text-gray-400 font-semibold text-[10px] uppercase">Tensor Statistics</span>
                  <div className="bg-gray-900/40 border border-gray-800/80 rounded-xl p-3 flex flex-col gap-1.5 font-mono text-[11px]">
                    <div className="flex justify-between">
                      <span className="text-gray-400">Mean:</span>
                      <span className="text-gray-200">{selectedTensor.mean.toFixed(6)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Std Dev:</span>
                      <span className="text-gray-200">{selectedTensor.std.toFixed(6)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Min Val:</span>
                      <span className="text-gray-200">{selectedTensor.min.toFixed(6)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Max Val:</span>
                      <span className="text-gray-200">{selectedTensor.max.toFixed(6)}</span>
                    </div>
                  </div>
                </div>

                {/* Coordinate Weight Sparkline */}
                <div className="flex flex-col gap-2">
                  <span className="text-gray-400 font-semibold text-[10px] uppercase">Embedding Coordinate Sparkline</span>
                  <div className="h-16 w-full bg-gray-950 border border-gray-800 rounded-xl overflow-hidden flex items-end px-1 gap-0.5">
                    {selectedTensor.vector.map((val, idx) => {
                      // Normalize val to a percentage height for demo sparkline
                      const abs = Math.abs(val)
                      const maxVal = Math.max(...selectedTensor.vector.map(Math.abs)) || 1.0
                      const height = `${(abs / maxVal) * 100}%`
                      const isPositive = val >= 0
                      
                      return (
                        <div
                          key={idx}
                          style={{ height }}
                          className={`flex-1 rounded-t-sm ${isPositive ? 'bg-indigo-500' : 'bg-purple-600'}`}
                          title={`Index ${idx}: ${val.toFixed(4)}`}
                        />
                      )
                    })}
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-20 text-center gap-3">
                <ShieldAlert className="h-8 w-8 text-gray-600" />
                <p className="text-xs text-gray-500 px-4">No tensor selected. Click on tokens in the Tokenizer or Embedding pages to inspect their coordinates!</p>
              </div>
            )}
          </div>

          {/* Quick Hardware Inspector at very bottom */}
          <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-3 text-xs flex flex-col gap-2">
            <span className="text-gray-400 font-semibold text-[10px] uppercase">Memory Overhead</span>
            <div className="flex justify-between font-mono text-[11px] text-gray-300">
              <span>Weights Memory:</span>
              <span>~{((stats?.total_params || 0) * 4 / (1024 * 1024)).toFixed(2)} MB</span>
            </div>
          </div>
        </aside>
      </div>

      {/* Floating Toast Notification Grid */}
      <div className="fixed bottom-6 right-6 flex flex-col gap-2 z-50">
        {toasts.map(t => (
          <div
            key={t.id}
            className={`px-4 py-3 rounded-xl shadow-lg border text-xs font-semibold flex items-center gap-2 min-w-64 backdrop-blur-xl animate-bounce ${
              t.type === 'success' ? 'bg-green-500/20 text-green-300 border-green-500/30' :
              t.type === 'error' ? 'bg-red-500/20 text-red-300 border-red-500/30' :
              'bg-indigo-500/20 text-indigo-300 border-indigo-500/30'
            }`}
          >
            <span>{t.msg}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ------------------------------------------------------------------------------------------------
// Sidebar Navigation Item Helper Component
// ------------------------------------------------------------------------------------------------
interface SidebarItemProps {
  icon: React.ReactNode
  label: string
  active: boolean
  onClick: () => void
}

function SidebarItem({ icon, label, active, onClick }: SidebarItemProps) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-xs font-medium transition-all duration-200 border ${
        active
          ? 'bg-indigo-500/10 text-indigo-400 border-indigo-500/25 shadow-inner'
          : 'text-gray-400 hover:text-gray-200 hover:bg-gray-900 border-transparent'
      }`}
    >
      {React.cloneElement(icon as React.ReactElement<any>, { className: 'h-4 w-4 shrink-0' })}
      <span>{label}</span>
    </button>
  )
}

// ------------------------------------------------------------------------------------------------
// VIEW: Dashboard View Component
// ------------------------------------------------------------------------------------------------
function DashboardView({ stats }: { stats: DashboardStats | null }) {
  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
          Model Dashboard
        </h2>
        <p className="text-xs text-gray-400 mt-1">High-level hyperparameters and real-time computation logs</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <StatCard title="Total Params" val={`${stats?.total_params?.toLocaleString() || 0}`} sub="Tied weights" />
        <StatCard title="Device" val={`${stats?.device || 'CPU'}`} sub="Compute hardware" />
        <StatCard title="Vocabulary Size" val={`${stats?.vocab_size || 0} tokens`} sub="Subword tokens" />
        <StatCard title="Embedding Dim (d_model)" val={`${stats?.embedding_dim || 0}`} sub="Vector width" />
        <StatCard title="Transformer Layers" val={`${stats?.num_layers || 0}`} sub="Blocks count" />
        <StatCard title="Attention Heads" val={`${stats?.num_heads || 0}`} sub="Self-attention partitions" />
      </div>

      <div className="glass-panel rounded-2xl p-6 flex flex-col gap-4">
        <h3 className="font-bold text-sm tracking-tight text-white">Model Architecture Layout Summary</h3>
        <div className="border border-gray-800 rounded-xl overflow-hidden text-xs">
          <div className="grid grid-cols-3 bg-gray-900/50 px-4 py-2 font-semibold text-gray-400 border-b border-gray-800">
            <span>Layer / Node Component</span>
            <span>Configuration</span>
            <span>Tensors Output Dims</span>
          </div>
          <div className="divide-y divide-gray-800">
            <div className="grid grid-cols-3 px-4 py-2.5 text-gray-300">
              <span className="font-bold text-indigo-400">Token Embedding</span>
              <span>Vocab: {stats?.vocab_size || 0} → Embedding: {stats?.embedding_dim || 0}</span>
              <span className="font-mono text-gray-400">[Batch, SeqLen, {stats?.embedding_dim || 0}]</span>
            </div>
            <div className="grid grid-cols-3 px-4 py-2.5 text-gray-300">
              <span className="font-bold text-indigo-400">Absolute Positional Encoding</span>
              <span>Sinusoidal (MaxContext: {stats?.context_len || 0})</span>
              <span className="font-mono text-gray-400">[Batch, SeqLen, {stats?.embedding_dim || 0}]</span>
            </div>
            <div className="grid grid-cols-3 px-4 py-2.5 text-gray-300">
              <span className="font-bold text-indigo-400">Stacked Transformer Blocks</span>
              <span>Pre-LayerNorm Stack ({stats?.num_layers || 0} blocks)</span>
              <span className="font-mono text-gray-400">[Batch, SeqLen, {stats?.embedding_dim || 0}]</span>
            </div>
            <div className="grid grid-cols-3 px-4 py-2.5 text-gray-300">
              <span className="font-bold text-indigo-400">Language Modeling Head</span>
              <span>Linear Tied Projection (Vocab: {stats?.vocab_size || 0})</span>
              <span className="font-mono text-gray-400">[Batch, SeqLen, {stats?.vocab_size || 0}]</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function StatCard({ title, val, sub }: { title: string; val: string; sub: string }) {
  return (
    <div className="glass-panel rounded-2xl p-5 border border-gray-800 flex flex-col gap-1.5 relative overflow-hidden">
      <div className="glow-pulse absolute -right-6 -bottom-6 w-16 h-16 rounded-full bg-indigo-500/10 blur-xl" />
      <span className="text-gray-400 font-semibold text-[10px] uppercase tracking-wider">{title}</span>
      <span className="text-xl font-bold tracking-tight text-white font-mono">{val}</span>
      <span className="text-[10px] text-gray-500 mt-1">{sub}</span>
    </div>
  )
}

// ------------------------------------------------------------------------------------------------
// VIEW: Tokenizer View Component
// ------------------------------------------------------------------------------------------------
function TokenizerView({ showToast, setSelectedTensor }: { showToast: any; setSelectedTensor: any }) {
  const [text, setText] = useState('unseen words like HuggingFace are tokenized as subwords.')
  const [tokens, setTokens] = useState<string[]>([])
  const [ids, setIds] = useState<number[]>([])

  const handleTokenize = async () => {
    try {
      const res = await api.tokenize(text)
      setTokens(res.tokens)
      setIds(res.ids)
      showToast('Text tokenized successfully.', 'success')
    } catch (err: any) {
      showToast(err.message || 'Tokenization failed.', 'error')
    }
  }

  // Load sample embedding stats if clicked
  const handleSelectToken = async (tok: string, id: number) => {
    try {
      const res = await api.getEmbedding(tok)
      if (res.embeddings && res.embeddings.length > 0) {
        const data = res.embeddings[0]
        setSelectedTensor({
          name: tok,
          id: id,
          shape: [1, res.shape[1]],
          vector: data.vector,
          mean: data.mean,
          std: data.std,
          min: data.min,
          max: data.max
        })
        showToast(`Token "${tok}" embeddings loaded in inspector.`, 'info')
      }
    } catch (err) {
      console.error(err)
    }
  }

  useEffect(() => {
    handleTokenize()
  }, [])

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-white">BPE Tokenizer Analysis</h2>
        <p className="text-xs text-gray-400 mt-1">Interactive byte pair encoding subword segmentation</p>
      </div>

      <div className="glass-panel rounded-2xl p-5 flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label className="text-gray-400 font-semibold text-[10px] uppercase">Input String Context</label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="w-full h-24 bg-gray-950/80 border border-gray-800 rounded-xl p-3 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none text-gray-200"
          />
        </div>
        <button
          onClick={handleTokenize}
          className="bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl py-2 px-4 text-xs font-semibold transition-all self-end flex items-center gap-1.5"
        >
          <ArrowRight className="h-4 w-4" />
          <span>Execute Tokenization</span>
        </button>
      </div>

      {/* Grid output */}
      <div className="grid grid-cols-2 gap-6">
        {/* Highlight splits */}
        <div className="glass-panel rounded-2xl p-5 flex flex-col gap-3">
          <h3 className="font-bold text-xs uppercase tracking-wider text-gray-400">Subwords Output Breakdown</h3>
          <div className="flex flex-wrap gap-1.5 bg-gray-950 p-4 rounded-xl min-h-24 border border-gray-900">
            {tokens.length === 0 ? (
              <span className="text-gray-500 text-xs">Enter text and execute to view...</span>
            ) : (
              tokens.map((tok, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSelectToken(tok, ids[idx])}
                  className="bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 border border-indigo-500/25 px-2.5 py-1 rounded-lg text-xs font-mono transition-all"
                  title="Click to inspect vector weights"
                >
                  {tok}
                </button>
              ))
            )}
          </div>
          <p className="text-[10px] text-gray-500 italic">Click on BPE tokens above to inspect their dimensions in the right side panel.</p>
        </div>

        {/* List mapping IDs */}
        <div className="glass-panel rounded-2xl p-5 flex flex-col gap-3">
          <h3 className="font-bold text-xs uppercase tracking-wider text-gray-400">Vocabulary Mapped ID List</h3>
          <div className="flex flex-wrap gap-1.5 bg-gray-950 p-4 rounded-xl min-h-24 border border-gray-900 font-mono text-xs">
            {ids.length === 0 ? (
              <span className="text-gray-500 text-xs">No tokens parsed...</span>
            ) : (
              ids.map((id, idx) => (
                <div key={idx} className="bg-gray-900 border border-gray-800 rounded px-2.5 py-1 text-gray-300 flex flex-col items-center">
                  <span className="text-[9px] text-gray-500">{tokens[idx]}</span>
                  <span className="font-bold text-indigo-400">{id}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------------------------------------
// VIEW: Vocabulary Explorer View Component
// ------------------------------------------------------------------------------------------------
function VocabView({ showToast }: { showToast: any }) {
  const [vocab, setVocab] = useState<{ id: number; token: string }[]>([])
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)
  const itemsPerPage = 12

  const fetchVocab = async () => {
    try {
      const res = await api.getVocabulary()
      setVocab(res.vocabulary)
    } catch (err: any) {
      showToast('Could not load vocabulary.', 'error')
    }
  }

  useEffect(() => {
    fetchVocab()
  }, [])

  const filtered = vocab.filter(item =>
    item.token.toLowerCase().includes(search.toLowerCase()) ||
    item.id.toString() === search
  )

  const maxPages = Math.ceil(filtered.length / itemsPerPage)
  const paginated = filtered.slice(page * itemsPerPage, (page + 1) * itemsPerPage)

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-white">Vocabulary Explorer</h2>
        <p className="text-xs text-gray-400 mt-1">Explore all learned subwords and special markers inside the token dictionary</p>
      </div>

      <div className="flex gap-4">
        {/* Search box */}
        <div className="flex-1 glass-panel px-4 py-2.5 rounded-xl border border-gray-800 flex items-center gap-2">
          <Search className="h-4 w-4 text-gray-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setPage(0)
            }}
            placeholder="Search BPE subword or ID index..."
            className="flex-1 bg-transparent text-xs text-gray-200 outline-none"
          />
        </div>
        <button
          onClick={fetchVocab}
          className="bg-gray-900 border border-gray-800 hover:bg-gray-800 text-gray-300 p-2.5 rounded-xl text-xs flex items-center justify-center transition-all"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      <div className="glass-panel rounded-2xl overflow-hidden border border-gray-800 text-xs">
        <div className="grid grid-cols-3 bg-gray-950 border-b border-gray-800 px-6 py-3 font-semibold text-gray-400 uppercase tracking-wider text-[10px]">
          <span>Token Index</span>
          <span>BPE Subword String</span>
          <span>Byte Representation</span>
        </div>
        <div className="divide-y divide-gray-900">
          {paginated.length === 0 ? (
            <div className="px-6 py-10 text-center text-gray-500">No matching vocabulary tokens found.</div>
          ) : (
            paginated.map((item) => (
              <div key={item.id} className="grid grid-cols-3 px-6 py-3 items-center text-gray-200 font-mono">
                <span className="font-bold text-indigo-400">{item.id}</span>
                <span className="bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 px-2 py-0.5 rounded-lg w-max text-xs">{item.token}</span>
                <span className="text-gray-400">{JSON.stringify(item.token)}</span>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Pagination controls */}
      {maxPages > 1 && (
        <div className="flex justify-between items-center text-xs text-gray-400 mt-2 px-1">
          <span>Showing {page * itemsPerPage + 1} - {Math.min((page + 1) * itemsPerPage, filtered.length)} of {filtered.length} entries</span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-3 py-1 bg-gray-900 border border-gray-800 rounded-lg hover:bg-gray-800 disabled:opacity-40 transition-all font-semibold"
            >
              Previous
            </button>
            <button
              onClick={() => setPage(p => Math.min(maxPages - 1, p + 1))}
              disabled={page === maxPages - 1}
              className="px-3 py-1 bg-gray-900 border border-gray-800 rounded-lg hover:bg-gray-800 disabled:opacity-40 transition-all font-semibold"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ------------------------------------------------------------------------------------------------
// VIEW: Dataset Viewer Component
// ------------------------------------------------------------------------------------------------
function DatasetView({ showToast }: { showToast: any }) {
  const [text, setText] = useState('the cat sat on the mat. building a model requires a dataset.')
  const [seqLen, setSeqLen] = useState(8)
  const [samples, setSamples] = useState<any[]>([])

  const fetchDataset = async () => {
    try {
      const res = await api.getDataset(text, seqLen)
      setSamples(res.samples)
      showToast('Causal training pairs loaded.', 'success')
    } catch (err: any) {
      showToast('Failed to load dataset sequence trace.', 'error')
    }
  }

  useEffect(() => {
    fetchDataset()
  }, [])

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-white">Dataset & DataLoader Inspector</h2>
        <p className="text-xs text-gray-400 mt-1">Visualize causal training sequence alignment: input $X \rightarrow$ target $Y$ (shifted 1 step)</p>
      </div>

      <div className="glass-panel rounded-2xl p-5 flex flex-col gap-4">
        <div className="grid grid-cols-3 gap-4">
          <div className="col-span-2 flex flex-col gap-1.5">
            <label className="text-gray-400 font-semibold text-[10px] uppercase">Corpus Mock Context</label>
            <input
              type="text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none text-gray-200"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-gray-400 font-semibold text-[10px] uppercase">Sequence Length</label>
            <input
              type="number"
              value={seqLen}
              onChange={(e) => setSeqLen(parseInt(e.target.value) || 8)}
              className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none text-gray-200"
            />
          </div>
        </div>
        <button
          onClick={fetchDataset}
          className="bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl py-2 px-4 text-xs font-semibold transition-all self-end"
        >
          Generate DataLoader Samples
        </button>
      </div>

      <div className="flex flex-col gap-4">
        {samples.length === 0 ? (
          <div className="glass-panel p-10 text-center text-gray-500 text-xs rounded-2xl">Execute dataset trace generator...</div>
        ) : (
          samples.map((s, sIdx) => (
            <div key={sIdx} className="glass-panel rounded-2xl p-5 flex flex-col gap-4">
              <span className="font-bold text-xs uppercase tracking-wider text-indigo-400">Sample Segment {s.index + 1}</span>
              
              <div className="flex flex-col gap-3 font-mono text-xs">
                {/* Inputs Row */}
                <div className="flex flex-col gap-1.5">
                  <span className="text-gray-500 text-[10px]">INPUT SEQUENCE (X)</span>
                  <div className="flex flex-wrap gap-1.5 bg-gray-950 p-3 rounded-xl border border-gray-900">
                    {s.input_tokens.map((tok: string, idx: number) => (
                      <div key={idx} className="bg-gray-900 border border-gray-800 rounded px-2 py-1 text-gray-300">
                        <div className="text-[9px] text-gray-500">{s.input_ids[idx]}</div>
                        <div className="font-bold text-indigo-300">{tok}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Targets Row */}
                <div className="flex flex-col gap-1.5">
                  <span className="text-gray-500 text-[10px]">CAUSAL TARGET ALIGNMENT (Y)</span>
                  <div className="flex flex-wrap gap-1.5 bg-purple-950/20 p-3 rounded-xl border border-purple-500/10">
                    {s.target_tokens.map((tok: string, idx: number) => (
                      <div key={idx} className="bg-purple-950/30 border border-purple-500/20 rounded px-2 py-1 text-gray-300">
                        <div className="text-[9px] text-purple-400/40">{s.target_ids[idx]}</div>
                        <div className="font-bold text-purple-300">{tok}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

// ------------------------------------------------------------------------------------------------
// VIEW: Embedding Viewer Component
// ------------------------------------------------------------------------------------------------
function EmbeddingView({ showToast, setSelectedTensor }: { showToast: any; setSelectedTensor: any }) {
  const [text, setText] = useState('transformers learn representations')
  const [embeddingData, setEmbeddingData] = useState<any[]>([])
  const [shape, setShape] = useState<number[]>([0, 0])

  const fetchEmbedding = async () => {
    try {
      const res = await api.getEmbedding(text)
      setEmbeddingData(res.embeddings)
      setShape(res.shape)
      showToast('Embedding matrix projections calculated.', 'success')
    } catch (err: any) {
      showToast('Embedding trace computation failed.', 'error')
    }
  }

  useEffect(() => {
    fetchEmbedding()
  }, [])

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-white">Embedding Layer Viewer</h2>
        <p className="text-xs text-gray-400 mt-1">Inspect spatial coordinate statistics and vector weights of token embedding maps</p>
      </div>

      <div className="glass-panel rounded-2xl p-5 flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label className="text-gray-400 font-semibold text-[10px] uppercase">Input String</label>
          <input
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none text-gray-200"
          />
        </div>
        <button
          onClick={fetchEmbedding}
          className="bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl py-2 px-4 text-xs font-semibold transition-all self-end"
        >
          Compute Vectors
        </button>
      </div>

      <div className="glass-panel rounded-2xl p-5 flex flex-col gap-4">
        <div className="flex justify-between items-center">
          <h3 className="font-bold text-xs uppercase tracking-wider text-gray-400">Embedding Layer output shape: <span className="text-indigo-400 font-mono">[{shape.join(', ')}]</span></h3>
        </div>

        <div className="flex flex-col gap-3">
          {embeddingData.map((data, idx) => (
            <div
              key={idx}
              onClick={() => setSelectedTensor({
                name: data.token,
                id: data.id,
                shape: [1, shape[1]],
                vector: data.vector,
                mean: data.mean,
                std: data.std,
                min: data.min,
                max: data.max
              })}
              className="bg-gray-900 border border-gray-800 hover:border-indigo-500/50 rounded-xl p-4 flex justify-between items-center cursor-pointer transition-all hover:bg-gray-900/80"
              title="Click to view full stats in the inspector"
            >
              <div className="flex items-center gap-3">
                <span className="h-6 w-6 rounded bg-indigo-500/10 border border-indigo-500/25 flex items-center justify-center text-[10px] text-indigo-300 font-mono">{data.id}</span>
                <span className="font-bold text-xs text-white">"{data.token}"</span>
              </div>

              {/* Coordinates spark grid */}
              <div className="flex gap-0.5 h-6 w-36 items-center px-1 bg-gray-950/80 border border-gray-900 rounded-lg">
                {data.vector.slice(0, 16).map((val: number, vIdx: number) => {
                  const maxVal = Math.max(...data.vector.map(Math.abs)) || 1.0
                  const height = `${Math.min(100, (Math.abs(val) / maxVal) * 100)}%`
                  const isPositive = val >= 0
                  return (
                    <div
                      key={vIdx}
                      style={{ height }}
                      className={`flex-1 rounded-sm ${isPositive ? 'bg-indigo-500' : 'bg-purple-600'}`}
                    />
                  )
                })}
              </div>

              <div className="flex gap-4 font-mono text-[10px] text-gray-400">
                <span>Mean: <span className="text-gray-200">{data.mean.toFixed(4)}</span></span>
                <span>Std: <span className="text-gray-200">{data.std.toFixed(4)}</span></span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------------------------------------
// VIEW: Positional Encoding Viewer Component
// ------------------------------------------------------------------------------------------------
function PositionalView({ showToast }: { showToast: any }) {
  const [seqLen, setSeqLen] = useState(16)
  const [embedDim, setEmbedDim] = useState(16)
  const [seqLenInput, setSeqLenInput] = useState('16')
  const [embedDimInput, setEmbedDimInput] = useState('16')
  const [isSaving, setIsSaving] = useState(false)
  
  useEffect(() => {
    let active = true
    const loadConfig = async () => {
      try {
        const config = await api.getModelConfig()
        if (active) {
          setSeqLen(config.max_sequence_length)
          setEmbedDim(config.embedding_dimension)
          setSeqLenInput(config.max_sequence_length.toString())
          setEmbedDimInput(config.embedding_dimension.toString())
        }
      } catch (err: any) {
        showToast(err.message || 'Failed to fetch model configuration', 'error')
      }
    }
    loadConfig()
    return () => {
      active = false
    }
  }, [])

  // Validation checks
  const parsedSeqLen = parseInt(seqLenInput, 10)
  const isSeqLenValid = !isNaN(parsedSeqLen) && parsedSeqLen >= 16 && parsedSeqLen <= 4096
  const seqLenError = seqLenInput && !isSeqLenValid
    ? 'Sequence Context must be an integer between 16 and 4096.'
    : ''

  const parsedEmbedDim = parseInt(embedDimInput, 10)
  const isEmbedDimValid = !isNaN(parsedEmbedDim) && parsedEmbedDim >= 16 && parsedEmbedDim <= 1024
  const embedDimError = embedDimInput && !isEmbedDimValid
    ? 'Embedding Dimension must be an integer between 16 and 1024.'
    : ''

  const isFormValid = isSeqLenValid && isEmbedDimValid

  const handleSave = async () => {
    if (!isFormValid) return
    setIsSaving(true)
    try {
      const res = await api.saveModelConfig({
        max_sequence_length: parsedSeqLen,
        embedding_dimension: parsedEmbedDim
      })
      showToast(res.message || 'Configuration saved successfully.', 'success')
      setSeqLen(parsedSeqLen)
      setEmbedDim(parsedEmbedDim)
    } catch (err: any) {
      showToast(err.message || 'Failed to save configuration.', 'error')
    } finally {
      setIsSaving(false)
    }
  }

  const handleReset = async () => {
    setIsSaving(true)
    try {
      await api.saveModelConfig({
        max_sequence_length: 16,
        embedding_dimension: 16
      })
      showToast('Configuration reset to defaults successfully.', 'success')
      setSeqLen(16)
      setEmbedDim(16)
      setSeqLenInput('16')
      setEmbedDimInput('16')
    } catch (err: any) {
      showToast(err.message || 'Failed to reset configuration.', 'error')
    } finally {
      setIsSaving(false)
    }
  }

  // Cap visual heatmap dimensions for rendering performance (up to 64x64)
  const displaySeqLen = Math.min(seqLen, 64)
  const displayEmbedDim = Math.min(embedDim, 64)

  // Custom manual calculation of Sinusoidal Positional Encoding values
  const getPE = () => {
    const pe: number[][] = []
    for (let pos = 0; pos < displaySeqLen; pos++) {
      const row: number[] = []
      for (let i = 0; i < displayEmbedDim; i++) {
        // formula: pos / (10000 ^ (2i/d_model))
        const div = Math.pow(10000.0, (2.0 * Math.floor(i / 2)) / displayEmbedDim)
        const angle = pos / div
        const val = i % 2 === 0 ? Math.sin(angle) : Math.cos(angle)
        row.push(val)
      }
      pe.push(row)
    }
    return pe
  }

  const peMatrix = getPE()

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-white">Positional Encoding Visualizer</h2>
        <p className="text-xs text-gray-400 mt-1">Inspect the Sinusoidal Positional waves pattern that provides order context to the model</p>
      </div>

      <div className="glass-panel rounded-2xl p-5 flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-gray-400 font-semibold text-[10px] uppercase">Sequence Positions Context (Max)</label>
            <input
              type="number"
              value={seqLenInput}
              onChange={(e) => setSeqLenInput(e.target.value)}
              className={`bg-gray-950 border rounded-xl px-3 py-2 text-xs focus:ring-1 focus:outline-none text-gray-200 ${
                seqLenError ? 'border-red-500/50 focus:ring-red-500' : 'border-gray-800 focus:ring-indigo-500'
              }`}
              placeholder="e.g. 16"
            />
            {seqLenError && <span className="text-[10px] text-red-500 mt-0.5">{seqLenError}</span>}
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-gray-400 font-semibold text-[10px] uppercase">Embedding Dimension (Width)</label>
            <input
              type="number"
              value={embedDimInput}
              onChange={(e) => setEmbedDimInput(e.target.value)}
              className={`bg-gray-950 border rounded-xl px-3 py-2 text-xs focus:ring-1 focus:outline-none text-gray-200 ${
                embedDimError ? 'border-red-500/50 focus:ring-red-500' : 'border-gray-800 focus:ring-indigo-500'
              }`}
              placeholder="e.g. 16"
            />
            {embedDimError && <span className="text-[10px] text-red-500 mt-0.5">{embedDimError}</span>}
          </div>
        </div>

        <div className="flex gap-3 justify-end mt-2">
          <button
            onClick={handleReset}
            disabled={isSaving}
            className="px-4 py-2 rounded-xl border border-gray-800 text-xs font-semibold text-gray-400 hover:bg-gray-900/50 hover:text-white transition disabled:opacity-50"
          >
            Reset to Default
          </button>
          <button
            onClick={handleSave}
            disabled={!isFormValid || isSaving}
            className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white transition disabled:opacity-50 disabled:hover:bg-indigo-600"
          >
            {isSaving ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>
      </div>

      <div className="glass-panel rounded-2xl p-6 flex flex-col gap-4">
        <h3 className="font-bold text-xs uppercase tracking-wider text-gray-400 flex items-center gap-2">
          <span>Sinusoidal PE Heatmap Grid: <span className="font-mono text-indigo-400">[{seqLen}, {embedDim}]</span></span>
          {(seqLen > 64 || embedDim > 64) && (
            <span className="text-[10px] text-yellow-500/80 font-normal normal-case">
              (Showing first {displaySeqLen}x{displayEmbedDim} elements for performance)
            </span>
          )}
        </h3>

        {/* Heatmap matrix container */}
        <div className="flex flex-col gap-1 overflow-x-auto p-2 bg-gray-950 border border-gray-900 rounded-xl">
          {peMatrix.map((row, posIdx) => (
            <div key={posIdx} className="flex gap-1 items-center shrink-0">
              <span className="w-12 text-[10px] font-mono text-gray-500 text-right pr-2">Pos {posIdx}</span>
              {row.map((val, dimIdx) => {
                const opacity = Math.abs(val)
                const isPositive = val >= 0
                return (
                  <div
                    key={dimIdx}
                    style={{ opacity: 0.2 + 0.8 * opacity }}
                    className={`h-6 w-6 rounded-sm flex items-center justify-center text-[8px] font-mono text-white ${
                      isPositive ? 'bg-indigo-500' : 'bg-purple-600'
                    }`}
                    title={`Pos ${posIdx}, Dim ${dimIdx}: ${val.toFixed(4)}`}
                  >
                    {val.toFixed(1)}
                  </div>
                )
              })}
            </div>
          ))}
        </div>
        <div className="flex justify-between text-[10px] text-gray-500 px-1 mt-1">
          <span>Even dimensions (0, 2, 4...) are Sin waves</span>
          <span>Odd dimensions (1, 3, 5...) are Cos waves</span>
        </div>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------------------------------------
// VIEW: Attention Viewer Component
// ------------------------------------------------------------------------------------------------
function AttentionView({ showToast }: { showToast: any }) {
  const [text, setText] = useState('the cat sat on the mat.')
  const [tokens, setTokens] = useState<string[]>([])
  const [attentionWeights, setAttentionWeights] = useState<number[][][]>([]) // [head, seq_len, seq_len]
  const [selectedHead, setSelectedHead] = useState(0)

  const fetchAttention = async () => {
    try {
      const res = await api.getAttention(text)
      setTokens(res.tokens)
      setAttentionWeights(res.attention_weights)
      showToast('Attention weight matrices computed.', 'success')
    } catch (err: any) {
      showToast('Attention weights query failed.', 'error')
    }
  }

  useEffect(() => {
    fetchAttention()
  }, [])

  const matrix = attentionWeights[selectedHead] || []

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-white">Attention Matrix Visualizer</h2>
        <p className="text-xs text-gray-400 mt-1">Investigate causal self-attention weights showing where each token "attends" in the context</p>
      </div>

      <div className="glass-panel rounded-2xl p-5 flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label className="text-gray-400 font-semibold text-[10px] uppercase">Input Prompt</label>
          <input
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none text-gray-200"
          />
        </div>
        <div className="flex justify-between items-center">
          <div className="flex gap-2">
            {attentionWeights.map((_, hIdx) => (
              <button
                key={hIdx}
                onClick={() => setSelectedHead(hIdx)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border ${
                  selectedHead === hIdx
                    ? 'bg-indigo-500/10 border-indigo-500/25 text-indigo-400'
                    : 'bg-gray-900 border-gray-800 text-gray-400 hover:text-gray-200'
                }`}
              >
                Head {hIdx + 1}
              </button>
            ))}
          </div>
          <button
            onClick={fetchAttention}
            className="bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl py-2 px-4 text-xs font-semibold transition-all"
          >
            Compute Matrix
          </button>
        </div>
      </div>

      {matrix.length > 0 && (
        <div className="glass-panel rounded-2xl p-6 flex flex-col gap-5 overflow-hidden">
          <h3 className="font-bold text-xs uppercase tracking-wider text-gray-400">Head {selectedHead + 1} Weight Heatmap Grid</h3>
          
          <div className="overflow-x-auto p-4 bg-gray-950 border border-gray-900 rounded-xl flex flex-col gap-1 min-w-[300px]">
            {/* Headers row */}
            <div className="flex gap-1 shrink-0 mb-1">
              <div className="w-14" />
              {tokens.map((tok, tIdx) => (
                <div key={tIdx} className="w-10 text-[9px] font-mono text-gray-500 text-center truncate" title={tok}>
                  {tok}
                </div>
              ))}
            </div>

            {matrix.map((row, rIdx) => (
              <div key={rIdx} className="flex gap-1 items-center shrink-0">
                <span className="w-14 text-[9px] font-mono text-gray-500 text-right pr-2 truncate" title={tokens[rIdx]}>
                  {tokens[rIdx]}
                </span>
                {row.map((val, cIdx) => {
                  // Causal attention is lower triangular. Upper triangular values should be ~0.0
                  const isUpper = cIdx > rIdx
                  return (
                    <div
                      key={cIdx}
                      style={{ opacity: isUpper ? 0.05 : 0.1 + 0.9 * val }}
                      className={`h-10 w-10 rounded border border-gray-900/50 flex flex-col items-center justify-center text-[8px] font-mono font-bold text-white transition-all hover:scale-105 ${
                        isUpper ? 'bg-gray-800' : 'bg-indigo-500'
                      }`}
                      title={`${tokens[rIdx]} -> ${tokens[cIdx]}: ${val.toFixed(4)}`}
                    >
                      {isUpper ? '-' : val.toFixed(2)}
                    </div>
                  )
                })}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ------------------------------------------------------------------------------------------------
// VIEW: Transformer View Component
// ------------------------------------------------------------------------------------------------
function TransformerView({ stats }: { stats: DashboardStats | null }) {
  const blocks = Array.from({ length: stats?.num_layers || 2 }, (_, i) => i + 1)
  
  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-white">Transformer Architecture Stack</h2>
        <p className="text-xs text-gray-400 mt-1">Structural visualization of the Pre-LayerNorm GPT Decoder flow</p>
      </div>

      <div className="flex flex-col items-center gap-4 py-8 bg-gray-950/40 border border-gray-800/80 rounded-2xl relative overflow-hidden">
        
        {/* Input tokens node */}
        <BlockNode label="Input Sequence IDs" shape="[BatchSize, SeqLen]" desc="Token integers lookup" color="border-gray-700 bg-gray-900 text-gray-300" />
        <ArrowDown />

        {/* Embedding nodes */}
        <div className="flex gap-4">
          <BlockNode label="Token Embedding" shape="[BatchSize, SeqLen, EmbeddingDim]" desc="Word coordinates lookup" color="border-indigo-500/30 bg-indigo-500/10 text-indigo-300" />
          <BlockNode label="Positional Encoding" shape="[BatchSize, SeqLen, EmbeddingDim]" desc="Sin/Cos order constants" color="border-purple-500/30 bg-purple-500/10 text-purple-300" />
        </div>
        <ArrowDown />

        {/* Embedding merge */}
        <BlockNode label="(+) Element-wise Addition" shape="[BatchSize, SeqLen, EmbeddingDim]" desc="Embedding representation stream" color="border-gray-800 bg-gray-900/50" />
        <ArrowDown />

        {/* Stacks of blocks */}
        {blocks.map((blockIdx) => (
          <React.Fragment key={blockIdx}>
            <div className="border border-indigo-500/25 bg-indigo-500/5 p-6 rounded-2xl flex flex-col items-center gap-3 w-80 relative">
              <span className="absolute -top-3 left-4 bg-indigo-500 text-white font-bold text-[9px] uppercase px-2 py-0.5 rounded-full">
                Transformer Block {blockIdx}
              </span>
              
              <BlockNode label="Pre-LN 1" shape="Channel mean/var" desc="Normalize before Attention" color="border-gray-800 bg-gray-950/50" />
              <ArrowDown />
              <BlockNode label="Multi-Head Self-Attention" shape="[BatchSize, SeqLen, EmbeddingDim]" desc="Causal masked query projection" color="border-indigo-500/20 bg-indigo-500/5" />
              <ArrowDown />
              <BlockNode label="(+) Residual Connection 1" shape="Add attention outputs to inputs" desc="Clean gradient shortcut" color="border-gray-800 bg-gray-950/50" />
              <ArrowDown />
              <BlockNode label="Pre-LN 2" shape="Channel mean/var" desc="Normalize before FFN" color="border-gray-800 bg-gray-950/50" />
              <ArrowDown />
              <BlockNode label="Position-wise FFN" shape="Expansion (4x d_model) → GELU" desc="Compute facts & mapping features" color="border-purple-500/20 bg-purple-500/5" />
              <ArrowDown />
              <BlockNode label="(+) Residual Connection 2" shape="Add FFN outputs to inputs" desc="Update final representations" color="border-gray-800 bg-gray-950/50" />
            </div>
            <ArrowDown />
          </React.Fragment>
        ))}

        {/* Final output nodes */}
        <BlockNode label="Final Pre-Head LayerNorm" shape="Channel normalizer" desc="Prep vectors for projection" color="border-gray-800 bg-gray-900/50" />
        <ArrowDown />
        
        <BlockNode label="Language Modeling Head" shape="[BatchSize, SeqLen, VocabSize]" desc="Linear projection output logits" color="border-emerald-500/30 bg-emerald-500/10 text-emerald-300" />
      </div>
    </div>
  )
}

function BlockNode({ label, shape, desc, color }: { label: string; shape: string; desc: string; color: string }) {
  return (
    <div className={`border rounded-xl p-3 text-xs w-64 text-center ${color}`}>
      <span className="font-bold block text-white">{label}</span>
      <span className="text-[10px] font-mono block text-gray-400 mt-1">{shape}</span>
      <span className="text-[9px] block text-gray-500 italic mt-0.5">{desc}</span>
    </div>
  )
}

function ArrowDown() {
  return (
    <div className="h-6 w-0.5 bg-gray-800 relative">
      <div className="absolute -bottom-1 -left-1 border-t-4 border-t-gray-800 border-x-4 border-x-transparent" />
    </div>
  )
}

// ------------------------------------------------------------------------------------------------
// VIEW: Training View Component
// ------------------------------------------------------------------------------------------------
interface TrainingViewProps {
  losses: LossData[]
  valLosses: ValLossData[]
  settings: SystemSettings | null
  isTraining: boolean
  showToast: any
}

function TrainingView({ losses, valLosses, settings, isTraining, showToast }: TrainingViewProps) {
  // Config overrides
  const [lr, setLr] = useState(0.001)
  const [epochs, setEpochs] = useState(5)
  const [batchSize, setBatchSize] = useState(4)

  useEffect(() => {
    if (settings) {
      setLr(settings.learning_rate)
      setEpochs(settings.epochs)
      setBatchSize(settings.batch_size)
    }
  }, [settings])

  const handleStart = async () => {
    try {
      const res = await api.startTraining({
        learning_rate: lr,
        epochs: epochs,
        batch_size: batchSize
      })
      if (res.success) {
        showToast('Training session triggered in background.', 'success')
      } else {
        showToast(res.message, 'error')
      }
    } catch (err: any) {
      showToast('Could not start training.', 'error')
    }
  }

  const handleStop = async () => {
    try {
      const res = await api.stopTraining()
      if (res.success) {
        showToast('Stop request dispatched.', 'info')
      }
    } catch (err: any) {
      showToast('Stop command failed.', 'error')
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            Model Training Center
          </h2>
          <p className="text-xs text-gray-400 mt-1">Start background SGD training and monitor loss optimization curves</p>
        </div>
        
        {/* Play/Stop controls */}
        <div className="flex gap-3">
          {isTraining ? (
            <button
              onClick={handleStop}
              className="bg-red-600 hover:bg-red-500 text-white rounded-xl py-2 px-4 text-xs font-semibold flex items-center gap-1.5 transition-all"
            >
              <Square className="h-4 w-4" />
              <span>Halt Training</span>
            </button>
          ) : (
            <button
              onClick={handleStart}
              className="bg-green-600 hover:bg-green-500 text-white rounded-xl py-2 px-4 text-xs font-semibold flex items-center gap-1.5 transition-all"
            >
              <Play className="h-4 w-4" />
              <span>Initiate Training</span>
            </button>
          )}
        </div>
      </div>

      {/* Basic overrides */}
      {!isTraining && (
        <div className="glass-panel rounded-2xl p-5 grid grid-cols-3 gap-4 text-xs">
          <div className="flex flex-col gap-1.5">
            <label className="text-gray-400 font-semibold text-[10px] uppercase">Learning Rate</label>
            <input
              type="number"
              step="0.0001"
              value={lr}
              onChange={(e) => setLr(parseFloat(e.target.value) || 0.001)}
              className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none text-gray-200"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-gray-400 font-semibold text-[10px] uppercase">Batch Size</label>
            <input
              type="number"
              value={batchSize}
              onChange={(e) => setBatchSize(parseInt(e.target.value) || 4)}
              className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none text-gray-200"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-gray-400 font-semibold text-[10px] uppercase">Epochs</label>
            <input
              type="number"
              value={epochs}
              onChange={(e) => setEpochs(parseInt(e.target.value) || 5)}
              className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none text-gray-200"
            />
          </div>
        </div>
      )}

      {/* Loss Plot */}
      <div className="glass-panel rounded-2xl p-6 flex flex-col gap-4">
        <h3 className="font-bold text-xs uppercase tracking-wider text-gray-400">Step Loss Optimization Curve</h3>
        
        <div className="h-64 w-full bg-gray-950/60 p-2 rounded-xl border border-gray-900">
          {losses.length === 0 ? (
            <div className="h-full w-full flex items-center justify-center text-gray-500 text-xs">No metrics recorded yet. Trigger training above.</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={losses}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="step" stroke="#9ca3af" fontSize={10} />
                <YAxis stroke="#9ca3af" fontSize={10} domain={['auto', 'auto']} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: 8, fontSize: 11 }}
                  labelStyle={{ color: '#9ca3af' }}
                />
                <Line type="monotone" dataKey="loss" stroke="#6366f1" strokeWidth={1.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Validation Epoch list */}
      <div className="glass-panel rounded-2xl p-5 flex flex-col gap-3">
        <h3 className="font-bold text-xs uppercase tracking-wider text-gray-400">Validation Loss History</h3>
        {valLosses.length === 0 ? (
          <span className="text-gray-500 text-xs italic px-1">No validation metrics complete. Val evaluations execute at the end of each training epoch.</span>
        ) : (
          <div className="flex gap-3 overflow-x-auto py-1">
            {valLosses.map((val, idx) => (
              <div key={idx} className="bg-gray-900 border border-gray-800 rounded-xl p-3 font-mono text-xs flex flex-col items-center min-w-32 shrink-0">
                <span className="text-[10px] text-gray-500">EPOCH {val.epoch}</span>
                <span className="text-lg font-bold text-indigo-400">{val.loss.toFixed(4)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ------------------------------------------------------------------------------------------------
// VIEW: Inference Playground Viewer Component
// ------------------------------------------------------------------------------------------------
function PlaygroundView({ showToast }: { showToast: any }) {
  const [prompt, setPrompt] = useState('the cat sat')
  const [maxTokens, setMaxTokens] = useState(30)
  const [temp, setTemp] = useState(1.0)
  const [topK, setTopK] = useState(0)
  const [topP, setTopP] = useState(0.0)

  const [output, setOutput] = useState('')
  const [loading, setLoading] = useState(false)

  const handleGenerate = async () => {
    setLoading(true)
    try {
      const res = await api.generate(prompt, maxTokens, temp, topK, topP)
      setOutput(res.generated_text)
      showToast('Sequence generated successfully.', 'success')
    } catch (err: any) {
      showToast(err.message || 'Generation failed.', 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-white">Inference Playground</h2>
        <p className="text-xs text-gray-400 mt-1">Prompt the model and inspect autoregressive output text token projections</p>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Configuration inputs */}
        <div className="glass-panel rounded-2xl p-5 flex flex-col gap-4 text-xs h-max">
          <h3 className="font-bold text-xs uppercase tracking-wider text-gray-400 border-b border-gray-800 pb-2">Generation Config</h3>
          
          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between font-semibold">
              <span className="text-gray-400 text-[10px] uppercase">Temperature ({temp.toFixed(1)})</span>
            </div>
            <input
              type="range"
              min="0.0"
              max="2.0"
              step="0.1"
              value={temp}
              onChange={(e) => setTemp(parseFloat(e.target.value))}
              className="accent-indigo-500 h-1.5 bg-gray-800 rounded-lg appearance-none cursor-pointer"
            />
            <span className="text-[9px] text-gray-500 italic">0.0 = greedy, 1.0 = standard, &gt;1.0 = creative</span>
          </div>

          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between font-semibold">
              <span className="text-gray-400 text-[10px] uppercase">Top-K ({topK})</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              step="1"
              value={topK}
              onChange={(e) => setTopK(parseInt(e.target.value))}
              className="accent-indigo-500 h-1.5 bg-gray-800 rounded-lg appearance-none cursor-pointer"
            />
            <span className="text-[9px] text-gray-500 italic">Filters tokens to only the top K selections (0 is disabled)</span>
          </div>

          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between font-semibold">
              <span className="text-gray-400 text-[10px] uppercase">Top-P ({topP.toFixed(2)})</span>
            </div>
            <input
              type="range"
              min="0.00"
              max="0.99"
              step="0.05"
              value={topP}
              onChange={(e) => setTopP(parseFloat(e.target.value))}
              className="accent-indigo-500 h-1.5 bg-gray-800 rounded-lg appearance-none cursor-pointer"
            />
            <span className="text-[9px] text-gray-500 italic">Nucleus threshold filters cumulative probability (0.0 is disabled)</span>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-gray-400 font-semibold text-[10px] uppercase">Max Tokens</label>
            <input
              type="number"
              value={maxTokens}
              onChange={(e) => setMaxTokens(parseInt(e.target.value) || 30)}
              className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none text-gray-200"
            />
          </div>
        </div>

        {/* IO Playground panel */}
        <div className="col-span-2 flex flex-col gap-4">
          <div className="glass-panel rounded-2xl p-5 flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-gray-400 font-semibold text-[10px] uppercase">Input Prompt Context</label>
              <input
                type="text"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Enter prompt starting tokens..."
                className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none text-gray-200"
              />
            </div>
            <button
              onClick={handleGenerate}
              disabled={loading}
              className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white rounded-xl py-2 px-4 text-xs font-semibold transition-all self-end"
            >
              {loading ? 'Model thinking...' : 'Generate Text'}
            </button>
          </div>

          {/* Outputs */}
          <div className="glass-panel rounded-2xl p-5 flex flex-col gap-3 flex-1 min-h-[160px]">
            <h3 className="font-bold text-xs uppercase tracking-wider text-gray-400">Generated Output Result</h3>
            <div className="bg-gray-950 p-4 rounded-xl text-xs font-mono border border-gray-900 min-h-24 whitespace-pre-wrap text-indigo-200 leading-6">
              {output === '' ? (
                <span className="text-gray-600">Generated sequence text will appear here...</span>
              ) : (
                output
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------------------------------------
// VIEW: Checkpoints View Component
// ------------------------------------------------------------------------------------------------
function CheckpointsView({ showToast }: { showToast: any }) {
  const [checkpoints, setCheckpoints] = useState<any[]>([])

  const fetchCheckpoints = async () => {
    try {
      const res = await api.getCheckpoints()
      setCheckpoints(res.checkpoints)
    } catch (err: any) {
      showToast('Could not query checkpoints list.', 'error')
    }
  }

  useEffect(() => {
    fetchCheckpoints()
  }, [])

  const handleLoad = async (filename: string) => {
    try {
      const res = await api.loadCheckpoint(filename)
      if (res.success) {
        showToast(res.message, 'success')
      }
    } catch (err: any) {
      showToast(err.message || 'Loading checkpoint failed.', 'error')
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white">Saved Model Checkpoints</h2>
          <p className="text-xs text-gray-400 mt-1">Review, restore, and test saved weight snapshots</p>
        </div>
        <button
          onClick={fetchCheckpoints}
          className="bg-gray-900 border border-gray-800 hover:bg-gray-800 text-gray-300 p-2.5 rounded-xl text-xs transition-all"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      <div className="glass-panel rounded-2xl overflow-hidden border border-gray-800 text-xs">
        <div className="grid grid-cols-5 bg-gray-950 border-b border-gray-800 px-6 py-3 font-semibold text-gray-400 uppercase tracking-wider text-[10px]">
          <span>File Name</span>
          <span>Epoch Completed</span>
          <span>Val Loss</span>
          <span>File Size</span>
          <span className="text-right">Action</span>
        </div>
        <div className="divide-y divide-gray-900 font-mono">
          {checkpoints.length === 0 ? (
            <div className="px-6 py-10 text-center text-gray-500">No saved checkpoint configurations found in checkpoints/ directory.</div>
          ) : (
            checkpoints.map((c, idx) => (
              <div key={idx} className="grid grid-cols-5 px-6 py-3 items-center text-gray-200">
                <span className="truncate pr-4 font-bold text-gray-300" title={c.filename}>{c.filename}</span>
                <span>{c.epoch}</span>
                <span className="text-indigo-400 font-bold">{c.loss}</span>
                <span className="text-gray-400">{c.size_mb} MB</span>
                <div className="text-right">
                  <button
                    onClick={() => handleLoad(c.filename)}
                    className="bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg py-1 px-3 text-[11px] font-semibold transition-all font-sans"
                  >
                    Restore Checkpoint
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------------------------------------
// VIEW: Settings View Component
// ------------------------------------------------------------------------------------------------
interface SettingsViewProps {
  settings: SystemSettings | null
  fetchSettings: () => void
  showToast: any
}

function SettingsView({ settings, fetchSettings, showToast }: SettingsViewProps) {
  const [lr, setLr] = useState(0.001)
  const [batchSize, setBatchSize] = useState(4)
  const [seqLen, setSeqLen] = useState(32)
  const [numLayers, setNumLayers] = useState(2)
  const [numHeads, setNumHeads] = useState(2)
  const [embedDim, setEmbedDim] = useState(32)
  const [hiddenDim, setHiddenDim] = useState(128)
  const [epochs, setEpochs] = useState(5)
  const [dropout, setDropout] = useState(0.1)

  useEffect(() => {
    if (settings) {
      setLr(settings.learning_rate)
      setBatchSize(settings.batch_size)
      setSeqLen(settings.seq_len)
      setNumLayers(settings.num_layers)
      setNumHeads(settings.num_heads)
      setEmbedDim(settings.embedding_dim)
      setHiddenDim(settings.hidden_dim)
      setEpochs(settings.epochs)
      setDropout(settings.dropout)
    }
  }, [settings])

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const res = await api.saveSettings({
        learning_rate: lr,
        batch_size: batchSize,
        seq_len: seqLen,
        num_layers: numLayers,
        num_heads: numHeads,
        embedding_dim: embedDim,
        hidden_dim: hiddenDim,
        epochs: epochs,
        dropout: dropout
      })
      if (res.success) {
        showToast('Settings saved.', 'success')
        fetchSettings()
      }
    } catch (err: any) {
      showToast('Could not save settings.', 'error')
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-white">Global Settings Configuration</h2>
        <p className="text-xs text-gray-400 mt-1">Configure structural layers and hyperparameter variables for active training sessions</p>
      </div>

      <form onSubmit={handleSave} className="glass-panel rounded-2xl p-6 flex flex-col gap-6 text-xs">
        <div className="grid grid-cols-2 gap-6">
          {/* LR */}
          <div className="flex flex-col gap-1.5">
            <label className="text-gray-400 font-semibold uppercase text-[10px]">Learning Rate</label>
            <input
              type="number"
              step="0.0001"
              value={lr}
              onChange={(e) => setLr(parseFloat(e.target.value) || 0.001)}
              className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none text-gray-200 font-mono"
            />
          </div>

          {/* Batch Size */}
          <div className="flex flex-col gap-1.5">
            <label className="text-gray-400 font-semibold uppercase text-[10px]">Batch Size</label>
            <input
              type="number"
              value={batchSize}
              onChange={(e) => setBatchSize(parseInt(e.target.value) || 4)}
              className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none text-gray-200 font-mono"
            />
          </div>

          {/* Context Len */}
          <div className="flex flex-col gap-1.5">
            <label className="text-gray-400 font-semibold uppercase text-[10px]">Sequence Max Context Length</label>
            <input
              type="number"
              value={seqLen}
              onChange={(e) => setSeqLen(parseInt(e.target.value) || 32)}
              className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none text-gray-200 font-mono"
            />
          </div>

          {/* Epochs */}
          <div className="flex flex-col gap-1.5">
            <label className="text-gray-400 font-semibold uppercase text-[10px]">Total Training Epochs</label>
            <input
              type="number"
              value={epochs}
              onChange={(e) => setEpochs(parseInt(e.target.value) || 5)}
              className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none text-gray-200 font-mono"
            />
          </div>

          {/* Blocks layers */}
          <div className="flex flex-col gap-1.5">
            <label className="text-gray-400 font-semibold uppercase text-[10px]">Transformer Block Stack Layers</label>
            <input
              type="number"
              value={numLayers}
              onChange={(e) => setNumLayers(parseInt(e.target.value) || 2)}
              className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none text-gray-200 font-mono"
            />
          </div>

          {/* Attention Heads */}
          <div className="flex flex-col gap-1.5">
            <label className="text-gray-400 font-semibold uppercase text-[10px]">Attention Heads</label>
            <input
              type="number"
              value={numHeads}
              onChange={(e) => setNumHeads(parseInt(e.target.value) || 2)}
              className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none text-gray-200 font-mono"
            />
          </div>

          {/* Embedding Dim */}
          <div className="flex flex-col gap-1.5">
            <label className="text-gray-400 font-semibold uppercase text-[10px]">Embedding Dimension (Width)</label>
            <input
              type="number"
              value={embedDim}
              onChange={(e) => setEmbedDim(parseInt(e.target.value) || 32)}
              className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none text-gray-200 font-mono"
            />
          </div>

          {/* FFN Hidden Dim */}
          <div className="flex flex-col gap-1.5">
            <label className="text-gray-400 font-semibold uppercase text-[10px]">FFN Expansion Dimension</label>
            <input
              type="number"
              value={hiddenDim}
              onChange={(e) => setHiddenDim(parseInt(e.target.value) || 128)}
              className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none text-gray-200 font-mono"
            />
          </div>

          {/* Dropout */}
          <div className="flex flex-col gap-1.5">
            <label className="text-gray-400 font-semibold uppercase text-[10px]">Dropout Rate</label>
            <input
              type="number"
              step="0.05"
              value={dropout}
              onChange={(e) => setDropout(parseFloat(e.target.value) || 0.1)}
              className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none text-gray-200 font-mono"
            />
          </div>
        </div>

        <button
          type="submit"
          className="bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl py-2 px-6 text-xs font-semibold self-end transition-all flex items-center gap-1.5"
        >
          <Sliders className="h-4 w-4" />
          <span>Save Configuration Settings</span>
        </button>
      </form>
    </div>
  )
}

// ==========================================
// 4.5 Dynamic Response Renderer Component
// ==========================================
interface DynamicResponseRendererProps {
  content: string
  question: string
}

function DynamicResponseRenderer({ content, question }: DynamicResponseRendererProps) {
  const q = question.toLowerCase().trim();
  const c = content.trim();

  // 1. Detect Tables (Markdown tables with pipes)
  if (c.includes('|') && c.includes('-') && c.split('\n').length > 2) {
    const lines = c.split('\n');
    const rows = lines.map(line => {
      return line.split('|').map(cell => cell.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
    }).filter(row => row.length > 0);

    if (rows.length >= 2) {
      const headers = rows[0];
      const dataRows = rows.slice(2);
      return (
        <div className="overflow-x-auto border border-gray-800 rounded-xl my-2 max-w-full">
          <table className="w-full text-left border-collapse text-[10px]">
            <thead>
              <tr className="bg-gray-900 border-b border-gray-800 text-white font-semibold">
                {headers.map((h, idx) => (
                  <th key={idx} className="p-2.5">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-850 bg-gray-950/20">
              {dataRows.map((row, rIdx) => (
                <tr key={rIdx} className="hover:bg-gray-900/30 text-gray-300">
                  {row.map((cell, cIdx) => (
                    <td key={cIdx} className="p-2.5">{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
  }

  // 2. Detect Yes/No Questions
  const lowerContent = c.toLowerCase();
  const startsWithYes = lowerContent.startsWith("yes") || c.startsWith("✅ yes");
  const startsWithNo = lowerContent.startsWith("no") || c.startsWith("❌ no") || lowerContent.startsWith("the uploaded document does not mention");
  
  if (startsWithYes || startsWithNo) {
    const isYes = startsWithYes;
    const explanation = c.replace(/^(yes|no|✅ yes|❌ no)[,\s\.]*/i, "").trim();
    return (
      <div className="flex flex-col gap-2">
        <div className="flex items-center">
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[9px] font-bold ${
            isYes 
              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" 
              : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
          }`}>
            {isYes ? "✅ Yes" : "❌ No"}
          </span>
        </div>
        {explanation && (
          <p className="text-gray-300 leading-relaxed pl-0.5">{explanation}</p>
        )}
      </div>
    );
  }

  // 3. Detect Phone, Email, and Candidate Name (Single value strings)
  const isEmail = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/.test(c) && c.length < 50;
  const isPhone = (/^(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}$/.test(c.replace(/[\s()-]/g, "")) || /^\+?\d{8,15}$/.test(c.replace(/[\s()-]/g, ""))) && c.length < 30;
  const isName = (q.includes("name") || q.includes("candidate") || q.includes("who is")) && c.length < 40 && !c.includes("\n") && !c.includes("•");

  if (isPhone || isEmail || isName) {
    return (
      <div className="flex items-center gap-3 py-1">
        <span className="text-lg">{isPhone ? "📞" : isEmail ? "📧" : "👤"}</span>
        <div>
          <div className="text-[8px] uppercase tracking-wider text-gray-500 font-semibold">
            {isPhone ? "Phone Number" : isEmail ? "Email Address" : "Candidate Name"}
          </div>
          <div className="text-white font-bold text-[11px] select-all">{c}</div>
        </div>
      </div>
    );
  }

  // 4. Detect Count
  if (q.includes("how many") || q.includes("count") || q.includes("total experience") || q.includes("years of experience")) {
    if (/^\d+(\s*years)?$/i.test(c)) {
      return (
        <div className="flex items-center gap-3 py-1">
          <span className="text-lg">📊</span>
          <div>
            <div className="text-[8px] uppercase tracking-wider text-gray-500 font-semibold">Total Count / Experience</div>
            <div className="text-indigo-400 font-extrabold text-sm">{c}</div>
          </div>
        </div>
      );
    }
  }

  // 5. Helper function to parse multiline lists into block groups
  const parseBlocks = (text: string) => {
    const lines = text.split('\n');
    const blocks: { title: string; details: string[] }[] = [];
    let currentBlock: { title: string; details: string[] } | null = null;
    
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      
      // Match bullet point or numbered item start
      if (line.startsWith('•') || line.startsWith('-') || /^\d+\./.test(trimmed)) {
        const titleText = trimmed.replace(/^[•\-\d\.\s]+/, '').trim();
        if (titleText) {
          currentBlock = { title: titleText, details: [] };
          blocks.push(currentBlock);
        }
      } else if (currentBlock) {
        const detailText = trimmed.replace(/^[\-\s]+/, '').trim();
        if (detailText) {
          currentBlock.details.push(detailText);
        }
      } else {
        // Fallback for lines without a header block
        blocks.push({ title: trimmed, details: [] });
      }
    }
    return blocks;
  };

  // 6. Detect Projects
  if (q.includes("project") || lowerContent.includes("project name")) {
    const blocks = parseBlocks(c);
    if (blocks.length > 0) {
      return (
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-1.5 font-semibold text-white mb-1">
            <span>🚀 Projects</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {blocks.map((block, i) => (
              <div key={i} className="bg-gray-950/40 border border-gray-855 p-3 rounded-xl relative overflow-hidden flex flex-col justify-between hover:border-gray-800 transition-all">
                <div className="absolute top-2 right-3 font-bold text-lg text-gray-800/40 select-none">#{i + 1}</div>
                <div>
                  <div className="font-bold text-white text-[11px] mb-1.5 pr-8 truncate">
                    {block.title}
                  </div>
                  {block.details.length > 0 && (
                    <ul className="space-y-1 text-gray-400 text-[10px] pl-1">
                      {block.details.map((detail, dIdx) => (
                        <li key={dIdx} className="leading-normal">
                          {detail}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      );
    }
  }

  // 7. Detect Experience
  if (q.includes("experience") || q.includes("work") || q.includes("job") || q.includes("company") || q.includes("employment")) {
    const blocks = parseBlocks(c);
    if (blocks.length > 0) {
      return (
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-1.5 font-semibold text-white mb-1">
            <span>💼 Work Experience</span>
          </div>
          <div className="flex flex-col gap-2.5">
            {blocks.map((block, i) => (
              <div key={i} className="bg-gray-950/40 border border-gray-855 p-3 rounded-xl hover:border-gray-800 transition-all">
                <div className="font-bold text-white flex items-center gap-2 mb-1.5">
                  <span className="h-1.5 w-1.5 bg-indigo-400 rounded-full" />
                  {block.title}
                </div>
                {block.details.length > 0 && (
                  <ul className="space-y-1 pl-3.5 text-gray-400 text-[10px]">
                    {block.details.map((detail, dIdx) => (
                      <li key={dIdx} className="list-disc leading-relaxed">
                        {detail}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>
      );
    }
  }

  // 8. Detect Education
  if (q.includes("education") || q.includes("study") || q.includes("college") || q.includes("degree") || q.includes("university")) {
    const blocks = parseBlocks(c);
    if (blocks.length > 0) {
      return (
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-1.5 font-semibold text-white mb-1">
            <span>🎓 Education</span>
          </div>
          <div className="flex flex-col gap-2.5">
            {blocks.map((block, i) => (
              <div key={i} className="bg-gray-950/40 border border-gray-855 p-3 rounded-xl hover:border-gray-800 transition-all">
                <div className="font-bold text-white flex items-center gap-2 mb-1.5">
                  <span className="h-1.5 w-1.5 bg-indigo-400 rounded-full" />
                  {block.title}
                </div>
                {block.details.length > 0 && (
                  <ul className="space-y-1 pl-3.5 text-gray-400 text-[10px]">
                    {block.details.map((detail, dIdx) => (
                      <li key={dIdx} className="list-disc leading-relaxed">
                        {detail}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>
      );
    }
  }

  // 9. Detect Skills
  if (q.includes("skills") || q.includes("technical") || q.includes("expert") || q.includes("competenc")) {
    const blocks = parseBlocks(c);
    if (blocks.length > 0) {
      return (
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-1.5 font-semibold text-white mb-1">
            <span>💻 Skills</span>
          </div>
          <div className="flex flex-wrap gap-1.5 mt-1">
            {blocks.map((block, i) => (
              <span key={i} className="bg-indigo-500/10 border border-indigo-500/15 text-indigo-300 text-[10px] px-2.5 py-1 rounded-full font-medium transition-all hover:bg-indigo-500/20">
                {block.title}
              </span>
            ))}
          </div>
        </div>
      );
    }
  }

  // 10. Detect Certifications
  if (q.includes("certif")) {
    const blocks = parseBlocks(c);
    if (blocks.length > 0) {
      return (
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-1.5 font-semibold text-white mb-1">
            <span>🏆 Certifications</span>
          </div>
          <ul className="space-y-1 pl-1">
            {blocks.map((block, i) => (
              <li key={i} className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 bg-indigo-400 rounded-full shrink-0" />
                <span>{block.title}</span>
              </li>
            ))}
          </ul>
        </div>
      );
    }
  }

  // 11. Detect Languages / Address
  const isLang = q.includes("language");
  const isAddr = q.includes("address") || q.includes("location") || q.includes("where does");
  if (isLang || isAddr) {
    const blocks = parseBlocks(c);
    if (blocks.length > 0) {
      return (
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-1.5 font-semibold text-white mb-1">
            <span>{isLang ? "🌍 Languages" : "🏠 Address"}</span>
          </div>
          <ul className="space-y-1 pl-1">
            {blocks.map((block, i) => (
              <li key={i} className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 bg-indigo-400 rounded-full shrink-0" />
                <span>{block.title}</span>
              </li>
            ))}
          </ul>
        </div>
      );
    }
  }

  // Default to Summary paragraph block
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-1.5 font-semibold text-white mb-0.5">
        <span>📝 Summary</span>
      </div>
      <p className="leading-relaxed">{c}</p>
    </div>
  );
}

// ==========================================
// 5. Document Chat View Component
// ==========================================
function DocumentChatView({ showToast }: { showToast: any }) {
  const [documents, setDocuments] = useState<any[]>([])
  const [activeDocId, setActiveDocId] = useState<string | null>(null)
  const [activeDocDetails, setActiveDocDetails] = useState<any | null>(null)
  const [uploading, setUploading] = useState(false)
  const [chatLoading, setChatLoading] = useState(false)
  const [previewSearch, setPreviewSearch] = useState('')
  const [sidebarSearch, setSidebarSearch] = useState('')
  
  const [messages, setMessages] = useState<any[]>([])
  const [inputVal, setInputVal] = useState('')
  const [sessionId] = useState(() => Math.random().toString(36).substring(7))
  
  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    loadDocuments()
  }, [])

  // Poll for document status updates if any document is processing
  useEffect(() => {
    const hasProcessing = documents.some(doc => 
      ['uploaded', 'processing', 'extracting', 'chunking', 'embedding', 'indexing'].includes(doc.status)
    )
    if (!hasProcessing) return

    const pollInterval = setInterval(() => {
      // Load documents from backend
      api.getDocuments().then(docs => {
        // If activeDocId was processing, and is now processed, load its details
        const oldDoc = documents.find(d => d.id === activeDocId)
        const newDoc = docs.find((d: any) => d.id === activeDocId)
        if (activeDocId && oldDoc && newDoc && oldDoc.status !== 'processed' && newDoc.status === 'processed') {
          loadDocumentDetails(activeDocId)
        }
        setDocuments(docs)
      }).catch(() => {})
    }, 1500)

    return () => clearInterval(pollInterval)
  }, [documents, activeDocId])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, chatLoading])

  useEffect(() => {
    if (activeDocId) {
      loadDocumentDetails(activeDocId)
      loadChatHistory()
    } else {
      setActiveDocDetails(null)
      setMessages([])
    }
  }, [activeDocId])

  const loadDocuments = async () => {
    try {
      const docs = await api.getDocuments()
      
      const oldDoc = documents.find(d => d.id === activeDocId)
      const newDoc = docs.find((d: any) => d.id === activeDocId)
      if (activeDocId && oldDoc && newDoc && oldDoc.status !== 'processed' && newDoc.status === 'processed') {
        loadDocumentDetails(activeDocId)
      }
      
      setDocuments(docs)
      if (docs.length > 0 && !activeDocId) {
        // Auto-select the first processed or first uploaded document
        const firstReady = docs.find((d: any) => d.status === 'processed') || docs[0]
        setActiveDocId(firstReady.id)
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to load documents.', 'error')
    }
  }

  const loadDocumentDetails = async (docId: string) => {
    try {
      const details = await api.getDocumentDetails(docId)
      setActiveDocDetails(details)
    } catch (err: any) {
      showToast(err.message || 'Failed to load document details.', 'error')
    }
  }

  const loadChatHistory = async () => {
    try {
      const history = await api.getChatHistory(sessionId)
      setMessages(history.map((m: any) => ({
        role: m.role,
        content: m.content,
        metadata: m.metadata || {}
      })))
    } catch (err) {
      setMessages([])
    }
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    try {
      showToast(`Uploading and indexing '${file.name}' locally...`, 'info')
      const doc = await api.uploadDocument(file, 500)
      if (doc.status === 'error') {
        throw new Error(doc.error || 'Ingestion failed')
      }
      showToast(`Document '${file.name}' indexed successfully.`, 'success')
      await loadDocuments()
      setActiveDocId(doc.id)
    } catch (err: any) {
      showToast(err.message || 'Upload failed.', 'error')
    } finally {
      setUploading(false)
      if (e.target) e.target.value = ''
    }
  }

  const handleDelete = async (docId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Are you sure you want to delete this document?')) return

    try {
      await api.deleteDocument(docId)
      showToast('Document deleted.', 'success')
      if (activeDocId === docId) {
        setActiveDocId(null)
      }
      loadDocuments()
    } catch (err: any) {
      showToast(err.message || 'Delete failed.', 'error')
    }
  }

  const handleResetChat = async () => {
    try {
      await api.resetChat(sessionId)
      setMessages([])
      showToast('Chat history reset.', 'success')
    } catch (err: any) {
      showToast(err.message || 'Failed to reset chat.', 'error')
    }
  }

  const handleSend = async (questionText: string) => {
    const query = questionText.trim()
    if (!query) return

    setMessages(prev => [...prev, { role: 'user', content: query }])
    setInputVal('')
    setChatLoading(true)

    try {
      const res = await api.postChat(sessionId, query, activeDocId, true, 3, 0.0)
      const reader = res.body?.getReader()
      if (!reader) throw new Error('Could not open stream reader')
      
      const decoder = new TextDecoder('utf-8')
      let buffer = ''
      
      setMessages(prev => [...prev, { role: 'assistant', content: '', loading: true }])

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const cleaned = line.trim()
          if (cleaned.startsWith('data: ')) {
            const eventData = cleaned.substring(6)
            if (eventData === '[DONE]') {
              break
            }
            try {
              const parsed = JSON.parse(eventData)
              if (parsed.token) {
                setMessages(prev => {
                  if (prev.length === 0) return prev
                  const last = prev[prev.length - 1]
                  if (last && last.role === 'assistant') {
                    return [
                      ...prev.slice(0, -1),
                      {
                        ...last,
                        content: last.content + parsed.token,
                        loading: false
                      }
                    ]
                  }
                  return prev
                })
              } else if (parsed.metadata) {
                setMessages(prev => {
                  if (prev.length === 0) return prev
                  const last = prev[prev.length - 1]
                  if (last && last.role === 'assistant') {
                    return [
                      ...prev.slice(0, -1),
                      {
                        ...last,
                        metadata: parsed.metadata
                      }
                    ]
                  }
                  return prev
                })
              }
            } catch (jsonErr) {
              // ignore partial line errors
            }
          }
        }
      }
    } catch (err: any) {
      showToast(err.message || 'Chat failed.', 'error')
      setMessages(prev => {
        if (prev.length === 0) return prev
        const last = prev[prev.length - 1]
        if (last && last.loading) {
          return [
            ...prev.slice(0, -1),
            {
              ...last,
              content: "An error occurred during generating reply.",
              loading: false
            }
          ]
        }
        return prev
      })
    } finally {
      setChatLoading(false)
    }
  }

  const getFileIcon = (ext: string) => {
    const e = ext.toLowerCase()
    if (e === '.pdf') return <FileText className="h-4 w-4 text-rose-400" />
    if (['.xlsx', '.xls', '.csv'].includes(e)) return <FileText className="h-4 w-4 text-emerald-400" />
    if (['.pptx', '.ppt'].includes(e)) return <FileText className="h-4 w-4 text-orange-400" />
    if (['.docx', '.doc'].includes(e)) return <FileText className="h-4 w-4 text-sky-400" />
    if (['.png', '.jpg', '.jpeg', '.tiff'].includes(e)) return <FileText className="h-4 w-4 text-amber-400" />
    return <FileText className="h-4 w-4 text-gray-400" />
  }

  const filteredDocs = documents.filter(d => 
    d.filename.toLowerCase().includes(sidebarSearch.toLowerCase())
  )

  const filteredChunks = activeDocDetails?.chunks?.filter((c: any) =>
    c.text.toLowerCase().includes(previewSearch.toLowerCase())
  ) || []

  return (
    <div className="flex gap-6 h-full overflow-hidden text-xs text-gray-300">
      <div className="w-64 glass-panel rounded-2xl p-4 flex flex-col gap-4 border border-gray-800 bg-gray-950/20 shrink-0">
        <div className="flex justify-between items-center border-b border-gray-800 pb-2">
          <span className="font-bold text-xs uppercase text-gray-400 tracking-wider">Document Library</span>
          <button 
            onClick={handleResetChat} 
            className="text-[10px] text-indigo-400 hover:text-indigo-300 hover:underline font-semibold"
          >
            Reset Chat
          </button>
        </div>

        <label className="flex flex-col items-center justify-center border border-dashed border-gray-850 hover:border-indigo-500/50 rounded-xl p-4 cursor-pointer transition-all bg-gray-900/10">
          <Upload className="h-5 w-5 text-gray-500 mb-1.5" />
          <span className="text-[10px] text-gray-400 text-center font-medium">Click to upload doc</span>
          <span className="text-[8px] text-gray-500 text-center mt-0.5">PDF, DOCX, XLSX, PPTX, Images...</span>
          <input 
            type="file" 
            onChange={handleUpload} 
            disabled={uploading} 
            className="hidden" 
            accept=".pdf,.docx,.doc,.xlsx,.xls,.csv,.pptx,.ppt,.txt,.md,.markdown,.json,.html,.htm,.xml,.png,.jpg,.jpeg,.tiff,.bmp"
          />
        </label>

        {uploading && (
          <div className="flex items-center gap-2 bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 px-3 py-2 rounded-xl text-[10px] animate-pulse">
            <RefreshCw className="h-3 w-3 animate-spin" />
            <span>Ingesting & indexing local vector blocks...</span>
          </div>
        )}

        <div className="relative">
          <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-gray-500" />
          <input
            type="text"
            placeholder="Search documents..."
            value={sidebarSearch}
            onChange={(e) => setSidebarSearch(e.target.value)}
            className="w-full bg-gray-950/80 border border-gray-850 rounded-xl pl-8 pr-3 py-1.5 text-xs text-gray-200 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        <div className="flex-1 overflow-y-auto flex flex-col gap-1 pr-1 border-t border-gray-900 pt-3">
          {filteredDocs.length === 0 ? (
            <div className="text-center text-gray-600 italic py-4">No documents found.</div>
          ) : (
            filteredDocs.map((doc) => (
              <div
                key={doc.id}
                onClick={() => doc.status === 'processed' && setActiveDocId(doc.id)}
                className={`group flex items-center justify-between px-3 py-2 rounded-xl cursor-pointer border transition-all ${
                  activeDocId === doc.id
                    ? 'bg-indigo-600/10 border-indigo-500 text-white'
                    : 'bg-gray-900/30 border-gray-850 hover:bg-gray-900/50 hover:text-white'
                }`}
              >
                <div className="flex flex-col overflow-hidden mr-2">
                  <div className="flex items-center gap-2">
                    {getFileIcon(doc.file_type)}
                    <span className="truncate font-medium text-[11px]">{doc.filename}</span>
                  </div>
                  {['uploaded', 'processing', 'extracting', 'chunking', 'embedding', 'indexing'].includes(doc.status) && (
                    <span className="text-[8px] text-indigo-400 font-semibold italic pl-6 mt-0.5">
                      {doc.status === 'uploaded' && 'Uploaded'}
                      {doc.status === 'processing' && 'Processing...'}
                      {doc.status === 'extracting' && 'Extracting text...'}
                      {doc.status === 'chunking' && 'Chunking...'}
                      {doc.status === 'embedding' && 'Generating vectors...'}
                      {doc.status === 'indexing' && 'Saving index...'}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  {['uploaded', 'processing', 'extracting', 'chunking', 'embedding', 'indexing'].includes(doc.status) && (
                    <RefreshCw className="h-3 w-3 animate-spin text-indigo-400" />
                  )}
                  {doc.status === 'error' && (
                    <span title={doc.error} className="flex items-center">
                      <AlertCircle className="h-3.5 w-3.5 text-rose-500" />
                    </span>
                  )}
                  <button
                    onClick={(e) => handleDelete(doc.id, e)}
                    className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-rose-400 p-0.5 rounded transition-all"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="flex-1 glass-panel rounded-2xl flex flex-col border border-gray-800 overflow-hidden bg-gray-950/10">
        {!activeDocId ? (
          <div className="flex-1 flex flex-col items-center justify-center p-6 text-center max-w-md mx-auto">
            <div className="p-4 bg-indigo-500/10 rounded-full border border-indigo-500/20 text-indigo-400 mb-4 animate-bounce">
              <MessageSquare className="h-8 w-8" />
            </div>
            <h3 className="text-base font-bold text-white mb-2">Local Knowledge Chat</h3>
            <p className="text-gray-400 text-xs leading-relaxed mb-4">
              Upload documents in the library to start an offline QA session. 
              The assistant will reason over extracted segments using your custom MyGPT model.
            </p>
            <div className="text-[10px] text-gray-500 border-t border-gray-900 pt-3 w-full">
              Supported Formats: PDF, DOCX, TXT, Markdown, CSV, Excel, PowerPoint, JSON, HTML, Images (OCR)
            </div>
          </div>
        ) : (
          <>
            <div className="px-4 py-3 border-b border-gray-800 bg-gray-900/30 flex justify-between items-center">
              <div className="flex items-center gap-2 overflow-hidden">
                <FileText className="h-4 w-4 text-indigo-400 shrink-0" />
                <span className="font-semibold text-white truncate max-w-xs md:max-w-md">
                  Active: {documents.find(d => d.id === activeDocId)?.filename}
                </span>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <span className="text-[9px] bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 px-2 py-0.5 rounded-full font-semibold uppercase tracking-wider">Local Inference</span>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
              {messages.length === 0 && (
                <div className="flex-1 flex flex-col items-center justify-center text-center text-gray-500 p-8">
                  <Bot className="h-8 w-8 text-gray-700 mb-2" />
                  <p className="text-xs">Ask a question about the active document to start reasoning.</p>
                  <div className="grid grid-cols-2 gap-2 mt-4 max-w-sm">
                    <button onClick={() => handleSend("Summarize this document.")} className="text-[10px] bg-gray-900/40 hover:bg-gray-900/60 border border-gray-855 hover:border-gray-750 px-3 py-2 rounded-xl text-left transition-all truncate text-gray-400 hover:text-white">
                      Summarize this document
                    </button>
                    <button onClick={() => handleSend("What are the important points?")} className="text-[10px] bg-gray-900/40 hover:bg-gray-900/60 border border-gray-855 hover:border-gray-750 px-3 py-2 rounded-xl text-left transition-all truncate text-gray-400 hover:text-white">
                      What are the important points?
                    </button>
                  </div>
                </div>
              )}

              {messages.map((msg, idx) => (
                <div key={idx} className={`flex gap-3 max-w-3xl ${msg.role === 'user' ? 'self-end flex-row-reverse' : 'self-start'}`}>
                  <div className={`p-2 rounded-full border shrink-0 h-max ${
                    msg.role === 'user'
                      ? 'bg-gray-800 border-gray-700 text-gray-300'
                      : 'bg-indigo-600/10 border-indigo-500/30 text-indigo-400'
                  }`}>
                    {msg.role === 'user' ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                  </div>

                  <div className="flex flex-col gap-2">
                    <div className={`rounded-2xl px-4 py-2.5 text-[11px] leading-relaxed shadow-sm ${
                      msg.role === 'user'
                        ? 'bg-gray-900 text-gray-200 border border-gray-800 rounded-tr-none'
                        : 'bg-gray-900/65 text-gray-300 border border-gray-850 rounded-tl-none'
                    }`}>
                      {msg.role === 'user' ? (
                        msg.content
                      ) : (
                        <DynamicResponseRenderer content={msg.content} question={messages[idx - 1]?.content || ""} />
                      )}
                      {msg.loading && (
                        <span className="inline-flex gap-0.5 ml-1 animate-pulse">
                          <span className="h-1.5 w-1.5 bg-indigo-400 rounded-full"></span>
                          <span className="h-1.5 w-1.5 bg-indigo-400 rounded-full"></span>
                          <span className="h-1.5 w-1.5 bg-indigo-400 rounded-full"></span>
                        </span>
                      )}
                    </div>

                    {msg.role === 'assistant' && msg.metadata && (
                      <div className="flex flex-col gap-2 pl-1">
                        {msg.metadata.sources && msg.metadata.sources.length > 0 && (
                          <details className="text-[10px] text-gray-500 cursor-pointer">
                            <summary className="hover:text-indigo-400 select-none font-semibold transition-all">
                              Source References ({msg.metadata.sources.length} sections)
                            </summary>
                            <div className="flex flex-col gap-1.5 mt-2 bg-gray-950/40 p-2.5 rounded-xl border border-gray-900/50">
                              {msg.metadata.sources.map((src: any, sIdx: number) => (
                                <div key={sIdx} className="border-b border-gray-900/80 pb-1.5 last:border-0 last:pb-0">
                                  <div className="flex justify-between text-[9px] font-semibold text-gray-400 mb-0.5">
                                    <span>Page {src.page_number} | Section: {src.section}</span>
                                    <span className="text-indigo-400 font-bold">Match: {(src.score * 100).toFixed(0)}%</span>
                                  </div>
                                  <p className="text-[9px] text-gray-500 italic font-sans leading-normal">"{src.text}"</p>
                                </div>
                              ))}
                            </div>
                          </details>
                        )}

                        {msg.metadata.confidence !== undefined && (
                          <div className="flex items-center gap-1.5 text-[9px] font-semibold text-gray-500">
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                            <span>MyGPT Confidence: <strong className="text-white">{msg.metadata.confidence}%</strong></span>
                          </div>
                        )}

                        {msg.metadata.suggested_questions && msg.metadata.suggested_questions.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 mt-1.5">
                            {msg.metadata.suggested_questions.map((q: string, qIdx: number) => (
                              <button
                                key={qIdx}
                                onClick={() => handleSend(q)}
                                className="text-[9px] bg-indigo-500/5 hover:bg-indigo-500/10 text-indigo-400/90 hover:text-indigo-300 border border-indigo-500/15 hover:border-indigo-400/30 px-2 py-1 rounded-lg transition-all"
                              >
                                {q}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {chatLoading && messages[messages.length - 1]?.role === 'user' && (
                <div className="flex gap-3 max-w-lg self-start">
                  <div className="p-2 rounded-full border bg-indigo-600/10 border-indigo-500/30 text-indigo-400 shrink-0">
                    <Bot className="h-4 w-4 animate-spin" />
                  </div>
                  <div className="bg-gray-900/65 text-gray-400 border border-gray-855 rounded-2xl rounded-tl-none px-4 py-2.5 text-[11px] flex items-center gap-2 shadow-sm animate-pulse">
                    <span>Searching context and reasoning...</span>
                  </div>
                </div>
              )}

              <div ref={chatEndRef} />
            </div>

            <div className="p-4 border-t border-gray-800 bg-gray-950/20">
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  handleSend(inputVal)
                }}
                className="relative"
              >
                <input
                  type="text"
                  placeholder="Ask a question about the document..."
                  value={inputVal}
                  onChange={(e) => setInputVal(e.target.value)}
                  disabled={chatLoading}
                  className="w-full bg-gray-950 border border-gray-800 rounded-xl pl-4 pr-12 py-3 text-xs text-gray-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500/50 disabled:opacity-50"
                />
                <button
                  type="submit"
                  disabled={chatLoading || !inputVal.trim()}
                  className="absolute right-2 top-2 p-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-all disabled:opacity-40 disabled:hover:bg-indigo-600"
                >
                  <Send className="h-3.5 w-3.5" />
                </button>
              </form>
            </div>
          </>
        )}
      </div>

      {activeDocId && activeDocDetails && (
        <div className="w-80 glass-panel rounded-2xl p-4 flex flex-col gap-4 border border-gray-800 bg-gray-950/20 shrink-0">
          <div className="border-b border-gray-800 pb-2">
            <span className="font-bold text-xs uppercase text-gray-400 tracking-wider">Document Preview</span>
          </div>

          <div className="relative">
            <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-gray-500" />
            <input
              type="text"
              placeholder="Find keywords in document..."
              value={previewSearch}
              onChange={(e) => setPreviewSearch(e.target.value)}
              className="w-full bg-gray-950/80 border border-gray-850 rounded-xl pl-8 pr-3 py-1.5 text-xs text-gray-200 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <div className="flex-1 overflow-y-auto flex flex-col gap-3 pr-1 border-t border-gray-900 pt-3">
            {filteredChunks.length === 0 ? (
              <div className="text-center text-gray-600 italic py-4">No content chunks match keyword.</div>
            ) : (
              filteredChunks.map((chunk: any, cIdx: number) => (
                <div key={cIdx} className="bg-gray-900/30 border border-gray-850 rounded-xl p-3 flex flex-col gap-1.5">
                  <div className="flex justify-between items-center text-[9px] font-semibold text-indigo-400">
                    <span>Page {chunk.page_number}</span>
                    <span className="text-gray-500">{chunk.section}</span>
                  </div>
                  <p className="text-[10px] text-gray-400 leading-relaxed font-mono select-text selection:bg-indigo-500 selection:text-white">
                    {chunk.text}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
