"""Explizite Kameraquellen mit einheitlichem BGR-Frame-Vertrag."""

from __future__ import annotations


class OpenCVSource:
    name = "opencv"

    def __init__(self, config: dict) -> None:
        import cv2

        self.capture = cv2.VideoCapture(config["index"])
        if not self.capture.isOpened():
            self.capture.release()
            raise ValueError("OpenCV-Kamera nicht verfügbar.")
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, config["width"])
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config["height"])

    def read(self):
        ok, image = self.capture.read()
        if not ok:
            raise OSError("Kamerabild fehlt.")
        return image

    def close(self) -> None:
        self.capture.release()


class Picamera2Source:
    """Picamera2 besitzt CSI; OpenCV erhält nur fertig gelieferte BGR-Frames."""

    name = "picamera2"

    def __init__(self, config: dict) -> None:
        try:
            from picamera2 import Picamera2
        except ImportError as exc:
            raise ValueError(
                "Picamera2 fehlt. Auf Raspberry Pi OS das passende Systempaket installieren."
            ) from exc
        self.capture = Picamera2(config["index"])
        video = self.capture.create_video_configuration(
            main={
                "size": (config["width"], config["height"]),
                "format": "BGR888",
            },
            buffer_count=4,
        )
        self.capture.configure(video)
        self.capture.start()

    def read(self):
        image = self.capture.capture_array("main")
        if image is None or getattr(image, "size", 0) == 0:
            raise OSError("Picamera2-Bild fehlt.")
        return image

    def close(self) -> None:
        try:
            self.capture.stop()
        finally:
            self.capture.close()


def open_camera(config: dict):
    return (
        Picamera2Source(config)
        if config["backend"] == "picamera2"
        else OpenCVSource(config)
    )
