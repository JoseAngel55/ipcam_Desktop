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
        self.pc = None
        self.websocket = None
        self.camera_name = None

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

        print("[Receptor] Esperando cámara...")
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
                print(f"[Receptor] Cámara conectada: {message.get('name')}")

            elif msg_type == "offer":
                print("[Receptor] Offer recibido, procesando...")
                self.camera_name = message.get("from", "camara")
                await self._handle_offer(message)

            elif msg_type == "ice_candidate":
                await self._handle_ice_candidate(message)

            elif msg_type == "camera_disconnected":
                print(f"[Receptor] Cámara desconectada: {message.get('name')}")
                if self.pc:
                    await self.pc.close()

    # ─── Handshake WebRTC ────────────────────────────────────────

    async def _handle_offer(self, message):
        self.pc = RTCPeerConnection()

        @self.pc.on("track")
        async def on_track(track):
            if track.kind == "video":
                print("[Receptor] Track de video recibido")
                asyncio.ensure_future(self._receive_video(track))
            elif track.kind == "audio":
                print("[Receptor] Track de audio recibido")

        @self.pc.on("iceconnectionstatechange")
        async def on_ice_state():
            print(f"[Receptor] ICE state: {self.pc.iceConnectionState}")

        offer = RTCSessionDescription(
            sdp=message["sdp"],
            type=message["sdpType"],
        )
        await self.pc.setRemoteDescription(offer)

        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)

        await self._send({
            "type": "answer",
            "sdp": self.pc.localDescription.sdp,
            "sdpType": self.pc.localDescription.type,
        })

        print("[Receptor] Answer enviado")

    async def _handle_ice_candidate(self, message):
        if not self.pc:
            return

        candidate_str = message.get("candidate")
        if not candidate_str:
            return

        try:
            # Parsear directamente desde el string SDP
            candidate = candidate_from_sdp(candidate_str.split(":", 1)[1])
            candidate.sdpMid = message.get("sdpMid")
            candidate.sdpMLineIndex = message.get("sdpMLineIndex")
            await self.pc.addIceCandidate(candidate)
        except Exception as e:
            print(f"[Receptor] Error ICE candidate: {e}")

    # ─── Recepción y display de video ────────────────────────────

    async def _receive_video(self, track):
        print("[Receptor] Iniciando display de video")
        window_name = f"IPCam - {self.camera_name or 'camara'}"

        # Ventana de tamaño fijo que no se redimensiona sola
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 1280, 720)

        while True:
            try:
                frame = await track.recv()
                img = frame.to_ndarray(format="bgr24")
                cv2.imshow(window_name, img)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    print("[Receptor] Cerrando ventana")
                    cv2.destroyAllWindows()
                    break

            except Exception as e:
                print(f"[Receptor] Stream terminado: {e}")
                cv2.destroyAllWindows()
                break