import numpy as np
from core.clahe import enhance

def test_enhance_returns_same_shape():
    img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    assert enhance(img).shape == img.shape

def test_enhance_returns_uint8():
    assert enhance(np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)).dtype == np.uint8

def test_enhance_grayscale():
    img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    assert enhance(img).shape == img.shape

def test_enhance_changes_pixels():
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[40:60, 40:60] = 128
    assert not np.array_equal(enhance(img), img)
