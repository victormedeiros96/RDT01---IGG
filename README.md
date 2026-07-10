# RDT01 — Análise de Patologias de Pavimento

Sistema para análise de patologias de pavimento asfáltico com suporte a modelos YOLO (PT/ONNX), edição manual de detecções por anotação de bbox, cálculo de IGG (DNIT 006/2003-PRO) e importação de dados de perfilômetro.

## Estrutura do Projeto

```
rdt01/
├── backend/                 # FastAPI (Python 3.12)
│   ├── src/
│   │   ├── api/             # Rotas REST
│   │   ├── core/            # Config, dependências
│   │   ├── models/          # Modelos de dados
│   │   └── services/        # Lógica de negócio
│   ├── Dockerfile
│   ├── requirements.txt     # Dependências GPU (Linux/Docker)
│   └── requirements-cpu.txt # Dependências CPU (Windows/sem GPU)
├── frontend/                # React/TypeScript (Vite)
│   ├── src/
│   │   ├── components/
│   │   ├── services/
│   │   └── types/
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml
├── sources.json             # Fontes de dados (pastas de imagens)
└── modelos/
    └── igg/
        ├── config.json
        ├── trincas.pt       # Modelo treinado
        └── panela_remendo.pt
```

## Pré-requisitos

- **Linux (recomendado):** Docker, Docker Compose, NVIDIA CUDA + Container Toolkit
- **Windows:** Node.js 22+, Python 3.12+, Redis (ou WSL2)

## Build e Execução

### Linux — Docker (com GPU)

```bash
cd rdt01
docker compose up -d --build
```

- Backend: http://localhost:8000
- Frontend: http://localhost:5173

### Windows / sem GPU — nativo

**Redis:**
```bash
# Opção 1: Docker Desktop (recomendado)
docker run -d -p 6379:6379 redis:7-alpine

# Opção 2: WSL2
wsl --install -d Ubuntu
sudo apt install redis-server
redis-server

# Opção 3: Memurai (Windows nativo)
# Baixe em https://www.memurai.com/
```

**Backend:**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements-cpu.txt
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev                  # http://localhost:5173
```

### Windows — Docker Desktop

```bash
cd rdt01
docker compose up -d --build
```

> **Nota:** No Windows, o Docker Desktop não suporta GPU nativamente.
> Use o modo nativo (acima) para desenvolvimento local com CPU.

## Configuração

1. Edite `sources.json` com as pastas de dados
2. Os dados de processamento e referências ficam em `../dados/` e `../Referencias/` (fora do repositório)
3. Ajuste `docker-compose.yml` se os caminhos das pastas forem diferentes

## Dependências

### GPU (Docker Linux) — `requirements.txt`
- `onnxruntime-gpu`, `torch` (compilado CUDA), `ultralytics`

### CPU (Windows/sem GPU) — `requirements-cpu.txt`
- `onnxruntime`, `torch` (CPU), `ultralytics`
