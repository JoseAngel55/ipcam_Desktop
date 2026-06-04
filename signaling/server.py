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
        role = client_info.get("role", "desconocido")
        print(f"[-] Cliente desconectado: {name} ({role})")

        if role == "camera":
            await broadcast_to_role("receiver", {
                "type": "camera_disconnected",
                "name": name,
            })


async def process_message(websocket, message):
    msg_type = message.get("type")

    if msg_type == "register":
        name = message.get("name", "sin-nombre")
        role = message.get("role")
        connected_clients[websocket] = {"role": role, "name": name}
        print(f"[*] Registrado: {name} ({role})")

        await websocket.send(json.dumps({
            "type": "registered",
            "message": f"Bienvenido {name}",
        }))

        # Si es una cámara, avisar a todos los receptores
        if role == "camera":
            await broadcast_to_role("receiver", {
                "type": "camera_connected",
                "name": name,
            })

    elif msg_type in ["offer", "ice_candidate"]:
        # Cámara → receptor: reenviar a todos los receptores
        sender = connected_clients[websocket].get("name", "desconocido")
        print(f"[*] Reenviando '{msg_type}' de {sender}")
        await broadcast_to_role("receiver", {
            **message,
            "from": sender,
        }, exclude=websocket)

    elif msg_type == "answer":
        # Receptor → cámara específica: reenviar solo a la cámara indicada
        target_name = message.get("target")
        print(f"[*] Reenviando 'answer' al objetivo: {target_name}")
        await send_to_name(target_name, {
            **message,
            "from": connected_clients[websocket].get("name"),
        }, exclude=websocket)

    else:
        print(f"[?] Mensaje desconocido: {msg_type}")


async def broadcast_to_role(role, message, exclude=None):
    for client, info in list(connected_clients.items()):
        if info.get("role") == role and client != exclude:
            try:
                await client.send(json.dumps(message))
            except Exception:
                pass


async def send_to_name(name, message, exclude=None):
    for client, info in list(connected_clients.items()):
        if info.get("name") == name and client != exclude:
            try:
                await client.send(json.dumps(message))
            except Exception:
                pass


async def start_server(host="0.0.0.0", port=8765):
    print(f"[*] Servidor iniciado en {host}:{port}")
    print(f"[*] Esperando conexiones...")
    async with websockets.serve(handle_client, host, port):
        await asyncio.Future()