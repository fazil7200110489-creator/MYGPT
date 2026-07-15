import { create } from 'zustand'

export interface LogEntry {
  id: string
  text: string
}

export interface LossData {
  step: number
  loss: number
}

export interface ValLossData {
  epoch: number
  loss: number
}

export interface DashboardStats {
  model_name: string
  device: string
  is_training: boolean
  vocab_size: number
  embedding_dim: number
  num_layers: number
  num_heads: number
  context_len: number
  current_epoch: number
  current_step: number
  total_params: number
}

export interface SystemSettings {
  learning_rate: number
  batch_size: number
  seq_len: number
  num_layers: number
  num_heads: number
  embedding_dim: number
  hidden_dim: number
  epochs: number
  dropout: number
}

interface AppState {
  activeTab: string
  wsConnected: boolean
  isTraining: boolean
  stats: DashboardStats | null
  settings: SystemSettings | null
  logs: string[]
  losses: LossData[]
  valLosses: ValLossData[]
  
  setActiveTab: (tab: string) => void
  setWsConnected: (connected: boolean) => void
  setTraining: (isTraining: boolean) => void
  updateStats: (stats: Partial<DashboardStats>) => void
  updateSettings: (settings: Partial<SystemSettings>) => void
  addLog: (log: string) => void
  setLogs: (logs: string[]) => void
  addLoss: (step: number, loss: number) => void
  setLosses: (losses: LossData[]) => void
  setValLosses: (valLosses: ValLossData[]) => void
}

export const useStore = create<AppState>((set) => ({
  activeTab: 'dashboard',
  wsConnected: false,
  isTraining: false,
  stats: null,
  settings: null,
  logs: [],
  losses: [],
  valLosses: [],

  setActiveTab: (tab) => set({ activeTab: tab }),
  setWsConnected: (connected) => set({ wsConnected: connected }),
  setTraining: (isTraining) => set({ isTraining }),
  updateStats: (stats) => set((state) => ({ 
    stats: state.stats ? { ...state.stats, ...stats } : (stats as DashboardStats),
    isTraining: stats.is_training !== undefined ? stats.is_training : state.isTraining
  })),
  updateSettings: (settings) => set((state) => ({ 
    settings: state.settings ? { ...state.settings, ...settings } : (settings as SystemSettings) 
  })),
  addLog: (log) => set((state) => ({ logs: [...state.logs.slice(-99), log] })),
  setLogs: (logs) => set({ logs }),
  addLoss: (step, loss) => set((state) => ({ losses: [...state.losses, { step, loss }] })),
  setLosses: (losses) => set({ losses }),
  setValLosses: (valLosses) => set({ valLosses })
}))
