# Solución cliente-servidor con sockets y MongoDB (dockerizada)

Este proyecto implementa un servidor TCP con **sockets** en Python que consulta y actualiza datos en **MongoDB**. Incluye `docker-compose` para levantar MongoDB, el servidor y una interfaz de administración opcional (mongo-express).

- Backend (sockets): `socket-server.py`
- Cliente CLI: `socket-client.py`
- Frontend Astro (no requerido para sockets): `frontexam/`

## Requisitos
- Docker y Docker Compose
- Python 3.11+ (solo si desea usar el cliente localmente)

## Puesta en marcha

```bash
# En la carpeta raíz del proyecto
docker compose up -d
```

Servicios levantados:
- `mongo` en `localhost:27017`
- `socket-server` en `localhost:50007`
- `mongo-express` en `http://localhost:8081` (opcional, para visualizar datos)

La base de datos se inicializa automáticamente con datos de ejemplo desde `db/init-mongo.js`.

## Uso del cliente

Ejecute el cliente interactivo para enviar comandos al servidor:

```bash
python socket-client.py
```

Protocolo de comandos (cada línea es una petición):
- `GET:<cedula>` — Obtiene Apellidos, Nombres y Saldo.
- `PUT:<cedula>:<nombres>:<apellidos>:<saldo>` — Crea/actualiza un registro.
- `ADD:<cedula>:<monto>` — Incrementa el saldo.
- `SUB:<cedula>:<monto>` — Decrementa el saldo (verifica saldo suficiente).

Ejemplos:
```
GET:1234567890
PUT:1234567890:Juan:Nieve:150.75
ADD:1234567890:50
SUB:1234567890:25
```

Las respuestas llegan en JSON, una por línea, por ejemplo:
```json
{"ok": true, "message": "Registro encontrado", "data": {"cedula": "1234567890", "nombres": "Juan", "apellidos": "Nieve", "saldo": 150.75}}
```

## Variables de entorno
Puede ajustar estas variables en `docker-compose.yml` o al construir la imagen:
- `SERVER_HOST` (por defecto `0.0.0.0`)
- `SERVER_PORT` (por defecto `50007`)
- `MONGO_URI` (por defecto `mongodb://root:example@mongo:27017/?authSource=admin` en compose)
- `MONGO_DB` (por defecto `clientes_db`)
- `MONGO_COLLECTION` (por defecto `personas`)

## Frontend Astro
El frontend Astro en `frontexam/` no se usa directamente para la comunicación por sockets (los navegadores no pueden abrir sockets TCP crudos). Si deseas una interfaz web, se podría añadir un gateway HTTP/WebSocket sobre el servidor TCP. Pide esto si lo necesitas y lo implemento.

## Parar y limpiar
```bash
docker compose down
# Para limpiar datos persistentes:
docker volume rm socket-taller_mongo-data  # el nombre puede variar según tu entorno
```