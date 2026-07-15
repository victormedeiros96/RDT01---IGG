import cv2
import numpy as np
import torch
import torchvision.transforms.v2.functional as F
from ultralytics import YOLO
from ultralytics.models.fastsam import FastSAMPredictor

from . import calibration as C


class OBBResult:
    def __init__(self, class_id, confidence, obb_px, x_center_m, y_range):
        self.class_id = class_id
        self.confidence = confidence
        self.obb_px = obb_px
        self.x_center_m = x_center_m
        self.y_range = y_range

    def __repr__(self):
        return f"OBB(cls={self.class_id}, conf={self.confidence:.3f}, x_m={self.x_center_m:.3f})"


def enhance_contrast(img_np, clip_limit=3.0, saturation_boost=2.0):
    lab = cv2.cvtColor(img_np, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    l_eq = clahe.apply(l)
    img_eq = cv2.cvtColor(cv2.merge((l_eq, a, b)), cv2.COLOR_LAB2BGR)

    hsv = cv2.cvtColor(img_eq, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * saturation_boost, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


def preprocess(img_np, target_size=C.YOLO_IMGSZ, enhance=False):
    if enhance:
        img_np = enhance_contrast(img_np)
    tensor = F.to_image(img_np)
    tensor = F.resize(tensor, (target_size, target_size),
                      interpolation=F.InterpolationMode.BILINEAR,
                      antialias=True)
    tensor = F.to_dtype(tensor, torch.float32, scale=True)
    return tensor


def tensor_to_numpy(tensor):
    return (tensor.permute(1, 2, 0).cpu().numpy() * 255).astype(np.uint8)


class Detector:
    def __init__(self, model_path, device="cuda"):
        self.device = device if torch.cuda.is_available() else "cpu"
        self.yolo = YOLO(model_path)
        overrides = dict(
            conf=C.FASTSAM_CONF,
            task="segment",
            mode="predict",
            model="FastSAM-x.pt",
            save=False,
            imgsz=C.FASTSAM_IMGSZ,
        )
        self.sam_predictor = FastSAMPredictor(overrides=overrides)

    def _poly_to_obb(self, mask):
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        cnt = max(contours, key=cv2.contourArea)
        if cv2.contourArea(cnt) < 10:
            return None
        rect = cv2.minAreaRect(cnt)
        box = cv2.boxPoints(rect)
        return box.reshape(-1).tolist()

    def _clip_px(self, x, y, w, h):
        return max(0, min(w - 1, int(x))), max(0, min(h - 1, int(y)))

    def _get_points_along_obb(self, xywhr_px, h_img, w_img,
                              num_points=C.FASTSAM_NUM_POINTS):
        cx, cy, w, h, rot = xywhr_px
        dx = np.cos(rot)
        dy = np.sin(rot)
        len_axis = max(w, h)
        points = []
        for i in range(num_points):
            offset = (i / (num_points - 1) - 0.5) * len_axis * 0.98
            px = int(cx + offset * dx)
            py = int(cy + offset * dy)
            px = max(0, min(w_img - 1, px))
            py = max(0, min(h_img - 1, py))
            points.append([px, py])

        ex, ey = self._clip_px(cx, cy - len_axis * 0.6, w_img, h_img)
        bx, by = self._clip_px(cx, cy + len_axis * 0.6, w_img, h_img)
        return [[ex, ey]] + points + [[bx, by]]

    def _get_negative_points(self, xywhr_px, h_img, w_img):
        cx, cy, w, h, rot = xywhr_px
        ortho_dx, ortho_dy = -np.sin(rot), np.cos(rot)
        len_axis = max(w, h)
        neg_offset = min(w, h) * 2.0
        points = []
        for frac in [-0.4, 0.0, 0.4]:
            ax = int(cx + frac * len_axis * np.cos(rot))
            ay = int(cy + frac * len_axis * np.sin(rot))
            nx, ny = self._clip_px(ax - neg_offset * ortho_dx,
                                   ay - neg_offset * ortho_dy, w_img, h_img)
            mx, my = self._clip_px(ax + neg_offset * ortho_dx,
                                   ay + neg_offset * ortho_dy, w_img, h_img)
            points.extend([[nx, ny], [mx, my]])
        return points

    def _xywhr_px_to_4pt(self, xywhr_px, w_orig, h_orig):
        cx, cy, w, h, rot = xywhr_px
        rect = ((float(cx), float(cy)),
                (float(w), float(h)), float(np.degrees(rot)))
        box = cv2.boxPoints(rect)
        obb_px = np.array(box.reshape(-1).tolist()).reshape(4, 2).astype(np.int32)
        return obb_px

    def detect(self, img_np):
        if img_np is None:
            return [], []
        h_orig, w_orig = img_np.shape[:2]

        results = self.yolo.predict(
            img_np, conf=C.YOLO_CONF, verbose=False, imgsz=C.YOLO_IMGSZ
        )[0]

        if results.obb is None or len(results.obb) == 0:
            return [], []

        yolo_obbs = []
        for det in results.obb:
            xywhr_px = det.xywhr[0].cpu().numpy()
            cx, cy, dw, dh, rot = xywhr_px
            obb_px = self._xywhr_px_to_4pt(xywhr_px, w_orig, h_orig)
            x_center_m = cx / w_orig * C.COVERAGE_M
            ys = obb_px[:, 1]
            y_range = (int(ys.min()), int(ys.max()))
            yolo_obbs.append(OBBResult(
                class_id=int(det.cls[0].cpu().numpy()),
                confidence=float(det.conf[0].cpu().numpy()),
                obb_px=obb_px,
                x_center_m=x_center_m,
                y_range=y_range,
            ))

        refined_obbs = self._refine_with_fastsam(img_np, results, h_orig, w_orig)
        return refined_obbs, yolo_obbs

    def _refine_with_fastsam(self, img, results, h_orig, w_orig):
        everything_results = self.sam_predictor(img)
        detections = []
        for det in results.obb:
            xywhr_px = det.xywhr[0].cpu().numpy()
            cx, cy, dw, dh, rot = xywhr_px
            class_id = int(det.cls[0].cpu().numpy())
            confidence = float(det.conf[0].cpu().numpy())

            pos_points = self._get_points_along_obb(xywhr_px, h_orig, w_orig)
            neg_points = self._get_negative_points(xywhr_px, h_orig, w_orig)

            try:
                point_results = self.sam_predictor.prompt(
                    everything_results,
                    points=pos_points + neg_points,
                    labels=[1] * len(pos_points) + [0] * len(neg_points),
                )
            except Exception:
                continue

            if (len(point_results) > 0 and point_results[0].masks is not None
                    and len(point_results[0].masks.data) > 0):
                combined_mask = (
                    torch.any(point_results[0].masks.data, dim=0)
                    .cpu().numpy().astype(np.uint8)
                )
                mh, mw = combined_mask.shape
                if mh != h_orig or mw != w_orig:
                    combined_mask = cv2.resize(
                        combined_mask, (w_orig, h_orig),
                        interpolation=cv2.INTER_NEAREST)

                combined_mask = self._extend_to_borders(
                    combined_mask, cx, cy, rot, h_orig, w_orig)

                obb = self._poly_to_obb(combined_mask)
                if obb:
                    obb_px = np.array(obb).reshape(4, 2).astype(np.int32)
                    x_center_m = cx / w_orig * C.COVERAGE_M
                    ys = obb_px[:, 1]
                    detections.append(OBBResult(
                        class_id=class_id,
                        confidence=confidence,
                        obb_px=obb_px,
                        x_center_m=x_center_m,
                        y_range=(int(ys.min()), int(ys.max())),
                    ))
        return detections

    def _extend_to_borders(self, mask, cx, cy, rot, h_img, w_img):
        ys, xs = np.where(mask > 0)
        if len(ys) < 5:
            return mask
        a, b = np.polyfit(xs, ys, 1)
        extended = mask.copy()

        y_min = int(a * 0 + b)
        y_max = int(a * (w_img - 1) + b)
        min_y, max_y = min(y_min, y_max), max(y_min, y_max)

        if min_y < 0:
            fy = min(5, h_img)
            x0 = max(0, min(w_img - 1, int((-fy - b) / a))) if abs(a) > 0.01 else w_img // 2
            x1 = max(0, min(w_img - 1, int((0 - b) / a))) if abs(a) > 0.01 else w_img // 2
            r1, r2 = min(x0, x1), max(x0, x1)
            if r2 > r1:
                extended[0:fy, r1:r2] = 1

        if max_y >= h_img:
            fy = max(0, h_img - 5)
            x0 = max(0, min(w_img - 1, int((h_img - 1 - b) / a))) if abs(a) > 0.01 else w_img // 2
            x1 = max(0, min(w_img - 1, int((fy - b) / a))) if abs(a) > 0.01 else w_img // 2
            r1, r2 = min(x0, x1), max(x0, x1)
            if r2 > r1:
                extended[fy:h_img, r1:r2] = 1

        return extended


def compute_iou(mask1, mask2):
    inter = np.logical_and(mask1 > 0, mask2 > 0).sum()
    union = np.logical_or(mask1 > 0, mask2 > 0).sum()
    return inter / union if union else 0.0
