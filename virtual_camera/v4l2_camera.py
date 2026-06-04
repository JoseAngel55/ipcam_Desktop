import subprocess
import platform
import numpy as np
import pyvirtualcam
import cv2


class VirtualCamera:
    def __init__(self, device_path: str, width: int = 1280, height: int = 720):
        self.device_path = device_path
        self.width = width
        self.height = height
        self._cam = None

    def open(self):
        try:
            system = platform.system()

            if system == "Linux":
                self._cam = pyvirtualcam.Camera(
                    width=self.width,
                    height=self.height,
                    fps=30,
                    device=self.device_path,
                    fmt=pyvirtualcam.PixelFormat.BGR,
                    backend="v4l2loopback",
                )
            elif system == "Windows":
                self._cam = pyvirtualcam.Camera(
                    width=self.width,
                    height=self.height,
                    fps=30,
                    device=self.device_path,
                    fmt=pyvirtualcam.PixelFormat.BGR,
                    backend="unitycapture",
                )
            else:
                raise RuntimeError(f"Sistema no soportado: {system}")

            print(f"[VirtualCam] Dispositivo abierto: {self._cam.device}")

        except Exception as e:
            raise RuntimeError(f"Error abriendo cámara virtual: {e}")

    def write_frame(self, bgr_frame: np.ndarray):
        if self._cam is None:
            return
        try:
            if bgr_frame.shape[1] != self.width or bgr_frame.shape[0] != self.height:
                bgr_frame = cv2.resize(bgr_frame, (self.width, self.height))
            self._cam.send(bgr_frame)
            self._cam.sleep_until_next_frame()
        except Exception as e:
            print(f"[VirtualCam] Error escribiendo frame: {e}")

    def close(self):
        if self._cam:
            self._cam.close()
            self._cam = None
            print(f"[VirtualCam] Dispositivo cerrado: {self.device_path}")


class VirtualCameraManager:
    def __init__(self, max_cameras: int = 4):
        self.max_cameras = max_cameras
        self.cameras: dict[str, VirtualCamera] = {}
        self._devices: list[str] = []
        self._system = platform.system()

    def load_module(self) -> bool:
        if self._system == "Linux":
            return self._load_linux()
        elif self._system == "Windows":
            return self._load_windows()
        else:
            print(f"[VirtualCam] Sistema no soportado: {self._system}")
            return False

    def _load_linux(self) -> bool:
        print(f"[VirtualCam] Cargando v4l2loopback ({self.max_cameras} dispositivos)...")

        # Descargar módulo si ya estaba cargado
        subprocess.run(
            ["sudo", "modprobe", "-r", "v4l2loopback"],
            capture_output=True
        )

        video_nr = ",".join([str(10 + i) for i in range(self.max_cameras)])
        card_label = ",".join([f"IPCam-{i + 1}" for i in range(self.max_cameras)])
        exclusive_caps = ",".join(["1"] * self.max_cameras)

        result = subprocess.run([
            "sudo", "modprobe", "v4l2loopback",
            f"devices={self.max_cameras}",
            f"video_nr={video_nr}",
            f"card_label={card_label}",
            f"exclusive_caps={exclusive_caps}",
        ], capture_output=True, text=True)

        if result.returncode != 0:
            print(f"[VirtualCam] Error cargando módulo: {result.stderr}")
            return False

        self._devices = [f"/dev/video{10 + i}" for i in range(self.max_cameras)]
        print(f"[VirtualCam] Dispositivos listos: {self._devices}")
        return True

    def _load_windows(self) -> bool:
        # UnityCapture registra dispositivos con estos nombres
        # "Unity Video Capture" es el primero
        # "Unity Video Capture 2", "Unity Video Capture 3"... los siguientes
        self._devices = ["Unity Video Capture"] + [
            f"Unity Video Capture {i + 2}" for i in range(self.max_cameras - 1)
        ]
        print(f"[VirtualCam] Modo Windows, dispositivos: {self._devices}")
        return True

    def assign_camera(self, camera_name: str) -> VirtualCamera | None:
        # Si ya tiene un dispositivo asignado, devolverlo
        if camera_name in self.cameras:
            return self.cameras[camera_name]

        # Buscar dispositivo libre
        used = {cam.device_path for cam in self.cameras.values()}
        free = [d for d in self._devices if d not in used]

        if not free:
            print(f"[VirtualCam] Sin dispositivos libres para {camera_name}")
            return None

        vcam = VirtualCamera(free[0])
        try:
            vcam.open()
            self.cameras[camera_name] = vcam
            print(f"[VirtualCam] Asignado: {camera_name} → {free[0]}")
            return vcam
        except Exception as e:
            print(f"[VirtualCam] Error asignando dispositivo: {e}")
            return None

    def release_camera(self, camera_name: str):
        vcam = self.cameras.pop(camera_name, None)
        if vcam:
            vcam.close()

    def unload_module(self):
        for vcam in list(self.cameras.values()):
            vcam.close()
        self.cameras.clear()

        if self._system == "Linux":
            subprocess.run(
                ["sudo", "modprobe", "-r", "v4l2loopback"],
                capture_output=True
            )
            print("[VirtualCam] Módulo descargado")