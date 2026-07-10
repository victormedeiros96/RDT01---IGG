# RDT01 - Sistema de Análise de Patologias de Pavimento

Sistema para análise de patologias asfálticas utilizando IA diretamente no browser (WebGPU via ONNX Runtime Web) e geração de relatórios IGG/ICP.

## Estrutura

```
backend/         # API FastAPI (Python 3.12)
frontend/        # SPA React + TypeScript + Vite
modelos/         # Pesos dos modelos ONNX organizados por tipo
  igg/           #   Modelos para cálculo IGG
  icp/           #   Modelos para cálculo ICP
dados/           # Dados dos projetos (montado como volume)
```

## Execução

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Health check: http://localhost:8000/health

## Funcionalidades (planejadas)

- [ ] Carregamento de modelos ONNX com WebGPU no browser
- [ ] Processamento de imagens linescan do pavimento
- [ ] Editor de grid interativo (retigráfico)
- [ ] Cálculo IGG (Índice de Gravidade Global)
- [ ] Cálculo ICP (Índice de Condição do Pavimento)
- [ ] Exportação para planilha ANTT
- [ ] Suporte a múltiplos projetos
