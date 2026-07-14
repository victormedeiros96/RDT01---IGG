import { useEffect, useState } from 'react'
import { listarViagens } from '../services/api'
import type { ViagemResumo } from '../services/api'
import { useAppStore } from '../store'
import { IconChevronRight, IconDownload, IconEye, IconArrowDown } from '../icons'

function normalize(c: string): string {
  return c.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
}

export function ReportsView() {
  const setCurrentView = useAppStore((s) => s.setCurrentView)
  const setViagemAnaliseNome = useAppStore((s) => s.setViagemAnaliseNome)
  const [viagens, setViagens] = useState<ViagemResumo[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [exporting, setExporting] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    listarViagens()
      .then(setViagens)
      .catch(() => setViagens([]))
      .finally(() => setLoading(false))
  }, [])

  const handleExport = async (viagem: string) => {
    setExporting(viagem)
    try {
      const res = await fetch(`/api/relatorios/exportar/${viagem}`, { method: 'POST' })
      if (!res.ok) return
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `igg_${viagem}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch { /* silent */ }
    setExporting(null)
  }

  const handleAnalise = (viagem: string) => {
    setViagemAnaliseNome(viagem)
    setCurrentView('analise')
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Relatórios</h1>
        <p className="page-subtitle">Resumo do IGG por viagem processada.</p>
      </div>

      {loading && <div className="reports-loading">Carregando...</div>}

      {!loading && viagens.length === 0 && (
        <div className="reports-empty">
          Nenhuma viagem processada encontrada.
        </div>
      )}

      {!loading && viagens.length > 0 && (
        <div className="reports-table-wrapper">
          <table className="reports-table">
            <thead>
              <tr>
                <th></th>
                <th>Viagem</th>
                <th>Trecho</th>
                <th>KMs</th>
                <th>IGG Médio</th>
                <th>Conceito</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {viagens.map((v) => (
                <>
                  <tr
                    key={v.viagem}
                    className="reports-row"
                    onClick={() => setExpanded(expanded === v.viagem ? null : v.viagem)}
                  >
                    <td className="reports-expand-cell">
                      {expanded === v.viagem ? <IconArrowDown size={16} /> : <IconChevronRight size={16} />}
                    </td>
                    <td className="reports-name">{v.viagem}</td>
                    <td>{v.config.km_inicial} → {v.config.km_final ?? '?'}</td>
                    <td>{v.total_kms}</td>
                    <td className="reports-igg-value">{v.igg_medio.toFixed(1)}</td>
                    <td>
                      <span className={`reports-badge concept-${normalize(v.conceito_medio)}`}>
                        {v.conceito_medio}
                      </span>
                    </td>
                    <td className="reports-actions">
                      <button
                        className="btn-sm"
                        onClick={(e) => { e.stopPropagation(); handleExport(v.viagem) }}
                        disabled={exporting === v.viagem}
                        title="Exportar CSV"
                      >
                        <IconDownload size={14} />
                      </button>
                      <button
                        className="btn-sm"
                        onClick={(e) => { e.stopPropagation(); handleAnalise(v.viagem) }}
                        title="Ver Análise"
                      >
                        <IconEye size={14} />
                      </button>
                    </td>
                  </tr>
                  {expanded === v.viagem && (
                    <tr key={`${v.viagem}-detail`} className="reports-detail-row">
                      <td colSpan={7}>
                        <div className="reports-detail">
                          <table className="reports-detail-table">
                            <thead>
                              <tr>
                                <th>KM</th>
                                <th>IGG</th>
                                <th>Conceito</th>
                              </tr>
                            </thead>
                            <tbody>
                              {v.igg_por_km.map((km) => (
                                <tr key={km.km}>
                                  <td>{km.km} → {km.km + 1}</td>
                                  <td className="reports-igg-value">{km.igg.toFixed(1)}</td>
                                  <td>
                                    <span className={`reports-badge-sm concept-${normalize(km.conceito)}`}>
                                      {km.conceito}
                                    </span>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          <div className="reports-detail-meta">
                            <span>{v.total_imagens} imagens analisadas</span>
                            <span>Sentido: {v.config.sentido}</span>
                            <span>Pista: {v.config.tipo_pista}{v.config.faixa ? ` Faixa ${v.config.faixa}` : ''}</span>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
