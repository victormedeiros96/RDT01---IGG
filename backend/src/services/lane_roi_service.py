from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from src.services.lane_roi import LaneDetector
from src.services.lane_roi import calibration as C


class LaneROIService:
    def __init__(self, model_path: str | Path, device: str = "cuda"):
        self.detector = LaneDetector(str(model_path), device=device)
        self._loaded = True

    def process_images(
        self,
        images: list[np.ndarray],
        lote_indice: int,
        output_dir: Path,
    ) -> dict:
        """
        Processa uma lista de imagens raw (4096×1024) de um lote,
        extrai o ROI da faixa (lane) e salva em JSON.

        Retorna o dict do ROI salvo.
        """
        left_inner_list: list[float] = []
        right_inner_list: list[float] = []
        left_conf_list: list[float] = []
        right_conf_list: list[float] = []

        for img in images:
            if img is None or img.size == 0:
                continue
            try:
                result = self.detector.process(img)
                state = result.lane_state
                if state and state.left and state.right:
                    left_inner_list.append(state.left.inner_m)
                    right_inner_list.append(state.right.inner_m)
                    left_conf_list.append(state.left.confidence)
                    right_conf_list.append(state.right.confidence)
            except Exception:
                continue

        # Se nenhuma detecção foi bem-sucedida, marca como inválido
        if not left_inner_list or not right_inner_list:
            lane_roi = {
                "lote": lote_indice,
                "valid": False,
                "left_inner_m": None,
                "right_inner_m": None,
                "left_inner_px": None,
                "right_inner_px": None,
                "confidence": 0.0,
                "n_frames": 0,
            }
        else:
            left_m = float(np.median(left_inner_list))
            right_m = float(np.median(right_inner_list))
            conf = float(np.mean(left_conf_list + right_conf_list))
            left_px = int(left_m * C.PX_PER_M)
            right_px = int(right_m * C.PX_PER_M)
            lane_roi = {
                "lote": lote_indice,
                "valid": True,
                "left_inner_m": round(left_m, 3),
                "right_inner_m": round(right_m, 3),
                "left_inner_px": max(0, left_px),
                "right_inner_px": min(C.IMAGE_WIDTH_PX, right_px),
                "confidence": round(conf, 3),
                "n_frames": len(left_inner_list),
            }

        # Salva o ROI
        output_dir.mkdir(parents=True, exist_ok=True)
        roi_path = output_dir / f"lote_{lote_indice:04d}_lane.json"
        roi_path.write_text(
            json.dumps(lane_roi, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return lane_roi

    @staticmethod
    def carregar_roi(lote_dir: Path, bloco_indice: int) -> dict | None:
        """Carrega o ROI salvo para um bloco específico."""
        roi_path = lote_dir / f"lote_{bloco_indice:04d}_lane.json"
        if not roi_path.is_file():
            return None
        try:
            return json.loads(roi_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    @staticmethod
    def filtrar_por_roi(
        detections: list[dict],
        lane_roi: dict | None,
    ) -> list[dict]:
        """Filtra detecções cujo centro está fora da ROI da faixa."""
        if not lane_roi or not lane_roi.get("valid"):
            return detections

        x_left = lane_roi["left_inner_px"]
        x_right = lane_roi["right_inner_px"]
        img_w = C.IMAGE_WIDTH_PX  # 4096

        # Margem de tolerância: 5% da largura da imagem
        margin = int(img_w * 0.05)

        filtered = []
        for det in detections:
            box = det.get("global_box", [])
            if len(box) < 4:
                filtered.append(det)
                continue
            x1, x2 = box[0], box[2]
            cx = (x1 + x2) / 2

            # Bbox é considerado dentro da ROI se seu centro está dentro
            # da ROI expandida pela margem
            if cx >= (x_left - margin) and cx <= (x_right + margin):
                filtered.append(det)
            # Se o bbox for muito largo (>80% da ROI), mantém mesmo que
            # o centro esteja na borda (pode ser um objeto grande como jacaré)
            elif (x2 - x1) >= (x_right - x_left) * 0.8:
                filtered.append(det)

        return filtered
