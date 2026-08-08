import numpy as np
from core.tiling import slide_window, map_to_original

def test_slide_window_count():
    img = np.zeros((640, 1280, 3), dtype=np.uint8)
    tiles = slide_window(img, tile_size=640, overlap_ratio=0.0)
    assert len(tiles) == 2

def test_slide_window_offsets():
    img = np.zeros((640, 1280, 3), dtype=np.uint8)
    tiles = slide_window(img, tile_size=640, overlap_ratio=0.0)
    assert tiles[0][1] == 0 and tiles[0][2] == 0
    assert tiles[1][1] == 640 and tiles[1][2] == 0

def test_slide_window_edge_adjustment():
    img = np.zeros((640, 1000, 3), dtype=np.uint8)
    tiles = slide_window(img, tile_size=640, overlap_ratio=0.0)
    for tile, ox, oy in tiles:
        assert tile.shape[1] == 640

def test_slide_window_tile_size():
    img = np.zeros((1300, 1300, 3), dtype=np.uint8)
    tiles = slide_window(img, tile_size=640, overlap_ratio=0.05)
    for tile, ox, oy in tiles:
        assert tile.shape[0] == 640 and tile.shape[1] == 640

def test_map_to_original():
    assert map_to_original([10, 20, 30, 40], 100, 200) == [110, 220, 130, 240]
