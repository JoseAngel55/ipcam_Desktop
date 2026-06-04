import asyncio
import socket
import netifaces


DISCOVERY_PORT = 8766  # Puerto separado del signaling


def get_local_interfaces() -> list[dict]:
    """
    Retorna todas las interfaces de red activas con su IP y máscara.
    Incluye LAN, WiFi y ZeroTier automáticamente.
    """
    interfaces = []

    for iface_name in netifaces.interfaces():
        addrs = netifaces.ifaddresses(iface_name)

        # Solo IPv4
        if netifaces.AF_INET not in addrs:
            continue

        for addr in addrs[netifaces.AF_INET]:
            ip = addr.get("addr", "")
            netmask = addr.get("netmask", "")

            # Ignorar loopback
            if ip.startswith("127."):
                continue

            interfaces.append({
                "name": iface_name,
                "ip": ip,
                "netmask": netmask,
            })

    return interfaces


def get_network_range(ip: str, netmask: str) -> list[str]:
    """
    Genera la lista de IPs del rango dado una IP y máscara.
    Limita a /24 máximo para no tardar demasiado.
    """
    parts = ip.split(".")
    base = f"{parts[0]}.{parts[1]}.{parts[2]}"
    return [f"{base}.{i}" for i in range(1, 255)]


async def check_host(ip: str, port: int, timeout: float = 0.5) -> str | None:
    """
    Intenta conectarse a ip:port. Retorna la IP si responde, None si no.
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return ip
    except Exception:
        return None


async def scan_network(progress_callback=None) -> list[str]:
    """
    Escanea todas las interfaces activas buscando dispositivos
    con la app corriendo en DISCOVERY_PORT.
    Retorna lista de IPs encontradas.
    """
    interfaces = get_local_interfaces()

    if not interfaces:
        print("[Scanner] No se encontraron interfaces de red activas")
        return []

    all_ips = []
    for iface in interfaces:
        print(f"[Scanner] Escaneando interfaz: {iface['name']} ({iface['ip']})")
        ips = get_network_range(iface["ip"], iface["netmask"])
        all_ips.extend(ips)

    # Eliminar duplicados
    all_ips = list(set(all_ips))
    total = len(all_ips)
    print(f"[Scanner] Escaneando {total} hosts...")

    # Escanear en lotes de 50 para no saturar
    found = []
    batch_size = 50

    for i in range(0, total, batch_size):
        batch = all_ips[i:i + batch_size]
        tasks = [check_host(ip, DISCOVERY_PORT) for ip in batch]
        results = await asyncio.gather(*tasks)
        found.extend([r for r in results if r is not None])

        if progress_callback:
            progress = min(i + batch_size, total)
            progress_callback(progress, total)

    print(f"[Scanner] Dispositivos encontrados: {found}")
    return found


async def start_discovery_listener():
    """
    Servidor TCP simple que escucha en DISCOVERY_PORT.
    Responde a cualquier conexión para que el scanner del PC
    pueda detectar este dispositivo desde otro PC (uso futuro).
    """
    async def handle(reader, writer):
        writer.write(b"ipcam-bridge")
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(
        handle, "0.0.0.0", DISCOVERY_PORT
    )
    print(f"[Discovery] Listener activo en puerto {DISCOVERY_PORT}")
    async with server:
        await server.serve_forever()