import asyncio
from signaling.server import start_server
from receiver.webrtc_receiver import CameraReceiver
from discovery.scanner import start_discovery_listener


async def start_receiver():
    await asyncio.sleep(1)
    receiver = CameraReceiver(server_ip="127.0.0.1", server_port=8765)
    await receiver.connect()


async def main():
    print("[*] IPCam Bridge iniciando...")
    try:
        await asyncio.gather(
            start_server(),
            start_receiver(),
            start_discovery_listener(),
        )
    finally:
        print("[*] Servidor detenido")


if __name__ == "__main__":
    asyncio.run(main())