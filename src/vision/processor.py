import io
import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError
from fastapi import HTTPException

def load_and_validate_image(file_bytes: bytes) -> np.ndarray:
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file provided")
    
    # Validate image size (e.g., max 10MB)
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")

    try:
        # Load using PIL to validate image integrity and format
        pil_img = Image.open(io.BytesIO(file_bytes))
        pil_img.verify()
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="Unsupported or corrupt image format")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {str(e)}")

    # PIL verify closes the file, need to reopen it to read bytes into OpenCV
    try:
        nparr = np.frombuffer(file_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise HTTPException(status_code=400, detail="OpenCV could not decode image")
            
        # Basic dimension validation
        height, width = img.shape[:2]
        if height > 5000 or width > 5000:
            raise HTTPException(status_code=400, detail="Image dimensions are unreasonably large")
            
        return img
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")
