# -*- coding: utf-8 -*-
"""
Cliente de sockets TCP interactivo para consultar/actualizar datos en MongoDB
vía el servidor de sockets.

Protocolo:
  - GET:<cedula>
  - PUT:<cedula>:<nombres>:<apellidos>:<saldo>
  - ADD:<cedula>:<monto>
  - SUB:<cedula>:<monto>
"""

import socket
import os


HOST = os.getenv('SERVER_HOST', '127.0.0.1')
PORT = int(os.getenv('SERVER_PORT', '50007'))
BUFFER_SIZE = 4096


def recv_line(sock: socket.socket) -> str:
    buffer = b''
    while True:
        chunk = sock.recv(BUFFER_SIZE)
        if not chunk:
            break
        buffer += chunk
        if b"\n" in buffer:
            line, _rest = buffer.split(b"\n", 1)
            return line.decode('utf-8', errors='replace')
    return buffer.decode('utf-8', errors='replace')


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f'Conectando con el servidor en {HOST}:{PORT}')
    sock.connect((HOST, PORT))

    try:
        print('Cliente listo. Ejemplos:')
        print('  GET:1234567890')
        print('  PUT:1234567890:Juan:Nieve:150.75')
        print('  ADD:1234567890:50')
        print('  SUB:1234567890:25')
        print('Escriba comando y presione Enter. Ctrl+C para salir.')
        while True:
            cmd = input('> ').strip()
            if not cmd:
                continue
            sock.sendall((cmd + "\n").encode('utf-8'))
            resp = recv_line(sock)
            print(resp)
    except KeyboardInterrupt:
        print('\nSaliendo...')
    finally:
        sock.close()


if __name__ == '__main__':
    main()

