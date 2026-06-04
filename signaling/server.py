import asyncio
import json
import websockets

connected_clients = {}

async def handle_client(websocket):
    print(f"[+] Nueva conexión desde {websocket.remote_address}")
    connected_clients[websocket] = {}

    try:
        async for raw_message in websocket:
            message = json.loads(raw_message)
            await process_message(websocket, message)

    except websockets.exceptions.ConnectionClosedOK:
        print(f"[-] Conexión cerrada limpiamente: {websocket.remote_address}")
    except websockets.exceptions.ConnectionClosedError:
        print(f"[-] Conexión cerrada con error: {websocket.remote_address}")
    finally:
        client_info = connected_clients.pop(websocket, {})
        name = client_info.get("name", "desconocido")
        print(f"[-] Cliente desconectado: {name}")
        await broadcast({
            "type": "camera_disconnected",
            "name": name,
        }, exclude=websocket)


async def process_message(websocket, message):
    msg_type = message.get("type")

    if msg_type == "register":
        connected_clients[websocket] = {
            "role": message.get("role"),
            "name": message.get("name", "sin-nombre"),
        }
        name = connected_clients[websocket]["name"]
        print(f"[*] Registrado: {name}")

        await websocket.send(json.dumps({
            "type": "registered",
            "message": f"Bienvenido {name}",
        }))

        await broadcast({
            "type": "camera_connected",
            "name": name,
        }, exclude=websocket)

    # Mensajes WebRTC — se reenvían al resto de clientes
    elif msg_type in ["offer", "answer", "ice_candidate"]:
        name = connected_clients[websocket].get("name", "desconocido")
        print(f"[*] Reenviando '{msg_type}' de {name}")

        await broadcast({
            **message,
            "from": name,
        }, exclude=websocket)

    else:
        print(f"[?] Mensaje desconocido: {msg_type}")


async def broadcast(message, exclude=None):
    for client in list(connected_clients.keys()):
        if client != exclude:
            try:
                await client.send(json.dumps(message))
            except Exception:
                pass


async def start_server(host="0.0.0.0", port=8765):
    print(f"[*] Servidor iniciado en {host}:{port}")
    print(f"[*] Esperando conexiones...")
    async with websockets.serve(handle_client, host, port):
        await asyncio.Future()