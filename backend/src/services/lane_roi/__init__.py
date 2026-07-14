import time
import cv2
import numpy as np

from .detector import Detector, preprocess, tensor_to_numpy
from .tracker import LaneTracker
from . import calibration as C
from . import viz


class FrameResult:
    def __init__(self):
        self.refined_obbs = []
        self.yolo_obbs = []
        self.lane_state = None
        self.full_image = None
        self.inference_time_ms = 0.0
        self.tracking_time_ms = 0.0
        self.iou = 0.0


class LaneDetector:
    def __init__(self, model_path="weights/best.pt", device="cuda"):
        self.detector = Detector(model_path, device=device)
        self.tracker = LaneTracker()

    def process(self, img):
        result = FrameResult()
        result.full_image = img
        t0 = time.perf_counter()

        h_orig, w_orig = img.shape[:2]
        if w_orig != C.YOLO_IMGSZ or h_orig != C.YOLO_IMGSZ:
            tensor = preprocess(img)
            img_r = tensor_to_numpy(tensor)
        else:
            img_r = img

        refined, yolo = self.detector.detect(img_r)

        if w_orig != C.YOLO_IMGSZ:
            sx = w_orig / C.YOLO_IMGSZ
            sy = h_orig / C.YOLO_IMGSZ
            for dets in [refined, yolo]:
                for d in dets:
                    d.obb_px[:, 0] = (d.obb_px[:, 0] * sx).astype(np.int32)
                    d.obb_px[:, 1] = (d.obb_px[:, 1] * sy).astype(np.int32)

        result.refined_obbs = refined
        result.yolo_obbs = yolo

        t1 = time.perf_counter()
        result.inference_time_ms = (t1 - t0) * 1000

        result.lane_state = self.tracker.update(refined, w_orig)
        t2 = time.perf_counter()
        result.tracking_time_ms = (t2 - t1) * 1000

        result.iou = self._compute_iou(yolo, refined, h_orig, w_orig)
        return result

    def _compute_iou(self, yolo, refined, h, w):
        if not yolo or not refined:
            return 0.0
        from .detector import compute_iou
        scores = []
        for y, r in zip(yolo, refined):
            my = np.zeros((h, w), dtype=np.uint8)
            cv2.fillPoly(my, [y.obb_px.reshape((-1, 1, 2))], 1)
            mr = np.zeros((h, w), dtype=np.uint8)
            cv2.fillPoly(mr, [r.obb_px.reshape((-1, 1, 2))], 1)
            scores.append(compute_iou(my, mr))
        return float(np.mean(scores)) if scores else 0.0

    def draw(self, result):
        vis = result.full_image.copy()
        vis = viz.draw_detections(vis, result.refined_obbs, (0, 255, 0))
        vis = viz.draw_lane_state(vis, result.lane_state)
        return vis

    def reset_tracker(self):
        self.tracker.reset()
