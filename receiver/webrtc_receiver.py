import asyncio
import cv2
import json
import websockets

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.sdp import candidate_from_sdp


class CameraReceiver:
    def __init__(self, server_ip="127.0.0.1", server_port=8765):
        self.server_ip = server_ip
        self.server_port = server_port
        self.websocket = None

        # Una RTCPeerConnection por cada cámara conectada
        # { "Android-Cam": RTCPeerConnection }
        self.peer_connections = {}

    # ─── Conexión al signaling server ────────────────────────────

    async def connect(self):
        uri = f"ws://{self.server_ip}:{self.server_port}"
        print(f"[Receptor] Conectando al servidor {uri}")

        self.websocket = await websockets.connect(uri)

        await self._send({
            "type": "register",
            "role": "receiver",
            "name": "PC-Receptor",
        })

        print("[Receptor] Esperando cámaras...")
        await self._message_loop()

    async def _send(self, message):
        await self.websocket.send(json.dumps(message))

    # ─── Loop de mensajes ────────────────────────────────────────

    async def _message_loop(self):
        async for raw in self.websocket:
            message = json.loads(raw)
            msg_type = message.get("type")

            if msg_type == "registered":
                print("[Receptor] Registrado en el servidor")

            elif msg_type == "camera_connected":
                print(f"[Receptor] Cámara disponible: {message.get('name')}")

            elif msg_type == "offer":
                camera_name = message.get("from", "camara")
                print(f"[Receptor] Offer de: {camera_name}")
                await self._handle_offer(camera_name, message)

            elif msg_type == "ice_candidate":
                camera_name = message.get("from")
                await self._handle_ice_candidate(camera_name, message)

            elif msg_type == "camera_disconnected":
                camera_name = message.get("name")
                print(f"[Receptor] Cámara desconectada: {camera_name}")
                await self._close_connection(camera_name)

    # ─── Handshake WebRTC por cámara ─────────────────────────────

    async def _handle_offer(self, camera_name, message):
        # Cerrar conexión previa si existe
        await self._close_connection(camera_name)

        pc = RTCPeerConnection()
        self.peer_connections[camera_name] = pc

        @pc.on("track")
        async def on_track(track):
            if track.kind == "video":
                print(f"[Receptor] Video de: {camera_name}")
                asyncio.ensure_future(self._receive_video(track, camera_name))
            elif track.kind == "audio":
                print(f"[Receptor] Audio de: {camera_name}")

        @pc.on("iceconnectionstatechange")
        async def on_ice_state():
            print(f"[Receptor] ICE {camera_name}: {pc.iceConnectionState}")

        offer = RTCSessionDescription(
            sdp=message["sdp"],
            type=message["sdpType"],
        )
        await pc.setRemoteDescription(offer)

        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        # El answer lleva el target para que el servidor
        # sepa a qué cámara reenviarlo
        await self._send({
            "type": "answer",
            "sdp": pc.localDescription.sdp,
            "sdpType": pc.localDescription.type,
            "target": camera_name,
        })

        print(f"[Receptor] Answer enviado a: {camera_name}")

    async def _handle_ice_candidate(self, camera_name, message):
        pc = self.peer_connections.get(camera_name)
        if not pc:
            return

        candidate_str = message.get("candidate")
        if not candidate_str:
            return

        try:
            candidate = candidate_from_sdp(candidate_str.split(":", 1)[1])
            candidate.sdpMid = message.get("sdpMid")
            candidate.sdpMLineIndex = message.get("sdpMLineIndex")
            await pc.addIceCandidate(candidate)
        except Exception as e:
            print(f"[Receptor] Error ICE {camera_name}: {e}")

    async def _close_connection(self, camera_name):
        pc = self.peer_connections.pop(camera_name, None)
        if pc:
            await pc.close()
            cv2.destroyWindow(f"IPCam - {camera_name}")
            print(f"[Receptor] Conexión cerrada: {camera_name}")

    # ─── Recepción y display de video ────────────────────────────

    async def _receive_video(self, track, camera_name):
        window_name = f"IPCam - {camera_name}"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 1280, 720)

        while True:
            try:
                frame = await track.recv()
                img = frame.to_ndarray(format="bgr24")
                cv2.imshow(window_name, img)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    cv2.destroyAllWindows()
                    break

            except Exception as e:
                print(f"[Receptor] Stream terminado {camera_name}: {e}")
                cv2.destroyWindow(window_name)
                break