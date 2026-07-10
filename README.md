# RDT01 — Análise de Patologias de Pavimento

Sistema para análise de patologias de pavimento asfáltico com suporte a modelos YOLO (PT/ONNX), edição manual de detecções por anotação de bbox, cálculo de IGG (DNIT 006/2003-PRO) e importação de dados de perfilômetro.

## Estrutura do Projeto

```
rdt01/
├── backend/          # FastAPI (Python 3.12)
│   ├── src/
│   │   ├── api/      # Rotas REST
│   │   ├── core/     # Config, dependências
│   │   ├── models/   # Modelos de dados
│   │   └── services/ # Lógica de negócio
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/         # React/TypeScript (Vite)
│   ├── src/
│   │   ├── components/
│   │   ├── services/
│   │   └── types/
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml
├── sources.json      # Fontes de dados (pastas de imagens)
└── modelos/          # Config dos modelos (pesos .pt/.onnx ficam fora)
```

## Pré-requisitos

- Docker e Docker Compose
- NVIDIA CUDA (para GPU)
- Modelos .pt/.onnx em `../modelos/igg/` (fora do repositório)
- Dados de processamento em `../dados/` (fora do repositório)

## Configuração

1. Edite `sources.json` com as pastas de dados
2. Coloque os modelos .pt em `../modelos/igg/`
3. Ajuste `docker-compose.yml` se necessário

## Execução

```bash
cd rdt01
docker compose up -d --build
```

- Backend: http://localhost:8000
- Frontend: http://localhost:5173
