import os
import socket
from typing import Tuple

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


SOCKET_HOST = os.getenv('SOCKET_HOST', 'localhost')
SOCKET_PORT = int(os.getenv('SOCKET_PORT', '50007'))
BUFFER_SIZE = 4096


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
def put_cliente(body: Cliente):
    resp = send_command(f"PUT:{body.cedula}:{body.nombres}:{body.apellidos}:{body.saldo}")
    return _json_or_error(resp)


class Operacion(BaseModel):
    monto: float


@app.post("/clientes/{cedula}/add")
def add_saldo(cedula: str, body: Operacion):
    resp = send_command(f"ADD:{cedula}:{body.monto}")
    return _json_or_error(resp)


@app.post("/clientes/{cedula}/sub")
def sub_saldo(cedula: str, body: Operacion):
    resp = send_command(f"SUB:{cedula}:{body.monto}")
    return _json_or_error(resp)


def _json_or_error(text: str):
    import json
    try:
        return json.loads(text)
    except Exception:
        raise HTTPException(status_code=502, detail={"ok": False, "message": "Respuesta inválida del servidor de sockets", "raw": text})