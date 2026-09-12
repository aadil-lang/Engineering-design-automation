import cv2
import numpy as np
import math
from core.models import Line, Circle, Contour, ImageMetadata, AnalyzeResponse

def extract_features(img: np.ndarray) -> AnalyzeResponse:
    height, width = img.shape[:2]
    img_meta = ImageMetadata(width=width, height=height)

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Noise reduction
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Edge detection
    edges = cv2.Canny(blurred, 50, 150, apertureSize=3)

    # Extract Lines using HoughLinesP
    lines_list = []
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=50, minLineLength=30, maxLineGap=10)
    if lines is not None:
        for line in lines:
            line_flat = line.flatten()
            if len(line_flat) == 4:
                x1, y1, x2, y2 = line_flat
                length = math.hypot(x2 - x1, y2 - y1)
                angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
                lines_list.append(Line(x1=float(x1), y1=float(y1), x2=float(x2), y2=float(y2), length=float(length), angle=float(angle)))

    # Extract Circles using HoughCircles
    circles_list = []
    circles = cv2.HoughCircles(blurred, cv2.HOUGH_GRADIENT, dp=1.2, minDist=30, param1=50, param2=30, minRadius=5, maxRadius=500)
    if circles is not None:
        circles = np.uint16(np.around(circles))
        for i in circles[0, :]:
            circle_flat = i.flatten()
            if len(circle_flat) == 3:
                cx, cy, r = circle_flat
                circles_list.append(Circle(center_x=float(cx), center_y=float(cy), radius=float(r)))

    # Extract Contours
    contours_list = []
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 50:  # Filter out very small contours
            perimeter = cv2.arcLength(cnt, True)
            x, y, w, h = cv2.boundingRect(cnt)
            contours_list.append(Contour(area=float(area), perimeter=float(perimeter), bounding_box=(float(x), float(y), float(w), float(h))))

    return AnalyzeResponse(
        image=img_meta,
        lines=lines_list,
        circles=circles_list,
        contours=contours_list
    )
