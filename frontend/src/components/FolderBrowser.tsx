import { useEffect, useState, useRef } from 'react'
import { fetchFontes } from '../services/api'
import type { FonteResponse } from '../services/api'
import { IconChevronRight } from '../icons'

interface FolderBrowserProps {
  onSelect: (caminho: string) => void
}

export function FolderBrowser({ onSelect }: FolderBrowserProps) {
  const [fontes, setFontes] = useState<FonteResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [manualPath, setManualPath] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setLoading(true)
    fetchFontes()
      .then(setFontes)
      .catch(() => setError('Não foi possível carregar as fontes de dados.'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="folder-browser">
      <div className="form-group">
        <label>Fonte de Dados</label>
        <p className="page-subtitle">Selecione uma fonte configurada ou digite o caminho manualmente.</p>
      </div>

      {error && <div className="folder-error">{error}</div>}

      <div className="folder-content">
        {loading && <div className="folder-loading">Carregando fontes...</div>}

        {!loading && fontes.length > 0 && (
          <>
            <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.4rem', display: 'block' }}>
              Fontes configuradas
            </label>
            <div className="source-list">
              {fontes.map((fonte) => (
                <button
                  key={fonte.id}
                  className="source-card"
                  onClick={() => onSelect(fonte.origem)}
                >
                  <div className="source-card-header">
                    <strong>{fonte.nome}</strong>
                    <IconChevronRight size={16} />
                  </div>
                  <div className="source-card-details">
                    <span>Origem: {fonte.origem}</span>
                    <span>Destino: {fonte.destino}</span>
                  </div>
                </button>
              ))}
            </div>
          </>
        )}

        {!loading && fontes.length === 0 && (
          <div className="folder-empty">
            Nenhuma fonte configurada. Adicione entradas em <code>sources.json</code> ou digite o caminho abaixo.
          </div>
        )}

        <div className="form-group" style={{ marginTop: '1rem' }}>
          <label>Caminho manual</label>
          <div className="path-bar">
            <input
              ref={inputRef}
              type="text"
              value={manualPath}
              onChange={(e) => setManualPath(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && manualPath.trim()) {
                  onSelect(manualPath.trim())
                }
              }}
              placeholder="/mnt/dados/imagens/..."
              className="path-input"
            />
            <button
              className="btn-ir"
              disabled={!manualPath.trim()}
              onClick={() => onSelect(manualPath.trim())}
            >
              Usar
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
