import cv2
import numpy as np
from annotations.config import (
    OCR_UPSCALE_FACTOR,
    OCR_DENOISE_KERNEL_SIZE,
    OCR_ADAPTIVE_BLOCK_SIZE,
    OCR_ADAPTIVE_C
)


def preprocess_for_ocr(
    image: np.ndarray,
    upscale_factor: float = OCR_UPSCALE_FACTOR
) -> np.ndarray:
    """
    Dedicated image preprocessing pipeline tailored for optical character recognition (OCR)
    on mechanical engineering drawings.

    Steps:
    1. Grayscale conversion (if multi-channel)
    2. Upscaling (bicubic interpolation to enhance fine details of numbers/symbols)
    3. Contrast enhancement via CLAHE (Contrast Limited Adaptive Histogram Equalization)
    4. Denoising using median blur to eliminate speckle noise without blurring edges
    5. Adaptive Gaussian thresholding to cleanly separate characters from drawing background
    """
    if image is None or image.size == 0:
        raise ValueError("Input image is empty or invalid")

    # 1. Grayscale
    if len(image.shape) == 3 and image.shape[2] == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    elif len(image.shape) == 2:
        gray = image.copy()
    else:
        gray = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)

    # 2. Upscaling
    if upscale_factor > 1.0:
        gray = cv2.resize(
            gray,
            (0, 0),
            fx=upscale_factor,
            fy=upscale_factor,
            interpolation=cv2.INTER_CUBIC
        )

    # 3. Contrast normalization (CLAHE)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # 4. Denoising
    kernel_size = OCR_DENOISE_KERNEL_SIZE
    if kernel_size % 2 == 0:
        kernel_size += 1
    denoised = cv2.medianBlur(enhanced, kernel_size)

    # 5. Adaptive thresholding
    block_size = OCR_ADAPTIVE_BLOCK_SIZE
    if block_size % 2 == 0:
        block_size += 1
    binary = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block_size,
        OCR_ADAPTIVE_C
    )

    return binary
