FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY socket-server.py /app/
COPY http_gateway.py /app/

# Variables por defecto; pueden sobrescribirse en docker-compose
ENV SERVER_HOST=0.0.0.0 \
    SERVER_PORT=50007 \
    MONGO_URI=mongodb://mongo:27017 \
    MONGO_DB=clientes_db \
    MONGO_COLLECTION=personas

EXPOSE 50007

CMD ["python", "socket-server.py"]