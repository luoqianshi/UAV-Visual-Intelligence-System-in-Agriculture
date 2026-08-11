"""CLAHE 增强：彩色图 BGR→LAB→L通道→BGR；灰度图直接增强。

颜色约定对齐 cv2.imread / .lqs/crop.py / ultralytics ndarray 输入（均按 BGR
处理），确保计数工作台分块后传入 detector 的 ndarray 与 ultralytics 期望一致，
避免 RGB/BGR 错配导致颜色反转、检测失准。
"""
import numpy as np
import cv2

def enhance(image: np.ndarray, clip_limit: float = 2.0, grid_size: tuple = (8, 8)) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=grid_size)
    if image.ndim == 2:
        return clahe.apply(image)
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
