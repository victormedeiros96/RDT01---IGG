from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from redis import Redis
from rq import Queue

from src.core.config import Settings
from src.core.dependencies import get_settings_dep

router = APIRouter(prefix="/api/pastas", tags=["pastas"])


@router.get("/config/fontes")
async def listar_fontes(settings: Settings = Depends(get_settings_dep)):
    import json as _json
    path = settings.sources_config
    if not path.is_file():
        return {"fontes": []}
    try:
        data = _json.loads(path.read_text(encoding="utf-8"))
        return {"fontes": data.get("fontes", [])}
    except Exception:
        return {"fontes": []}


@router.get("/config/fontes/scan")
async def scan_fontes(settings: Settings = Depends(get_settings_dep)):
    """Escaneia /mnt/ em busca de pastas com imagens, até 3 níveis de profundidade."""
    sugestoes: list[dict] = []

    def _scan_dir(base: Path, depth: int = 0):
        if depth > 3:
            return
        if not base.is_dir():
            return
        try:
            for p in sorted(base.iterdir()):
                if not p.is_dir():
                    continue
                # Verifica se tem imagens direto ou subpasta left/
                for candidate in [p, p / "left"]:
                    if not candidate.is_dir():
                        continue
                    imgs = list(candidate.glob("*.[jJ][pP][gG]")) + list(candidate.glob("*.[pP][nN][gG]"))
                    if imgs:
                        sugestoes.append({
                            "caminho": str(p),
                            "nome": p.name,
                            "total_imagens": len(imgs),
                        })
                        break
                else:
                    _scan_dir(p, depth + 1)
        except PermissionError:
            pass

    _scan_dir(Path("/mnt"))
    sugestoes.sort(key=lambda s: s["nome"])
    return {"sugestoes": sugestoes}


@router.post("/config/fontes")
async def adicionar_fonte(body: dict, settings: Settings = Depends(get_settings_dep)):
    import json as _json
    path = settings.sources_config

    fontes: list[dict] = []
    if path.is_file():
        try:
            fontes = _json.loads(path.read_text(encoding="utf-8")).get("fontes", [])
        except Exception:
            fontes = []

    nova = {
        "id": body.get("id", ""),
        "nome": body.get("nome", ""),
        "origem": body.get("origem", ""),
        "destino": body.get("destino", ""),
    }
    if not nova["id"] or not nova["origem"]:
        raise HTTPException(400, "Campos 'id' e 'origem' são obrigatórios")

    # Remove duplicata se existir
    fontes = [f for f in fontes if f.get("id") != nova["id"]]
    fontes.append(nova)

    path.write_text(_json.dumps({"fontes": fontes}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "ok", "fonte": nova}


@router.delete("/config/fontes/{fonte_id}")
async def remover_fonte(fonte_id: str, settings: Settings = Depends(get_settings_dep)):
    import json as _json
    path = settings.sources_config
    if not path.is_file():
        raise HTTPException(404, "Nenhuma fonte configurada")

    fontes: list[dict] = []
    try:
        fontes = _json.loads(path.read_text(encoding="utf-8")).get("fontes", [])
    except Exception:
        raise HTTPException(500, "Erro ao ler configuração")

    novas = [f for f in fontes if f.get("id") != fonte_id]
    if len(novas) == len(fontes):
        raise HTTPException(404, f"Fonte '{fonte_id}' não encontrada")

    path.write_text(_json.dumps({"fontes": novas}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "ok", "removida": fonte_id}

EXTENSOES_IMAGEM = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
JOBS_LIST_KEY = "rdt01:jobs"


def _get_redis(settings: Settings) -> Redis:
    return Redis.from_url(settings.redis_url)


def _get_queue(settings: Settings) -> Queue:
    return Queue("rdt01-processing", connection=_get_redis(settings))


@router.get("/listar")
async def listar_conteudo(
    caminho: str = Query("", description="Caminho da pasta a listar"),
    settings: Settings = Depends(get_settings_dep),
):
    if not caminho:
        raizes: list[dict] = []
        for p in Path("/").iterdir():
            if p.is_dir():
                raizes.append({"nome": p.name, "caminho": str(p), "tipo": "pasta"})
        return {"atual": "/", "pastas": raizes, "arquivos": []}

    path = Path(caminho)
    if not path.exists():
        raise HTTPException(404, "Pasta não encontrada")
    if not path.is_dir():
        raise HTTPException(400, "Caminho informado não é uma pasta")

    try:
        pastas: list[dict] = []
        arquivos: list[dict] = []

        for entry in sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            info = {"nome": entry.name, "caminho": str(entry.absolute())}
            if entry.is_dir():
                info["tipo"] = "pasta"
                pastas.append(info)
            elif entry.is_file() and entry.suffix.lower() in EXTENSOES_IMAGEM:
                info["tipo"] = "imagem"
                info["tamanho"] = entry.stat().st_size
                arquivos.append(info)

        return {
            "atual": str(path.absolute()),
            "pai": str(path.parent) if path.parent != path else None,
            "pastas": pastas,
            "arquivos": arquivos,
        }
    except PermissionError:
        raise HTTPException(403, "Sem permissão para acessar esta pasta")


@router.post("/processar")
async def processar_imagens(
    body: dict,
    settings: Settings = Depends(get_settings_dep),
):
    pasta_origem = body.get("pasta_origem", "")
    viagem_nome = body.get("viagem_nome", "sem_nome")
    km_inicial = body.get("km_inicial")
    km_final = body.get("km_final")
    tipo_pista = body.get("tipo_pista", "simples")
    sentido = body.get("sentido", "crescente")
    faixa = body.get("faixa")

    if not pasta_origem:
        raise HTTPException(400, "Campo 'pasta_origem' é obrigatório")

    origem = Path(pasta_origem)
    if not origem.is_dir():
        raise HTTPException(404, f"Pasta não encontrada: {pasta_origem}")

    queue = _get_queue(settings)
    job = queue.enqueue(
        "src.jobs.processar_imagens_job",
        pasta_origem=str(origem),
        viagem_nome=viagem_nome,
        km_inicial=km_inicial,
        km_final=km_final,
        tipo_pista=tipo_pista,
        sentido=sentido,
        faixa=faixa,
        job_timeout=3600,
        meta={
            "viagem": viagem_nome,
            "pasta": str(origem),
            "km_inicial": km_inicial,
            "km_final": km_final,
            "tipo_pista": tipo_pista,
            "sentido": sentido,
            "faixa": faixa,
        },
    )

    r = _get_redis(settings)
    r.lpush(JOBS_LIST_KEY, job.id)
    r.ltrim(JOBS_LIST_KEY, 0, 49)

    return {"status": "queued", "job_id": job.id}


@router.get("/status/{job_id}")
async def job_status(job_id: str, settings: Settings = Depends(get_settings_dep)):
    queue = _get_queue(settings)
    try:
        job = queue.fetch_job(job_id)
    except Exception:
        raise HTTPException(404, "Job não encontrado")

    if job is None:
        raise HTTPException(404, "Job não encontrado")

    result: dict = {"status": job.get_status()}

    if job.is_finished:
        result["resultado"] = job.result
        if job.result:
            if "lotes" in job.result:
                result["total_lotes"] = len(job.result["lotes"])
            elif "total_imagens" in job.result:
                result["total_imagens"] = job.result["total_imagens"]
    elif job.is_failed:
        result["error"] = str(job.exc_info)

    return result


@router.get("/jobs")
async def listar_jobs(settings: Settings = Depends(get_settings_dep)):
    r = _get_redis(settings)
    queue = _get_queue(settings)
    raw_ids = r.lrange(JOBS_LIST_KEY, 0, 49)
    job_ids = [jid.decode("utf-8") for jid in raw_ids]

    jobs: list[dict] = []
    for jid in job_ids:
        job = queue.fetch_job(jid)
        if job is None:
            continue
        entry: dict = {
            "job_id": job.id,
            "status": job.get_status(),
            "meta": job.meta,
            "progress": {
                "current_lote": job.meta.get("current_lote"),
                "total_lotes": job.meta.get("total_lotes"),
                "progress_msg": job.meta.get("progress_msg"),
            } if job.meta else None,
            "criado_em": job.created_at.isoformat() if job.created_at else None,
            "tempo_total": job.enqueued_at.isoformat() if job.enqueued_at else None,
        }
        if job.is_finished:
            entry["resultado"] = job.result
        elif job.is_failed:
            entry["error"] = str(job.exc_info)
        jobs.append(entry)

    return jobs


@router.get("/faixas/{viagem_nome}")
async def listar_faixas(viagem_nome: str, settings: Settings = Depends(get_settings_dep)):
    """Lista todas as faixas de 5m de uma viagem com seus metadados."""
    base = settings.dados_dir / viagem_nome
    if not base.is_dir():
        raise HTTPException(404, f"Viagem não encontrada: {viagem_nome}")

    import json as _json

    meta_files = sorted(base.glob("lote_*_meta.json"))
    faixas: list[dict] = []

    for meta_path in meta_files:
        try:
            meta = _json.loads(meta_path.read_text(encoding="utf-8"))
            bloco = meta.get("bloco", {})
            for faixa in meta.get("faixas", []):
                faixa["_bloco"] = bloco
                faixas.append(faixa)
        except Exception:
            continue

    return {
        "viagem": viagem_nome,
        "total_faixas": len(faixas),
        "faixas": faixas,
    }


@router.get("/faixa/{viagem_nome}/{arquivo}")
async def servir_faixa(viagem_nome: str, arquivo: str, settings: Settings = Depends(get_settings_dep)):
    """Serve uma faixa de 5m (PNG)."""
    caminho = settings.dados_dir / viagem_nome / arquivo
    if not caminho.is_file():
        raise HTTPException(404, "Faixa não encontrada")
    return FileResponse(str(caminho), media_type="image/png")


@router.get("/meta/{viagem_nome}/{bloco_indice}")
async def obter_meta_bloco(viagem_nome: str, bloco_indice: int, settings: Settings = Depends(get_settings_dep)):
    """Retorna os metadados de um bloco específico."""
    import json as _json

    base = settings.dados_dir / viagem_nome
    meta_path = base / f"lote_{bloco_indice:04d}_meta.json"
    if not meta_path.is_file():
        raise HTTPException(404, "Metadados não encontrados para este bloco")

    try:
        meta = _json.loads(meta_path.read_text(encoding="utf-8"))
        return meta
    except Exception as e:
        raise HTTPException(500, f"Erro ao ler metadados: {e}")


@router.post("/analisar/{viagem_nome}")
async def iniciar_inferencia(
    viagem_nome: str,
    body: dict = {},
    settings: Settings = Depends(get_settings_dep),
):
    tipo_modelo = body.get("tipo_modelo", "igg")
    tipo_pista = body.get("tipo_pista", "simples")
    sentido = body.get("sentido", "crescente")
    faixa = body.get("faixa")
    destino = settings.dados_dir / viagem_nome
    if not destino.is_dir():
        raise HTTPException(404, f"Viagem não encontrada: {viagem_nome}")
    queue = _get_queue(settings)
    job = queue.enqueue(
        "src.jobs.processar_inferencia_job",
        viagem_nome=viagem_nome,
        tipo_modelo=tipo_modelo,
        tipo_pista=tipo_pista,
        sentido=sentido,
        faixa=faixa,
        job_timeout=7200,
        meta={
            "viagem": viagem_nome,
            "tipo_modelo": tipo_modelo,
            "tipo_pista": tipo_pista,
            "sentido": sentido,
            "faixa": faixa,
        },
    )
    r = _get_redis(settings)
    r.lpush(JOBS_LIST_KEY, job.id)
    r.ltrim(JOBS_LIST_KEY, 0, 49)
    return {"status": "queued", "job_id": job.id}

@router.get("/analise/{viagem_nome}")
async def obter_analise(viagem_nome: str, settings: Settings = Depends(get_settings_dep)):
    import json as _json
    import re as _re

    base = settings.dados_dir / viagem_nome
    json_path = base / "analise_completa.json"
    if not json_path.is_file():
        raise HTTPException(404, "Análise ainda não realizada para esta viagem")

    config_path = base / "viagem_config.json"
    viagem_config: dict = {}
    if config_path.is_file():
        viagem_config = _json.loads(config_path.read_text(encoding="utf-8"))

    # Normaliza campo tipo_faixa -> tipo_pista (compatibilidade com versões antigas)
    if "tipo_faixa" in viagem_config and "tipo_pista" not in viagem_config:
        viagem_config["tipo_pista"] = viagem_config.pop("tipo_faixa")

    analise: dict = _json.loads(json_path.read_text(encoding="utf-8"))
    parametros_path = base / "parametros_adicionais.json"
    parametros_por_km = {}
    if parametros_path.is_file():
        try:
            parametros_por_km = _json.loads(parametros_path.read_text(encoding="utf-8"))
        except Exception:
            parametros_por_km = {}

    def _faixa_num(nome: str) -> int:
        """Extrai o índice numérico do nome da faixa (ex: lote_0000_faixa_2.png -> 2)."""
        digits = _re.findall(r"\d+", nome)
        return int(digits[-1]) if digits else 0

    def _bloco_num(nome: str) -> int:
        """Extrai o índice do bloco do nome (ex: lote_0003_faixa_1.png -> 3)."""
        match = _re.search(r"lote_(\d+)", nome)
        return int(match.group(1)) if match else 0

    # Ordena faixas por bloco + índice
    faixas_ordenadas = sorted(analise.keys(), key=lambda n: (_bloco_num(n), _faixa_num(n)))

    imagens = []
    for seq_idx, nome in enumerate(faixas_ordenadas):
        dados = analise[nome]
        # Compatibilidade: formato antigo (lista) vs novo (dict com deteccoes + faixa_meta)
        if isinstance(dados, list):
            deteccoes = dados
            faixa_meta = None
        else:
            deteccoes = dados.get("deteccoes", [])
            faixa_meta = dados.get("faixa_meta")

        img_path = base / nome
        existe = img_path.is_file()

        # Calcula KM a partir dos metadados da faixa
        km = None
        if faixa_meta:
            km = faixa_meta.get("km_inicio")
        elif viagem_config.get("km_inicial") is not None:
            bloco_idx = _bloco_num(nome)
            faixa_idx = _faixa_num(nome)
            km_por_faixa = 0.005
            km_por_bloco = 0.020
            km = viagem_config["km_inicial"]
            if viagem_config.get("sentido") == "decrescente":
                km -= bloco_idx * km_por_bloco + faixa_idx * km_por_faixa
            else:
                km += bloco_idx * km_por_bloco + faixa_idx * km_por_faixa

        # Carrega ROI da faixa (lane detection)
        lane_roi = None
        bloco_idx_lane = _bloco_num(nome)
        lane_path = base / f"lote_{bloco_idx_lane:04d}_lane.json"
        if lane_path.is_file():
            try:
                lane_roi = _json.loads(lane_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        imagens.append({
            "arquivo": nome,
            "bloco_index": _bloco_num(nome),
            "faixa_index": _faixa_num(nome),
            "lote_index": seq_idx,
            "km": km,
            "existe_imagem": existe,
            "total_deteccoes": len(deteccoes),
            "deteccoes": deteccoes,
            "lane_roi": lane_roi,
        })

    return {
        "viagem": viagem_nome,
        "config": viagem_config,
        "total_imagens": len(imagens),
        "imagens": imagens,
        "parametros_por_km": parametros_por_km,
    }


@router.post("/analise/{viagem_nome}/salvar")
async def salvar_analise_editada(
    viagem_nome: str,
    body: dict,
    settings: Settings = Depends(get_settings_dep),
):
    import json as _json

    base = settings.dados_dir / viagem_nome
    json_path = base / "analise_completa.json"
    if not json_path.is_file():
        raise HTTPException(404, "Análise ainda não realizada para esta viagem")

    deteccoes_por_imagem = body.get("deteccoes_por_imagem")
    if not isinstance(deteccoes_por_imagem, dict):
        raise HTTPException(400, "Campo 'deteccoes_por_imagem' é obrigatório")

    analise: dict = _json.loads(json_path.read_text(encoding="utf-8"))

    atualizadas = 0
    for nome, deteccoes in deteccoes_por_imagem.items():
        if nome not in analise or not isinstance(deteccoes, list):
            continue
        dados = analise[nome]
        if isinstance(dados, list):
            analise[nome] = deteccoes
        else:
            dados["deteccoes"] = deteccoes
            analise[nome] = dados
        atualizadas += 1

    json_path.write_text(_json.dumps(analise, ensure_ascii=False, indent=2), encoding="utf-8")

    parametros_por_km = body.get("parametros_por_km")
    parametros_atualizados = 0
    if isinstance(parametros_por_km, dict):
        parametros_path = base / "parametros_adicionais.json"
        parametros_path.write_text(_json.dumps(parametros_por_km, ensure_ascii=False, indent=2), encoding="utf-8")
        parametros_atualizados = len(parametros_por_km)

    return {
        "status": "ok",
        "imagens_atualizadas": atualizadas,
        "parametros_atualizados": parametros_atualizados,
    }


@router.delete("/analise/{viagem_nome}")
async def deletar_analise(
    viagem_nome: str,
    settings: Settings = Depends(get_settings_dep),
):
    import shutil

    base = settings.dados_dir / viagem_nome
    if not base.is_dir():
        raise HTTPException(404, f"Viagem não encontrada: {viagem_nome}")

    shutil.rmtree(base)
    return {"status": "ok", "viagem": viagem_nome}
