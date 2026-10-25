"""Optionales YuNet/SFace-Backend, exakt ein Besitzer im Kamera-Worker."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .people import unit


class FaceBackend:
    def __init__(self, config: dict) -> None:
        import cv2

        detector, recognizer = config["detector_model"], config["recognizer_model"]
        if (
            not detector
            or not recognizer
            or not Path(detector).is_file()
            or not Path(recognizer).is_file()
        ):
            raise ValueError("Lokale YuNet- und SFace-ONNX-Modelle fehlen.")
        self.detector = cv2.FaceDetectorYN.create(
            str(detector), "", (640, 480), 0.9, 0.3, 500
        )
        self.recognizer = cv2.FaceRecognizerSF.create(str(recognizer), "")
        self.model_id = (
            "sface-sha256:" + hashlib.sha256(Path(recognizer).read_bytes()).hexdigest()
        )

    def detect(self, image) -> list[tuple]:
        import cv2

        height, width = image.shape[:2]
        self.detector.setInputSize((width, height))
        _, rows = self.detector.detect(image)
        if rows is None:
            return []
        results = []
        for row in sorted(rows, key=lambda r: float(r[2] * r[3]), reverse=True)[:5]:
            aligned = self.recognizer.alignCrop(image, row)
            feature = unit(
                self.recognizer.feature(aligned).reshape(-1).astype(float).tolist()
            )
            gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
            tiny = cv2.resize(gray, (9, 8))
            bits = (tiny[:, 1:] > tiny[:, :-1]).reshape(-1)
            fingerprint = sum(int(value) << index for index, value in enumerate(bits))
            eye_x = (float(row[4]) + float(row[6])) / 2
            eye_y = (float(row[5]) + float(row[7])) / 2
            eye_span = max(1, abs(float(row[4] - row[6])))
            ok, jpeg = cv2.imencode(".jpg", aligned, [cv2.IMWRITE_JPEG_QUALITY, 85])
            values = {
                "feature": feature,
                "yaw": (float(row[8]) - eye_x) / eye_span,
                "pitch": (float(row[9]) - eye_y) / eye_span,
                "sharpness": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
                "brightness": float(gray.mean()),
                "face_pixels": min(float(row[2]), float(row[3])),
                "image": jpeg.tobytes() if ok else None,
                "fingerprint": fingerprint,
            }
            results.append((tuple(float(v) for v in row[:4]), values))
        return results
