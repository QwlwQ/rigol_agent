"""Perception orchestration boundary for VLM, OCR, and state recognition."""
class PerceptionManager:
    def __init__(self, locator=None, ocr=None, state_recognizer=None):
        self.locator=locator; self.ocr=ocr; self.state_recognizer=state_recognizer
