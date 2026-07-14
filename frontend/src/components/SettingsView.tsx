import { useEffect, useState, useCallback } from 'react'
import { fetchFontes } from '../services/api'
import type { FonteResponse } from '../services/api'
import { IconPlus, IconX } from '../icons'

export function SettingsView() {
  const [fontes, setFontes] = useState<FonteResponse[]>([])
  const [sugestoes, setSugestoes] = useState<{ caminho: string; nome: string; total_imagens: number }[]>([])
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [msg, setMsg] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ id: '', nome: '', origem: '', destino: '' })

  const carregar = useCallback(async () => {
    setLoading(true)
    const f = await fetchFontes()
    setFontes(f)
    setLoading(false)
  }, [])

  useEffect(() => { carregar() }, [carregar])

  const handleScan = async () => {
    setScanning(true)
    setMsg('')
    try {
      const res = await fetch('/api/pastas/config/fontes/scan')
      const data = await res.json()
      setSugestoes(data.sugestoes ?? [])
      if (!data.sugestoes?.length) setMsg('Nenhuma pasta com imagens encontrada em /mnt/')
    } catch { setMsg('Erro ao escanear') }
    setScanning(false)
  }

  const handleAdd = async () => {
    if (!form.id || !form.origem) return
    setMsg('')
    try {
      const res = await fetch('/api/pastas/config/fontes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (!res.ok) { setMsg('Erro ao adicionar'); return }
      setForm({ id: '', nome: '', origem: '', destino: '' })
      setShowAdd(false)
      await carregar()
      setMsg('Fonte adicionada.')
    } catch { setMsg('Erro ao adicionar') }
  }

  const handleDelete = async (id: string) => {
    if (!confirm(`Remover fonte "${id}"?`)) return
    try {
      await fetch(`/api/pastas/config/fontes/${id}`, { method: 'DELETE' })
      await carregar()
    } catch { setMsg('Erro ao remover') }
  }

  const usarSugestao = (s: typeof sugestoes[0]) => {
    const nome = s.nome
    setForm({
      id: nome.toLowerCase().replace(/[^a-z0-9]/g, '_'),
      nome: nome,
      origem: s.caminho,
      destino: nome.toLowerCase().replace(/[^a-z0-9]/g, '_'),
    })
    setShowAdd(true)
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Configurações</h1>
        <p className="page-subtitle">Gerencie as fontes de dados (pastas de imagens).</p>
      </div>

      {msg && <p style={{ color: 'var(--success)', marginBottom: '0.75rem' }}>{msg}</p>}

      <div className="card" style={{ marginBottom: '1rem' }}>
        <div className="grid-header">
          <h3>Fontes de Dados</h3>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button className="btn btn-sm" onClick={handleScan} disabled={scanning}>
              🔍 Escanear /mnt/
            </button>
            <button className="btn btn-sm" onClick={() => setShowAdd(!showAdd)}>
              <IconPlus size={14} /> Adicionar
            </button>
          </div>
        </div>

        {loading && <p style={{ padding: '1rem 0', color: 'var(--text-muted)' }}>Carregando...</p>}

        {!loading && fontes.length === 0 && (
          <p style={{ padding: '1rem 0', color: 'var(--text-muted)' }}>
            Nenhuma fonte configurada. Clique em "Escanear /mnt/" para encontrar pastas automaticamente.
          </p>
        )}

        {!loading && fontes.length > 0 && (
          <div className="source-list" style={{ marginTop: '0.5rem' }}>
            {fontes.map((f) => (
              <div key={f.id} className="source-card" style={{ cursor: 'default' }}>
                <div className="source-card-header">
                  <strong>{f.nome}</strong>
                  <button className="btn-sm" style={{ color: 'var(--danger)' }} onClick={() => handleDelete(f.id)}>
                    <IconX size={14} />
                  </button>
                </div>
                <div className="source-card-details">
                  <span>Origem: {f.origem}</span>
                  <span>Destino: {f.destino}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {showAdd && (
        <div className="card">
          <h3>Nova Fonte</h3>
          <div className="form-grid" style={{ marginTop: '0.75rem' }}>
            <div className="form-group">
              <label>ID</label>
              <input type="text" value={form.id} onChange={(e) => setForm({ ...form, id: e.target.value })} placeholder="br364_lote_01" />
            </div>
            <div className="form-group">
              <label>Nome</label>
              <input type="text" value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} placeholder="BR364 Lote 01" />
            </div>
            <div className="form-group">
              <label>Caminho de Origem</label>
              <input type="text" value={form.origem} onChange={(e) => setForm({ ...form, origem: e.target.value })} placeholder="/mnt/hd2/..." />
            </div>
            <div className="form-group">
              <label>Pasta de Destino</label>
              <input type="text" value={form.destino} onChange={(e) => setForm({ ...form, destino: e.target.value })} placeholder="br364_lote_01" />
            </div>
          </div>
          <button className="btn btn-primary" onClick={handleAdd} disabled={!form.id || !form.origem} style={{ marginTop: '0.5rem' }}>
            Salvar Fonte
          </button>
        </div>
      )}

      {scanning && <p style={{ padding: '1rem 0', color: 'var(--text-muted)' }}>Escaneando /mnt/...</p>}

      {sugestoes.length > 0 && (
        <div className="card" style={{ marginTop: '1rem' }}>
          <h3>Sugestões encontradas em /mnt/</h3>
          <div className="source-list" style={{ marginTop: '0.5rem' }}>
            {sugestoes.map((s) => (
              <button key={s.caminho} className="source-card" onClick={() => usarSugestao(s)}>
                <div className="source-card-header">
                  <strong>{s.nome}</strong>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{s.total_imagens} imagens</span>
                </div>
                <div className="source-card-details">
                  <span>{s.caminho}</span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
