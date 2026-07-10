# RDT01 — Análise de Patologias de Pavimento

Sistema para análise de patologias de pavimento asfáltico com modelos YOLO (PT/ONNX), edição manual de detecções por anotação de bbox, cálculo de IGG (DNIT 006/2003-PRO) e importação de dados de perfilômetro.

## Requisitos

- **Docker** + **Docker Compose**
- **NVIDIA GPU** com drivers e **NVIDIA Container Toolkit**
- Pelo menos **30 GB livres** em disco para dados de processamento

## Estrutura

```
rdt01/
├── backend/                 # FastAPI (Python 3.12)
│   ├── src/                 # Código fonte da API
│   ├── Dockerfile
│   └── requirements.txt     # Dependências GPU
├── frontend/                # React/TypeScript (Vite)
│   ├── src/                 # Código fonte
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml
├── sources.json             # Fontes de dados (pastas de imagens)
└── modelos/
    └── igg/
        ├── config.json
        ├── trincas.pt       # Modelo treinado (~6 MB)
        └── panela_remendo.pt
```

**Fora do repositório** (pastas montadas como volume no container):

```
../dados/          → imagens processadas, resultados, parâmetros
../modelos/        → modelos .onnx (se houver)
../Referencias/    → PDFs, planilhas de referência
```

## Primeira execução

```bash
git clone <url-do-repo> rdt01
cd rdt01

# Ajuste sources.json com o caminho das pastas de imagens
# Certifique-se de que ../dados, ../modelos, ../Referencias existem

docker compose up -d --build
```

- **Frontend:** http://localhost:5173
- **Backend:** http://localhost:8000
- **Redis** e **Worker** sobem automaticamente

## Uso

1. Acesse http://localhost:5173
2. Selecione **IGG** na tela inicial
3. Configure a viagem (KM inicial/final, tipo de pista, sentido)
4. Selecione a **fonte de dados** (definida em `sources.json`)
5. Acompanhe o processamento na tela de **Processamentos**
6. Após concluído, vá em **Análise** para revisar e editar detecções
7. Importe planilha de perfilômetro para obter dados TRI/TRE
8. O **IGG** é calculado automaticamente a cada edição
9. Exporte o CSV final com o botão **Exportar**
