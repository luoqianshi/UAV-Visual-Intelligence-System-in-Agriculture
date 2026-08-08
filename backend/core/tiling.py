"""滑窗分块 + 坐标映射。步长=tile_size×(1-overlap)，边缘回退确保尺寸一致。"""
import numpy as np

def slide_window(image: np.ndarray, tile_size: int = 640, overlap_ratio: float = 0.05) -> list:
    h, w = image.shape[:2]
    step = int(tile_size * (1 - overlap_ratio))
    def calc_starts(length):
        if length <= tile_size:
            return [0]
        starts = list(range(0, length - tile_size + 1, step))
        if starts[-1] != length - tile_size:
            starts.append(length - tile_size)
        return starts
    tiles = []
    for oy in calc_starts(h):
        for ox in calc_starts(w):
            tile = image[oy:oy+tile_size, ox:ox+tile_size]
            tiles.append((tile, ox, oy))
    return tiles

def map_to_original(bbox: list, offset_x: int, offset_y: int) -> list:
    return [bbox[0]+offset_x, bbox[1]+offset_y, bbox[2]+offset_x, bbox[3]+offset_y]
