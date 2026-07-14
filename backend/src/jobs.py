from __future__ import annotations

from pathlib import Path

from rq import get_current_job

from src.core.config import get_settings
from src.services.image_processor import processar_pasta, LARGURA_PX
from src.services.inference_pipeline import InferencePipeline
from src.services.model_loader import listar_modelos


def _set_progress(current: int, total: int, message: str) -> None:
    job = get_current_job()
    if job is not None:
        meta = job.get_meta()
        meta["current_lote"] = current
        meta["total_lotes"] = total
        meta["progress_msg"] = message
        job.meta = meta
        job.save()


def processar_imagens_job(
    pasta_origem: str,
    viagem_nome: str,
    km_inicial: float | None = None,
    km_final: float | None = None,
    tipo_pista: str = "simples",
    sentido: str = "crescente",
    faixa: int | None = None,
) -> dict:
    import json as _json
    settings = get_settings()
    origem = Path(pasta_origem)
    destino = settings.dados_dir / viagem_nome

    config = {
        "nome": viagem_nome,
        "km_inicial": km_inicial,
        "km_final": km_final,
        "tipo_pista": tipo_pista,
        "sentido": sentido,
        "faixa": faixa,
    }
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "viagem_config.json").write_text(_json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    max_batches = None
    if km_inicial is not None and km_final is not None:
        distancia_km = abs(float(km_final) - float(km_inicial))
        distancia_m = distancia_km * 1000
        max_batches = max(1, int(distancia_m // 20))

    lotes = processar_pasta(
        origem, destino,
        km_inicial=km_inicial,
        sentido=sentido,
        tipo_pista=tipo_pista,
        faixa=faixa,
        max_batches=max_batches,
        modelo_lane=settings.modelos_dir / "lane" / "best.pt" if (settings.modelos_dir / "lane" / "best.pt").exists() else None,
    )

    return {
        "total_lotes": len(lotes),
        "lotes": lotes,
        "destino": str(destino),
    }


def processar_inferencia_job(
    viagem_nome: str,
    tipo_modelo: str = "igg",
    tipo_pista: str = "simples",
    sentido: str = "crescente",
    faixa: int | None = None,
) -> dict:
    settings = get_settings()
    destino = settings.dados_dir / viagem_nome
    modelos = listar_modelos(settings.modelos_dir)
    modelo_info = next((m for m in modelos if m.tipo == tipo_modelo), None)
    if modelo_info is None:
        raise ValueError(f"Modelo '{tipo_modelo}' não encontrado")

    cfg = modelo_info.config
    pipeline = InferencePipeline(
        modelos_dir=modelo_info.pasta,
        input_folder=destino,
        output_folder=destino,
        sub_modelos=[m.model_dump() for m in cfg.modelos] if cfg.modelos else [],
        area_minima=cfg.area_minima,
    )
    resultado = pipeline.run(
        tipo_pista=tipo_pista,
        sentido=sentido,
        faixa=faixa,
        progress_callback=_set_progress,
    )

    return {
        "viagem": viagem_nome,
        "total_imagens": len(resultado),
        "arquivo_saida": str(destino / "analise_completa.json"),
    }
