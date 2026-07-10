import { useEffect, useState } from 'react'
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

  useEffect(() => {
    setLoading(true)
    fetchFontes()
      .then((data) => setFontes(data))
      .catch(() => setError('Não foi possível carregar as fontes de dados.'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="folder-browser">
      <div className="form-group">
        <label>Fonte de Dados</label>
        <p className="page-subtitle">Selecione a pasta de imagens linescan do trecho a analisar.</p>
      </div>

      {error && <div className="folder-error">{error}</div>}

      <div className="folder-content">
        {loading && <div className="folder-loading">Carregando fontes...</div>}

        {!loading && fontes.length === 0 && (
          <div className="folder-empty">
            Nenhuma fonte configurada. Adicione entradas em <code>sources.json</code>.
          </div>
        )}

        {!loading && fontes.length > 0 && (
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
        )}
      </div>
    </div>
  )
}
