import pytest
import cv2
import numpy as np
import io
from PIL import Image

@pytest.fixture
def synthetic_image_bytes():
    # Create a white image
    img = np.ones((500, 500, 3), dtype=np.uint8) * 255
    
    # Draw a line
    cv2.line(img, (50, 50), (450, 50), (0, 0, 0), 2)
    
    # Draw a circle
    cv2.circle(img, (250, 250), 100, (0, 0, 0), 2)
    
    # Draw a rectangle (contour)
    cv2.rectangle(img, (50, 350), (150, 450), (0, 0, 0), 2)
    
    # Convert to PIL Image to save as bytes
    pil_img = Image.fromarray(img)
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return buf.getvalue()

@pytest.fixture
def synthetic_image_np(synthetic_image_bytes):
    nparr = np.frombuffer(synthetic_image_bytes, np.uint8)
    return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

@pytest.fixture
def empty_image_bytes():
    return b""

@pytest.fixture
def corrupt_image_bytes():
    return b"not an image file"
