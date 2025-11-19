"""
Servidor de sockets TCP que consulta y actualiza datos en MongoDB.

Protocolo de mensajes (delimitado por nueva línea "\n"):
  - GET:<cedula>
  - PUT:<cedula>:<nombres>:<apellidos>:<saldo>
  - ADD:<cedula>:<monto>
  - SUB:<cedula>:<monto>

Respuestas en JSON terminadas con "\n".
"""

import os
import json
import socket
from typing import Dict, Any

from pymongo import MongoClient
from datetime import datetime, timezone

# Configuración del servidor TCP
HOST = os.getenv('SERVER_HOST', '0.0.0.0')
PORT = int(os.getenv('SERVER_PORT', '50007'))
BUFFER_SIZE = 4096

# Configuración de MongoDB
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://mongo:27017')
MONGO_DB = os.getenv('MONGO_DB', 'clientes_db')
MONGO_COLLECTION = os.getenv('MONGO_COLLECTION', 'personas')
MONGO_COLLECTION_OPS = os.getenv('MONGO_COLLECTION_OPS', 'operaciones')


def _log_operacion(col_ops, data: dict):
    """Registra una operación en la colección de operaciones con timestamp UTC."""
    doc = {
        **data,
        "ts": datetime.now(timezone.utc),
    }
    try:
        col_ops.insert_one(doc)
    except Exception as e:
        # No interrumpir el proceso principal si falla el log
        print(f"Error al registrar operación: {e}")


def json_response(ok: bool, message: str, data: Dict[str, Any] | None = None) -> bytes:
    payload = {"ok": ok, "message": message}
    if data is not None:
        payload["data"] = data
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode('utf-8')


def parse_command(raw: str) -> tuple[str, list[str]]:
    raw = raw.strip()
    parts = raw.split(':')
    cmd = parts[0].upper() if parts else ''
    args = parts[1:]
    return cmd, args


def handle_get(col, cedula: str) -> bytes:
    doc = col.find_one({"cedula": cedula})
    if not doc:
        return json_response(False, f"No existe registro para cédula {cedula}")
    data = {
        "cedula": doc.get("cedula"),
        "nombres": doc.get("nombres"),
        "apellidos": doc.get("apellidos"),
        "saldo": float(doc.get("saldo", 0)),
    }
    return json_response(True, "Registro encontrado", data)


def handle_put(col, cedula: str, nombres: str, apellidos: str, saldo_str: str) -> bytes:
    try:
        saldo = float(saldo_str)
    except ValueError:
        return json_response(False, "Saldo inválido")
    col.update_one(
        {"cedula": cedula},
        {"$set": {"cedula": cedula, "nombres": nombres, "apellidos": apellidos, "saldo": saldo}},
        upsert=True,
    )
    # Log de operación
    _log_operacion(col.database[MONGO_COLLECTION_OPS], {
        "cedula": cedula,
        "tipo": "PUT",
        "monto": None,
        "saldo_nuevo": saldo,
        "nombres": nombres,
        "apellidos": apellidos,
        "estado": "APROBADO",
    })
    return json_response(True, "Registro creado/actualizado", {"cedula": cedula, "saldo": saldo})


def handle_add(col, cedula: str, monto_str: str) -> bytes:
    try:
        monto = float(monto_str)
    except ValueError:
        return json_response(False, "Monto inválido")
    res = col.find_one_and_update(
        {"cedula": cedula},
        {"$inc": {"saldo": monto}},
        return_document=True,
    )
    if not res:
        return json_response(False, f"No existe registro para cédula {cedula}")
    nuevo_saldo = float(res.get("saldo", 0))
    nombres = res.get("nombres", "")
    apellidos = res.get("apellidos", "")
    _log_operacion(col.database[MONGO_COLLECTION_OPS], {
        "cedula": cedula,
        "tipo": "ADD",
        "monto": monto,
        "saldo_nuevo": nuevo_saldo,
        "estado": "APROBADO",
        "nombres": nombres,
        "apellidos": apellidos,
    })
    return json_response(True, "Saldo incrementado", {"cedula": cedula, "saldo": nuevo_saldo, "nombres": nombres, "apellidos": apellidos})


def handle_sub(col, cedula: str, monto_str: str) -> bytes:
    try:
        monto = float(monto_str)
    except ValueError:
        return json_response(False, "Monto inválido")
    # Comprobación de saldo suficiente
    doc = col.find_one({"cedula": cedula})
    if not doc:
        return json_response(False, f"No existe registro para cédula {cedula}")
    saldo_actual = float(doc.get("saldo", 0))
    nombres = doc.get("nombres", "")
    apellidos = doc.get("apellidos", "")
    if saldo_actual < monto:
        _log_operacion(col.database[MONGO_COLLECTION_OPS], {
            "cedula": cedula,
            "tipo": "SUB",
            "monto": monto,
            "saldo_nuevo": saldo_actual,
            "estado": "RECHAZADO",
            "nombres": nombres,
            "apellidos": apellidos,
        })
        return json_response(False, "Saldo insuficiente", {
            "cedula": cedula,
            "nombres": doc.get('nombres'),
            "apellidos": doc.get('apellidos')
        })

    # Actualizar saldo y registrar operación
    res = col.find_one_and_update(
        {"cedula": cedula},
        {"$inc": {"saldo": -monto}},
        return_document=True,
    )
    nuevo_saldo = float(res.get("saldo", 0))
    _log_operacion(col.database[MONGO_COLLECTION_OPS], {
        "cedula": cedula,
        "tipo": "SUB",
        "monto": monto,
        "saldo_nuevo": nuevo_saldo,
        "estado": "APROBADO",
        "nombres": nombres,
        "apellidos": apellidos,
    })
    return json_response(True, "Saldo decrementado", {"cedula": cedula, "saldo": nuevo_saldo, "nombres": nombres, "apellidos": apellidos})


def main():
    # Conexión a MongoDB
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client[MONGO_DB]
    col = db[MONGO_COLLECTION]
    # Asegurar índices básicos
    db[MONGO_COLLECTION_OPS].create_index([("cedula", 1), ("ts", -1)])

    # Socket TCP
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, PORT))
    sock.listen(8)
    print(f"Servidor escuchando en {HOST}:{PORT}. MongoDB: {MONGO_URI} db={MONGO_DB} col={MONGO_COLLECTION}")

    try:
        while True:
            print('Esperando conectar con un cliente')
            connection, client_address = sock.accept()
            print('Conectado desde', client_address)
            with connection:
                # Recibir por líneas; cada petición termina con "\n"
                buffer = b''
                while True:
                    chunk = connection.recv(BUFFER_SIZE)
                    if not chunk:
                        break
                    buffer += chunk
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        raw = line.decode('utf-8', errors='replace')
                        print(f"Petición: {raw}")
                        cmd, args = parse_command(raw)
                        if cmd == 'GET' and len(args) == 1:
                            response = handle_get(col, args[0])
                        elif cmd == 'PUT' and len(args) == 4:
                            response = handle_put(col, args[0], args[1], args[2], args[3])
                        elif cmd == 'ADD' and len(args) == 2:
                            response = handle_add(col, args[0], args[1])
                        elif cmd == 'SUB' and len(args) == 2:
                            response = handle_sub(col, args[0], args[1])
                        else:
                            response = json_response(False, "Comando inválido o argumentos incorrectos")
                        connection.sendall(response)
    except KeyboardInterrupt:
        print("Deteniendo servidor...")
    finally:
        sock.close()


if __name__ == '__main__':
    main()

  