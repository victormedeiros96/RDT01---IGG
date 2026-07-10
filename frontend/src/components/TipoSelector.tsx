import { fetchModelos } from '../services/api'
import { useEffect, useState } from 'react'
import type { ModeloInfo } from '../types'
import { useAppStore } from '../store'
import { IconBrain, IconImage } from '../icons'

export function TipoSelector() {
  const setAnalysisType = useAppStore((s) => s.setAnalysisType)
  const [modelos, setModelos] = useState<ModeloInfo[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchModelos()
      .then((data) => setModelos(data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const iggModels = modelos.filter((m) => m.tipo === 'igg')
  const icpModels = modelos.filter((m) => m.tipo === 'icp')

  return (
    <div className="tipo-selector">
      <header className="selector-header">
        <h1>RDT01</h1>
        <p className="subtitulo">Selecione o tipo de análise de patologias de pavimento</p>
      </header>

      {loading ? (
        <div className="spinner" />
      ) : (
        <div className="cartoes">
          <div
            className="cartao"
            style={{ '--cor-accent': '#6366f1' } as React.CSSProperties}
            onClick={() => iggModels[0] && setAnalysisType('igg', iggModels[0])}
          >
            <span className="cartao-icone"><IconBrain size={40} /></span>
            <h2>IGG</h2>
            <p>Índice de Gravidade Global — análise estrutural do pavimento com base no retigráfico.</p>
            {iggModels.length > 0 && (
              <span className="cartao-modelo">
                {iggModels.length} modelo{iggModels.length > 1 ? 's' : ''} disponíve{iggModels.length > 1 ? 'is' : 'l'}
              </span>
            )}
          </div>

          <div
            className="cartao"
            style={{ '--cor-accent': '#10b981' } as React.CSSProperties}
            onClick={() => icpModels[0] && setAnalysisType('icp', icpModels[0])}
          >
            <span className="cartao-icone"><IconImage size={40} /></span>
            <h2>ICP</h2>
            <p>Índice de Condição do Pavimento — avaliação superficial por trechos homogêneos.</p>
            {icpModels.length > 0 && (
              <span className="cartao-modelo">
                {icpModels.length} modelo{icpModels.length > 1 ? 's' : ''} disponíve{icpModels.length > 1 ? 'is' : 'l'}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
