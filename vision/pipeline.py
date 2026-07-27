# ──────────────────────────────────────────────
# Project Ella v1.0 — Screen Vision Pipeline
# Powered by mss, EasyOCR, and OpenCV (100% Local & GPU)
# ──────────────────────────────────────────────

import time
from pathlib import Path
import numpy as np
from logger import get_logger

log = get_logger("vision.pipeline")


class VisionPipeline:
    """
    Ella's eyes — processes the screen locally using OCR & Computer Vision.
    
    Pipeline Steps:
    1. Screenshot: Fast frame grab via mss.
    2. OCR: Text extraction using EasyOCR (GPU-accelerated, English & Hindi).
    3. UI Detection: Locating interactive components (buttons, input boxes) using OpenCV.
    4. Vision Reasoning: Constructing structured layout data for LLM reasoning.
    """

    def __init__(self):
        self.reader = None
        self.mss_instance = None
        
        # Lazy-load OCR model on first screenshot to keep startup fast
        self._lazy_load()

    def _lazy_load(self):
        """Lazy load MSS and EasyOCR models (GPU-enabled)."""
        if self.reader is not None:
            return
            
        try:
            import mss
            import easyocr
            
            log.info("Loading EasyOCR with CUDA support...")
            self.mss_instance = mss.mss()
            
            # Load OCR for English and Hindi with GPU acceleration enabled
            self.reader = easyocr.Reader(['en', 'hi'], gpu=True)
            log.info("Vision pipeline ready (OCR loaded on GPU).")
        except Exception as e:
            log.error(f"Error initializing Vision Pipeline: {e}")

    def capture_screenshot(self, output_path: str = None) -> np.ndarray:
        """Capture the primary monitor screen as a numpy array (BGR)."""
        self._lazy_load()
        if self.mss_instance is None:
            log.error("MSS screenshot tool not available.")
            return np.zeros((100, 100, 3), dtype=np.uint8)
            
        try:
            import cv2
            
            # Capture primary monitor
            monitor = self.mss_instance.monitors[1] # 1 is primary monitor
            screenshot = self.mss_instance.shot(output=output_path) if output_path else self.mss_instance.grab(monitor)
            
            # Convert mss screen grab buffer to OpenCV numpy BGR image
            img = np.array(screenshot)
            # Remove alpha channel if present
            if img.shape[2] == 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
            return img
        except Exception as e:
            log.error(f"Screenshot capture failed: {e}")
            return np.zeros((100, 100, 3), dtype=np.uint8)

    def extract_text(self, img: np.ndarray) -> list:
        """
        Run EasyOCR on the screenshot.
        
        Returns:
            list of dicts: [{'text': str, 'box': [[x,y],...], 'confidence': float}]
        """
        self._lazy_load()
        if self.reader is None:
            log.error("OCR reader not loaded.")
            return []
            
        try:
            start_time = time.time()
            results = self.reader.readtext(img)
            
            ocr_elements = []
            for (bbox, text, prob) in results:
                # Convert coordinates to simple [x, y, width, height] format
                xs = [pt[0] for pt in bbox]
                ys = [pt[1] for pt in bbox]
                x, y = int(min(xs)), int(min(ys))
                w, h = int(max(xs) - x), int(max(ys) - y)
                
                ocr_elements.append({
                    "text": text,
                    "box": [x, y, w, h],
                    "confidence": float(prob)
                })
                
            log.debug(f"OCR extracted {len(ocr_elements)} text blocks in {time.time() - start_time:.2f}s")
            return ocr_elements
        except Exception as e:
            log.error(f"OCR extraction failed: {e}")
            return []

    def detect_ui_elements(self, img: np.ndarray) -> list:
        """
        Use OpenCV contour analysis to find bounding boxes of clickable UI components
        (e.g., buttons, input forms, interactive panels).
        """
        try:
            import cv2
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # Apply adaptive thresholding to get clean outlines
            thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
            
            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            ui_boxes = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                
                # Filter boxes by size to locate interactive elements (e.g. buttons, text fields)
                # Ignore tiny noise (< 20px) or massive containers (> 60% of screen)
                screen_h, screen_w = img.shape[:2]
                if 20 < w < screen_w * 0.6 and 15 < h < screen_h * 0.4:
                    # Check aspect ratio
                    aspect_ratio = float(w) / h
                    
                    # Typical buttons are wide, input boxes are long, etc.
                    ui_boxes.append({
                        "box": [x, y, w, h],
                        "type": "button" if aspect_ratio > 2.0 else "interactive_element"
                    })
                    
            log.debug(f"OpenCV detected {len(ui_boxes)} potential UI containers.")
            return ui_boxes
        except Exception as e:
            log.error(f"OpenCV UI element detection failed: {e}")
            return []

    def analyze_screen(self) -> dict:
        """
        Full Vision Reasoning Pipeline:
        Capture Screen ➔ OCR Text ➔ Detect UI Elements ➔ Structured Layout representation
        """
        img = self.capture_screenshot()
        if img.size == 0 or np.all(img == 0):
            return {"text_elements": [], "ui_elements": [], "summary": "Failed to capture screen"}
            
        ocr_results = self.extract_text(img)
        ui_results = self.detect_ui_elements(img)
        
        # Merge results to find which UI elements contain what text
        structured_layout = []
        for ui in ui_results:
            ux, uy, uw, uh = ui["box"]
            contained_text = []
            
            for ocr in ocr_results:
                ox, oy, ow, oh = ocr["box"]
                # Check bounding box containment/overlap
                if ox >= ux and oy >= uy and (ox + ow) <= (ux + uw) and (oy + oh) <= (uy + uh):
                    contained_text.append(ocr["text"])
            
            if contained_text:
                structured_layout.append({
                    "type": ui["type"],
                    "box": ui["box"],
                    "text": " ".join(contained_text)
                })
        
        # Collect OCR texts not mapped to any UI contours
        unmapped_texts = []
        for ocr in ocr_results:
            is_mapped = False
            ox, oy, ow, oh = ocr["box"]
            for ui in ui_results:
                ux, uy, uw, uh = ui["box"]
                if ox >= ux and oy >= uy and (ox + ow) <= (ux + uw) and (oy + oh) <= (uy + uh):
                    is_mapped = True
                    break
            if not is_mapped:
                unmapped_texts.append(ocr)
                
        return {
            "layout": structured_layout,
            "unmapped_text": unmapped_texts,
            "all_text": [o["text"] for o in ocr_results]
        }


if __name__ == "__main__":
    # Test Vision pipeline
    import logging
    logging.basicConfig(level=logging.INFO)
    pipeline = VisionPipeline()
    res = pipeline.analyze_screen()
    print("Vision analysis complete.")
    print("Found text count:", len(res["all_text"]))
    print("First 10 texts:", res["all_text"][:10])
