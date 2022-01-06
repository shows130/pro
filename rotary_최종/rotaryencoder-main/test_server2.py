# TCP server example
import sys
import socket
import logging
import threading
import datetime, time
from utils import calc_checksum, get_protocol_data
from flask import Flask

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger('server')


class SocketServer(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self._status = True
        # self.queue = []

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, v):
        if not isinstance(v, bool):
            print('Error: Not boolean type.')
        self._status = v

    def get_job(self):
        if not self.queue:
            return []
        return self.queue.pop(0)

    def run(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        server_socket.bind(("", 5090))
        server_socket.listen(5)

        # self.queue = []

        print("TCPServer Waiting for client on port 5090")

        while True:
            client_socket, address = server_socket.accept()
            logger.info(f"I got a connection from {address}")
            while True:
                try:
                    data = client_socket.recv(512)
                    logger.info(f'received: {data}')
                    if data[1] == ord("T"):
                        dt = datetime.datetime.now().strftime('%y%m%d%H%M%S000')
                        value = f'{0:> 4d}'
                        data = get_protocol_data(dt, value, "T")
                        client_socket.send(data)
                        print("시간동기화 확인")
                        continue

                    if 23 != len(data):
                        raise ValueError(
                            f'data is not expected size (23), but {len(data)}')
                    checksum = calc_checksum(data[2:21])
                    if data[21].to_bytes(1, 'big') != checksum:
                        raise ValueError('checksum error.')
                    
                    # if data[1] == "S":
                    #     get_protocol_data(dt, value, "S")
                    #     client_socket.send(data)
                    # else :
                    #     get_protocol_data(dt, value, "C")
                    #     client_socket.send(data)
                except Exception as e:
                    logger.error(str(e))
                finally:
                    client_socket.close()
                    break


def main():
    app = Flask(__name__)
    print("Hello world")
    @app.route('/')
    def board():
        return "Welcome"

    @app.route('/example', defaults={'number': 0})
    @app.route('/example/<number>')
    def boards(number):
        return f'{number}'

    th = SocketServer()
    th.daemon = True
    th.start()

    app.run(host="0.0.0.0", port=8080)


if __name__ == '__main__':
    main()