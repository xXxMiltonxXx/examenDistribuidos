import os
import socket
from typing import Tuple, List

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient


SOCKET_HOST = os.getenv('SOCKET_HOST', 'localhost')
SOCKET_PORT = int(os.getenv('SOCKET_PORT', '50007'))
BUFFER_SIZE = 4096

# Configuración de Mongo para lecturas de operaciones
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://mongo:27017')
MONGO_DB = os.getenv('MONGO_DB', 'clientes_db')
MONGO_COLLECTION_OPS = os.getenv('MONGO_COLLECTION_OPS', 'operaciones')


app = FastAPI(title="Gateway HTTP → Sockets", version="1.0")

# CORS para permitir llamadas desde el frontend (localhost:4321)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4321",
        "http://127.0.0.1:4321",
        "*",  # opcional: permitir cualquier origen
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conexión Mongo para lecturas
mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client[MONGO_DB]
col_ops = mongo_db[MONGO_COLLECTION_OPS]


# Gestor simple de conexiones WebSocket para broadcast
class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, message: dict):
        to_remove = []
        for ws in list(self.active):
            try:
                await ws.send_json(message)
            except Exception:
                to_remove.append(ws)
        for ws in to_remove:
            self.disconnect(ws)


manager = ConnectionManager()


def send_command(command: str) -> str:
    """Envía un comando (terminado en \n) al servidor de sockets y retorna una línea de respuesta."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((SOCKET_HOST, SOCKET_PORT))
        s.sendall((command + "\n").encode('utf-8'))
        buffer = b''
        while True:
            chunk = s.recv(BUFFER_SIZE)
            if not chunk:
                break
            buffer += chunk
            if b"\n" in buffer:
                line, _ = buffer.split(b"\n", 1)
                return line.decode('utf-8', errors='replace')
    return buffer.decode('utf-8', errors='replace')


@app.get("/health")
def health():
    return {"ok": True, "message": "gateway up"}


@app.get("/clientes/{cedula}")
def get_cliente(cedula: str):
    resp = send_command(f"GET:{cedula}")
    return _json_or_error(resp)


class Cliente(BaseModel):
    cedula: str
    nombres: str
    apellidos: str
    saldo: float


@app.put("/clientes")
def put_cliente(body: Cliente, background_tasks: BackgroundTasks):
    resp = send_command(f"PUT:{body.cedula}:{body.nombres}:{body.apellidos}:{body.saldo}")
    parsed = _json_or_error(resp)
    # Broadcast de operación PUT
    try:
        payload = {
            "event": "operacion",
            "data": {
                "tipo": "PUT",
                "cedula": body.cedula,
                "nombres": body.nombres,
                "apellidos": body.apellidos,
                "saldo": parsed.get("data", {}).get("saldo"),
                "estado": "APROBADO"
            }
        }
    except Exception:
        payload = {"event": "operacion", "data": {"tipo": "PUT", "cedula": body.cedula, "estado": "APROBADO"}}
    background_tasks.add_task(manager.broadcast, payload)
    return parsed


class Operacion(BaseModel):
    monto: float


@app.post("/clientes/{cedula}/add")
def add_saldo(cedula: str, body: Operacion, background_tasks: BackgroundTasks):
    resp = send_command(f"ADD:{cedula}:{body.monto}")
    parsed = _json_or_error(resp)
    data = parsed.get("data", {})
    background_tasks.add_task(manager.broadcast, {
        "event": "operacion",
        "data": {
            "tipo": "ADD",
            "cedula": cedula,
            "monto": body.monto,
            "saldo": data.get("saldo"),
            "nombres": data.get("nombres"),
            "apellidos": data.get("apellidos"),
            "estado": "APROBADO"
        }
    })
    return parsed


@app.post("/clientes/{cedula}/sub")
def sub_saldo(cedula: str, body: Operacion, background_tasks: BackgroundTasks):
    resp = send_command(f"SUB:{cedula}:{body.monto}")
    parsed = _json_or_error(resp)
    data = parsed.get("data", {})

    if parsed.get("ok"):
        # Operación exitosa
        background_tasks.add_task(manager.broadcast, {
            "event": "operacion",
            "data": {
                "tipo": "SUB",
                "cedula": cedula,
                "monto": body.monto,
                "saldo": data.get("saldo"),
                "nombres": data.get("nombres"),
                "apellidos": data.get("apellidos"),
                "estado": "APROBADO"
            }
        })
    elif not parsed.get("ok") and parsed.get("message") == "Saldo insuficiente":
        # Operación rechazada
        background_tasks.add_task(manager.broadcast, {
            "event": "operacion",
            "data": {
                "tipo": "SUB",
                "cedula": cedula,
                "monto": body.monto,
                "saldo": None,
                "nombres": data.get("nombres"),
                "apellidos": data.get("apellidos"),
                "estado": "RECHAZADO"
            }
        })

    return parsed


@app.get("/operaciones")
def listar_operaciones(cedula: str, limit: int = 50):
    cur = col_ops.find({"cedula": cedula}).sort("ts", -1).limit(limit)
    items = []
    for d in cur:
        d.pop('_id', None)
        ts = d.get('ts')
        # serializar timestamp
        try:
            d['ts'] = ts.isoformat()
        except Exception:
            d['ts'] = str(ts)
        items.append(d)
    return {"ok": True, "data": items}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Mantener conexión; ignoramos mensajes del cliente
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


def _json_or_error(text: str):
    import json
    try:
        return json.loads(text)
    except Exception:
        raise HTTPException(status_code=502, detail={"ok": False, "message": "Respuesta inválida del servidor de sockets", "raw": text})