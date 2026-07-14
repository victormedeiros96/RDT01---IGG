import numpy as np
from collections import deque
from dataclasses import dataclass
from typing import Optional

from . import calibration as C


@dataclass
class LaneBoundary:
    center_m: float
    inner_m: float
    confidence: float


@dataclass
class LaneState:
    left: Optional[LaneBoundary] = None
    right: Optional[LaneBoundary] = None
    lane_change: bool = False


class LaneTracker:
    def __init__(self, window=20):
        self.left = None
        self.right = None
        self._frames_since_left = 0
        self._frames_since_right = 0
        self._max_gap = 10
        self._width_history = deque(maxlen=window)

    @property
    def _adaptive_width(self):
        if not self._width_history:
            return C.LANE_WIDTH_M
        return np.median(self._width_history)

    def reset(self):
        self.left = None
        self.right = None
        self._frames_since_left = 0
        self._frames_since_right = 0
        self._width_history.clear()

    def update(self, refined_obbs, img_w=512):
        if not refined_obbs:
            self._frames_since_left += 1
            self._frames_since_right += 1
            return self._get_state()

        centers_m = np.array([d.x_center_m for d in refined_obbs])
        left_side = centers_m < C.CENTER_M
        right_side = ~left_side

        left_dets = [refined_obbs[i] for i in np.where(left_side)[0]]
        right_dets = [refined_obbs[i] for i in np.where(right_side)[0]]

        left_c = [self._make_boundary(d, "left", img_w) for d in left_dets]
        right_c = [self._make_boundary(d, "right", img_w) for d in right_dets]
        left_c = [c for c in left_c if c]
        right_c = [c for c in right_c if c]

        best_left = self._pick(left_c, self.left)
        best_right = self._pick(right_c, self.right)

        self._frames_since_left = 0 if best_left else self._frames_since_left + 1
        self._frames_since_right = 0 if best_right else self._frames_since_right + 1

        w = self._adaptive_width

        if best_left and best_right:
            measured = best_right.center_m - best_left.center_m
            if C.LANE_WIDTH_MIN_M <= measured <= C.LANE_WIDTH_MAX_M:
                self._width_history.append(measured)
                self.left = best_left
                self.right = best_right
            else:
                self.left = best_left
                self.right = self._shift(best_left, w)
        elif best_left and not best_right:
            lane_change = self._detect_lane_change_single(best_left, "left")
            if lane_change:
                self.left = self._shift(best_left, -w)
                self.right = best_left
            elif self._frames_since_right <= self._max_gap and self.right:
                self.left = best_left
            else:
                self.left = best_left
                self.right = self._shift(best_left, w)
        elif best_right and not best_left:
            lane_change = self._detect_lane_change_single(best_right, "right")
            if lane_change:
                self.right = best_right
                self.left = self._shift(best_right, -w)
            elif self._frames_since_left <= self._max_gap and self.left:
                self.right = best_right
            else:
                self.right = best_right
                self.left = self._shift(best_right, -w)

        return self._get_state()

    def _make_boundary(self, det, side, img_w):
        obb = det.obb_px
        if len(obb) < 4:
            return None
        xs = obb[:, 0].astype(float)
        ys = obb[:, 1].astype(float)
        order = np.argsort(ys)
        xs_s = xs[order]
        mid = len(xs_s) // 2
        top_min, top_max = float(xs_s[:mid].min()), float(xs_s[:mid].max())
        bot_min, bot_max = float(xs_s[mid:].min()), float(xs_s[mid:].max())

        center = det.x_center_m
        scale = C.COVERAGE_M / img_w

        if side == "left":
            inner = max(top_max, bot_max) * scale
        else:
            inner = min(top_min, bot_min) * scale

        return LaneBoundary(center_m=center, inner_m=inner,
                            confidence=det.confidence)

    def _pick(self, candidates, previous):
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        if previous:
            return min(candidates, key=lambda c: abs(c.center_m - previous.center_m))
        return max(candidates, key=lambda c: c.confidence)

    def _detect_lane_change_single(self, detection, side):
        if side == "right" and self.left and self.right:
            dist_to_left = abs(detection.center_m - self.left.center_m)
            dist_to_right = abs(detection.center_m - self.right.center_m)
            return dist_to_left < dist_to_right * 0.5
        if side == "left" and self.left and self.right:
            dist_to_left = abs(detection.center_m - self.left.center_m)
            dist_to_right = abs(detection.center_m - self.right.center_m)
            return dist_to_right < dist_to_left * 0.5
        return False

    def _shift(self, boundary, offset):
        return LaneBoundary(
            boundary.center_m + offset,
            boundary.inner_m + offset,
            boundary.confidence * 0.7)

    def _get_state(self, lane_change=False):
        return LaneState(left=self.left, right=self.right,
                         lane_change=lane_change)
