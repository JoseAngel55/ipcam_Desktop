import asyncio
from signaling.server import start_server
from receiver.webrtc_receiver import CameraReceiver


async def start_receiver():
    # Esperar a que el servidor esté listo
    await asyncio.sleep(1)
    receiver = CameraReceiver(server_ip="127.0.0.1", server_port=8765)
    await receiver.connect()


async def main():
    await asyncio.gather(
        start_server(),
        start_receiver(),
    )


if __name__ == "__main__":
    asyncio.run(main())