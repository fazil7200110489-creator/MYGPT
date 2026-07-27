const BASE_URL = 'http://127.0.0.1:8000'

export const api = {
  async getDashboard() {
    const res = await fetch(`${BASE_URL}/api/dashboard`)
    if (!res.ok) throw new Error('Failed to fetch dashboard info')
    return res.json()
  },

  async tokenize(text: string) {
    const res = await fetch(`${BASE_URL}/api/tokenize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    })
    if (!res.ok) throw new Error('Tokenize failed')
    return res.json()
  },

  async getVocabulary() {
    const res = await fetch(`${BASE_URL}/api/vocabulary`)
    if (!res.ok) throw new Error('Failed to load vocabulary')
    return res.json()
  },

  async getDataset(text: string, seqLen: number, stride: number = 1) {
    const res = await fetch(`${BASE_URL}/api/dataset`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, seq_len: seqLen, stride })
    })
    if (!res.ok) throw new Error('Failed to load dataset trace')
    return res.json()
  },

  async getEmbedding(text: string) {
    const res = await fetch(`${BASE_URL}/api/embedding`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    })
    if (!res.ok) throw new Error('Failed to inspect embeddings')
    return res.json()
  },

  async getAttention(text: string) {
    const res = await fetch(`${BASE_URL}/api/attention`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    })
    if (!res.ok) throw new Error('Failed to compute attention weights')
    return res.json()
  },

  async startTraining(settings: any) {
    const res = await fetch(`${BASE_URL}/api/train/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ settings })
    })
    if (!res.ok) throw new Error('Failed to start training')
    return res.json()
  },

  async stopTraining() {
    const res = await fetch(`${BASE_URL}/api/train/stop`, {
      method: 'POST'
    })
    if (!res.ok) throw new Error('Failed to send stop signal')
    return res.json()
  },

  async getTrainStatus() {
    const res = await fetch(`${BASE_URL}/api/train/status`)
    if (!res.ok) throw new Error('Failed to query training status')
    return res.json()
  },

  async generate(prompt: string, maxTokens: number = 50, temperature: number = 1.0, topK: number = 0, topP: number = 0.0) {
    const res = await fetch(`${BASE_URL}/api/inference`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt,
        max_tokens: maxTokens,
        temperature,
        top_k: topK,
        top_p: topP
      })
    })
    if (!res.ok) throw new Error('Inference request failed')
    return res.json()
  },

  async getCheckpoints() {
    const res = await fetch(`${BASE_URL}/api/checkpoints`)
    if (!res.ok) throw new Error('Failed to load checkpoints')
    return res.json()
  },

  async loadCheckpoint(filename: string) {
    const res = await fetch(`${BASE_URL}/api/checkpoint/load`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename })
    })
    if (!res.ok) throw new Error('Checkpoint loading failed')
    return res.json()
  },

  async getSettings() {
    const res = await fetch(`${BASE_URL}/api/settings`)
    if (!res.ok) throw new Error('Failed to get settings config')
    return res.json()
  },

  async saveSettings(settings: any) {
    const res = await fetch(`${BASE_URL}/api/settings/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ settings })
    })
    if (!res.ok) throw new Error('Settings update failed')
    return res.json()
  },

  async getDocuments() {
    const res = await fetch(`${BASE_URL}/api/documents`)
    if (!res.ok) throw new Error('Failed to load documents')
    return res.json()
  },

  async uploadDocument(file: File, chunkSize: number = 500) {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('chunk_size', chunkSize.toString())
    
    const res = await fetch(`${BASE_URL}/api/documents/upload`, {
      method: 'POST',
      body: formData
    })
    if (!res.ok) throw new Error('Failed to upload document')
    return res.json()
  },

  async uploadBatchResumes(files: File[]) {
    const formData = new FormData()
    files.forEach(file => {
      formData.append('files', file)
    })

    const res = await fetch(`${BASE_URL}/api/v2/recruiter/upload_batch`, {
      method: 'POST',
      body: formData
    })
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}))
      throw new Error(errData.detail || 'Batch resume upload failed')
    }
    return res.json()
  },

  async deleteDocument(docId: string) {
    const res = await fetch(`${BASE_URL}/api/documents/${docId}`, {
      method: 'DELETE'
    })
    if (!res.ok) throw new Error('Failed to delete document')
    return res.json()
  },

  async getDocumentDetails(docId: string) {
    const res = await fetch(`${BASE_URL}/api/document/${docId}`)
    if (!res.ok) throw new Error('Failed to fetch document details')
    return res.json()
  },

  async searchDocument(docId: string, query: string, topK: number = 3, threshold: number = 0.0) {
    const res = await fetch(`${BASE_URL}/api/document/${docId}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, top_k: topK, similarity_threshold: threshold })
    })
    if (!res.ok) throw new Error('Document search failed')
    return res.json()
  },

  async postChat(sessionId: string, question: string, docId: string | null = null, stream: boolean = false, topK: number = 3, threshold: number = 0.0) {
    const res = await fetch(`${BASE_URL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        question,
        doc_id: docId,
        stream,
        top_k: topK,
        similarity_threshold: threshold
      })
    })
    if (!res.ok) throw new Error('Chat request failed')
    return res
  },

  async getChatHistory(sessionId: string) {
    const res = await fetch(`${BASE_URL}/api/chat/history?session_id=${sessionId}`)
    if (!res.ok) throw new Error('Failed to load chat history')
    return res.json()
  },

  async resetChat(sessionId: string) {
    const formData = new FormData()
    formData.append('session_id', sessionId)
    const res = await fetch(`${BASE_URL}/api/chat/reset`, {
      method: 'POST',
      body: formData
    })
    if (!res.ok) throw new Error('Failed to reset chat')
    return res.json()
  },

  async getModelConfig() {
    const res = await fetch(`${BASE_URL}/api/model/config`)
    if (!res.ok) throw new Error('Failed to load model config')
    return res.json()
  },

  async saveModelConfig(config: { max_sequence_length: number; embedding_dimension: number }) {
    const res = await fetch(`${BASE_URL}/api/model/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    })
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}))
      throw new Error(errData.detail?.[0]?.msg || errData.message || 'Failed to save model config')
    }
    return res.json()
  },

  async queryRecruiterPlatform(query: string, sessionId: string = 'recruiter_session', selectedCandidateIds?: string[]) {
    const res = await fetch(`${BASE_URL}/api/v2/recruiter/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        session_id: sessionId,
        selected_candidate_ids: selectedCandidateIds || null
      })
    })
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}))
      throw new Error(errData.detail || 'Recruiter query failed')
    }
    return res.json()
  },

  async getCandidatePool(domain?: string, skill?: string, location?: string, status?: string) {
    const params = new URLSearchParams()
    if (domain) params.append('domain', domain)
    if (skill) params.append('skill', skill)
    if (location) params.append('location', location)
    if (status) params.append('status', status)
    
    const res = await fetch(`${BASE_URL}/api/v2/recruiter/candidates?${params.toString()}`)
    if (!res.ok) throw new Error('Failed to load candidate pool')
    return res.json()
  },

  async updateCandidateStage(candidateId: string, stage: string, notes: string = '') {
    const res = await fetch(`${BASE_URL}/api/v2/recruiter/candidates/${candidateId}/stage`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stage, notes })
    })
    if (!res.ok) throw new Error('Failed to update candidate stage')
    return res.json()
  },

  async exportRecruiterReport(formatType: string = 'csv') {
    const res = await fetch(`${BASE_URL}/api/v2/recruiter/export?format=${formatType}`)
    if (!res.ok) throw new Error('Export report failed')
    return res.json()
  },

  async deleteCandidateFromPool(candidateId: string) {
    const res = await fetch(`${BASE_URL}/api/v2/recruiter/candidates/${candidateId}`, {
      method: 'DELETE'
    })
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}))
      throw new Error(errData.detail || 'Failed to delete candidate from pool')
    }
    return res.json()
  }
}
