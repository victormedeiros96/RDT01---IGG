from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import torch
import torchvision.transforms.v2.functional as F
from ultralytics import YOLO
from ultralytics.models.fastsam import FastSAMPredictor

from src.services.lane_roi import calibration as C


# FastSAM global (singleton)
_fastsam_predictor: FastSAMPredictor | None = None


def _get_fastsam() -> FastSAMPredictor:
    global _fastsam_predictor
    if _fastsam_predictor is None:
        overrides = dict(
            conf=C.FASTSAM_CONF,
            task="segment",
            mode="predict",
            model="FastSAM-x.pt",
            save=False,
            imgsz=C.FASTSAM_IMGSZ,
        )
        _fastsam_predictor = FastSAMPredictor(overrides=overrides)
    return _fastsam_predictor


def segmentar_ponto(
    img_bgr: np.ndarray,
    px: int,
    py: int,
) -> dict:
    """
    Dado um ponto (px, py) na imagem, executa FastSAM prompt
    e retorna máscara, bbox e confiança.
    """
    h, w = img_bgr.shape[:2]
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    sam = _get_fastsam()
    everything = sam(img_rgb)

    pos_points = [[px, py]]
    neg_points: list[list[int]] = []

    result = sam.prompt(everything, points=pos_points, negative_points=neg_points)

    masks = result[0].masks
    if masks is None or len(masks) == 0:
        return {"success": False, "error": "FastSAM não retornou máscara"}

    mask = masks.data[0].cpu().numpy()
    mask_bin = (mask > 0).astype(np.uint8) * 255

    # Redimensiona se necessário
    if mask_bin.shape[:2] != (h, w):
        mask_bin = cv2.resize(mask_bin, (w, h), interpolation=cv2.INTER_NEAREST)

    # Bbox da máscara
    ys, xs = np.where(mask_bin > 0)
    if len(xs) == 0 or len(ys) == 0:
        return {"success": False, "error": "Máscara vazia"}

    x1, y1 = int(xs.min()), int(ys.min())
    x2, y2 = int(xs.max()), int(ys.max())
    cx = (x1 + x2) / 2
    x_center_m = cx / w * C.COVERAGE_M
    conf = float(result[0].boxes.conf[0].cpu().numpy()) if result[0].boxes is not None else 1.0

    return {
        "success": True,
        "bbox": [x1, y1, x2, y2],
        "center_m": round(x_center_m, 3),
        "confidence": round(conf, 3),
        "area_px": int((x2 - x1) * (y2 - y1)),
    }


class CalibracaoFaixa:
    """
    Gerencia a calibração da largura da faixa.

    A calibração é salva em dados/<viagem>/calibracao_faixa.json
    e usada pelo LaneROIService para filtrar detecções.
    """

    TOLERANCIA_M = 0.20  # ±20cm

    def __init__(self, viagem_dir: Path):
        self.path = viagem_dir / "calibracao_faixa.json"
        self._dados: dict | None = None

    def carregar(self) -> dict | None:
        if self._dados is not None:
            return self._dados
        if not self.path.is_file():
            return None
        try:
            self._dados = json.loads(self.path.read_text(encoding="utf-8"))
            return self._dados
        except Exception:
            return None

    def salvar(self, left_center_m: float, right_center_m: float) -> dict:
        largura = round(right_center_m - left_center_m, 3)
        dados = {
            "left_center_m": round(left_center_m, 3),
            "right_center_m": round(right_center_m, 3),
            "largura_m": largura,
            "largura_max_m": round(largura + self.TOLERANCIA_M, 3),
            "largura_min_m": round(max(0.1, largura - self.TOLERANCIA_M), 3),
        }
        self.path.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        self._dados = dados
        return dados

    @staticmethod
    def filtrar_por_calibracao(
        left_m: float | None,
        right_m: float | None,
        calibracao: dict | None,
    ) -> tuple[float | None, float | None]:
        """
        Filtra/estima as bordas da faixa com base na calibração.
        Retorna (left_m, right_m) ajustados.
        """
        if calibracao is None:
            return left_m, right_m

        largura_esperada = calibracao["largura_m"]
        largura_min = calibracao["largura_min_m"]
        largura_max = calibracao["largura_max_m"]
        centro_esperado = (calibracao["left_center_m"] + calibracao["right_center_m"]) / 2
        desloc_max = calibracao.get("largura_m", 1.0) * 0.3  # máx 30% de deslocamento

        # Caso 1: ambos detectados
        if left_m is not None and right_m is not None:
            largura = right_m - left_m
            centro = (left_m + right_m) / 2
            desloc = abs(centro - centro_esperado)

            if largura_min <= largura <= largura_max and desloc <= desloc_max:
                return left_m, right_m

            # Largura OK mas deslocado: corrige centro
            if largura_min <= largura <= largura_max:
                ajuste = centro_esperado - centro
                return round(left_m + ajuste, 3), round(right_m + ajuste, 3)

            # Tenta manter o lado mais próximo do esperado
            dist_left = abs(left_m - calibracao["left_center_m"]) if left_m is not None else 999
            dist_right = abs(right_m - calibracao["right_center_m"]) if right_m is not None else 999

            if dist_left < dist_right and left_m is not None:
                return left_m, round(left_m + largura_esperada, 3)
            if right_m is not None:
                return round(right_m - largura_esperada, 3), right_m
            return left_m, right_m

        # Caso 2: só lado esquerdo
        if left_m is not None:
            return left_m, round(left_m + largura_esperada, 3)

        # Caso 3: só lado direito
        if right_m is not None:
            return round(right_m - largura_esperada, 3), right_m

        return None, None
