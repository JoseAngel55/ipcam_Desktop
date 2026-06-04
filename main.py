import asyncio
import platform
from signaling.server import start_server
from receiver.webrtc_receiver import CameraReceiver
from virtual_camera.v4l2_camera import VirtualCameraManager


def print_requirements():
    system = platform.system()
    print(f"[*] Sistema detectado: {system}")

    if system == "Linux":
        print("[*] Requisito: v4l2loopback-dkms instalado y headers del kernel")
    elif system == "Windows":
        print("[*] Requisito: UnityCapture instalado (InstallMultipleDevices.bat)")


async def start_receiver(vcam_manager: VirtualCameraManager):
    await asyncio.sleep(1)
    receiver = CameraReceiver(
        server_ip="127.0.0.1",
        server_port=8765,
        vcam_manager=vcam_manager,
    )
    await receiver.connect()


async def main():
    print_requirements()

    vcam_manager = VirtualCameraManager(max_cameras=4)

    if not vcam_manager.load_module():
        print("[!] No se pudo cargar el módulo de cámara virtual")
        print("[!] Continuando solo con preview, sin cámara virtual")
        vcam_manager = None

    try:
        await asyncio.gather(
            start_server(),
            start_receiver(vcam_manager),
        )
    finally:
        if vcam_manager:
            vcam_manager.unload_module()


if __name__ == "__main__":
    asyncio.run(main())