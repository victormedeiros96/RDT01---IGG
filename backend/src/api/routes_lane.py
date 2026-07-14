from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

from src.core.config import Settings
from src.core.dependencies import get_settings_dep
from src.services.lane_calibrate import segmentar_ponto, CalibracaoFaixa
from src.services.lane_roi import calibration as C

router = APIRouter(prefix="/api/lane", tags=["lane"])


@router.post("/segmentar-ponto")
async def segmentar_ponto_endpoint(
    file: UploadFile = File(...),
    px: int = Form(...),
    py: int = Form(...),
):
    """Recebe uma imagem e um ponto (px,py), retorna máscara FastSAM."""
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(400, "Imagem inválida")

    resultado = segmentar_ponto(img, px, py)
    if not resultado.get("success"):
        raise HTTPException(400, resultado.get("error", "Falha na segmentação"))

    return resultado


@router.post("/calibrar/{viagem_nome}")
async def calibrar_faixa(
    viagem_nome: str,
    body: dict,
    settings: Settings = Depends(get_settings_dep),
):
    """Salva calibração da faixa para uma viagem."""
    base = settings.dados_dir / viagem_nome
    if not base.is_dir():
        raise HTTPException(404, f"Viagem não encontrada: {viagem_nome}")

    left_m = body.get("left_center_m")
    right_m = body.get("right_center_m")
    if left_m is None or right_m is None:
        raise HTTPException(400, "Campos 'left_center_m' e 'right_center_m' obrigatórios")

    cal = CalibracaoFaixa(base)
    dados = cal.salvar(left_m, right_m)
    return {"status": "ok", "calibracao": dados}


@router.get("/calibracao/{viagem_nome}")
async def obter_calibracao(
    viagem_nome: str,
    settings: Settings = Depends(get_settings_dep),
):
    """Retorna a calibração salva para uma viagem."""
    base = settings.dados_dir / viagem_nome
    cal = CalibracaoFaixa(base)
    dados = cal.carregar()
    if dados is None:
        raise HTTPException(404, "Calibração não encontrada")
    return dados


@router.post("/aplicar-calibracao/{viagem_nome}")
async def aplicar_calibracao(
    viagem_nome: str,
    settings: Settings = Depends(get_settings_dep),
):
    """Aplica calibração aos JSONs de lane existentes."""
    base = settings.dados_dir / viagem_nome
    cal = CalibracaoFaixa(base)
    calib = cal.carregar()
    if calib is None:
        raise HTTPException(400, "Calibre a faixa primeiro")

    lane_files = sorted(base.glob("lote_*_lane.json"))
    atualizados = 0
    for path in lane_files:
        try:
            dados = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not dados.get("valid"):
            continue

        left = dados.get("left_inner_m")
        right = dados.get("right_inner_m")
        novo_left, novo_right = CalibracaoFaixa.filtrar_por_calibracao(left, right, calib)

        if novo_left != left or novo_right != right:
            dados["left_inner_m"] = round(novo_left, 3) if novo_left is not None else None
            dados["right_inner_m"] = round(novo_right, 3) if novo_right is not None else None
            if novo_left is not None:
                px = int(novo_left * C.PX_PER_M + C.IMAGE_WIDTH_PX / 2)
                dados["left_inner_px"] = max(0, px)
            if novo_right is not None:
                px = int(novo_right * C.PX_PER_M + C.IMAGE_WIDTH_PX / 2)
                dados["right_inner_px"] = min(C.IMAGE_WIDTH_PX, px)
            dados["calibrado"] = True
            path.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
            atualizados += 1

    return {"status": "ok", "lotes_atualizados": atualizados}
