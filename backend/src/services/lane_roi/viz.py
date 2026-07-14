import cv2
import numpy as np

LEFT_COLOR = (0, 0, 255)
RIGHT_COLOR = (255, 0, 0)
DET_COLOR = (0, 255, 0)
ROI_COLOR = (0, 255, 120)


def _clip(x, lo, hi):
    return max(lo, min(hi, x))


def draw_detections(img, detections, color=DET_COLOR):
    vis = img.copy()
    for det in detections:
        pts = det.obb_px.reshape((-1, 1, 2))
        cv2.polylines(vis, [pts], isClosed=True, color=color, thickness=1)
    return vis


def draw_lane_state(img, lane_state):
    vis = img.copy()
    h, w = img.shape[:2]
    wm1, hm1 = w - 1, h - 1
    scale = w / 4.4

    if lane_state.left:
        x = _clip(int(lane_state.left.inner_m * scale), 0, wm1)
        cv2.line(vis, (x, 0), (x, hm1), LEFT_COLOR, 3)
        cx = _clip(int(lane_state.left.center_m * scale), 0, wm1)
        cv2.putText(vis, f"Esq {lane_state.left.center_m:.2f}m",
                    (_clip(cx - 60, 0, w - 140), 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, LEFT_COLOR, 2)

    if lane_state.right:
        x = _clip(int(lane_state.right.inner_m * scale), 0, wm1)
        cv2.line(vis, (x, 0), (x, hm1), RIGHT_COLOR, 3)
        cx = _clip(int(lane_state.right.center_m * scale), 0, wm1)
        cv2.putText(vis, f"Dir {lane_state.right.center_m:.2f}m",
                    (_clip(cx - 60, 0, w - 140), 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, RIGHT_COLOR, 2)

    if lane_state.left and lane_state.right:
        lx = _clip(int(lane_state.left.inner_m * scale), 0, wm1)
        rx = _clip(int(lane_state.right.inner_m * scale), 0, wm1)
        if rx > lx:
            overlay = vis.copy()
            cv2.rectangle(overlay, (lx, 0), (rx, hm1), ROI_COLOR, -1)
            cv2.addWeighted(overlay, 0.12, vis, 0.88, 0, vis)

        largura = lane_state.right.inner_m - lane_state.left.inner_m
        cv2.putText(vis, f"Largura {largura:.2f}m",
                    (w // 2 - 60, hm1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    if lane_state.lane_change:
        cv2.putText(vis, "TROCA DE FAIXA", (w // 2 - 100, h // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)

    return vis
