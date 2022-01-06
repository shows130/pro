# TCP server example
import sys
import socket
import logging
import threading
import datetime
from types import MethodType
from utils import calc_checksum, get_protocol_data
from flask import Flask, render_template, request, redirect
import pymysql
import yaml

# logging 초기 설정
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG) #
logger = logging.getLogger('server')

# yaml파일에서 데이터 불러오기
with open('test_server.yaml') as f:
    server_data = yaml.load(f, Loader=yaml.FullLoader)

# db와 연결
db = pymysql.connect(host=server_data['sql']['host'], user=server_data['sql']['user'], password=server_data['sql']['password'], db=server_data['sql']['db'], charset=server_data['sql']['charset'])    
cur = db.cursor()

# SocketServer 클래스 생성
class SocketServer(threading.Thread):
    # 초기설정
    def __init__(self):
        threading.Thread.__init__(self)
        self._status = True
        # self.queue = []

    # get
    @property
    def status(self):
        return self._status

    # set
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

        server_socket.bind((server_data['device']['address'], server_data['device']['port']))
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
                    if data[2] == ord("T"):
                        _id = server_data['server_id']
                        dt = datetime.datetime.now().strftime('%y%m%d%H%M%S000')
                        value = f'{0:> 4d}'
                        data = get_protocol_data(dt, value, "T", _id)
                        client_socket.send(data)
                        continue

                    if 24 != len(data):
                        raise ValueError(
                            f'data is not expected size (24), but {len(data)}')
                    checksum = calc_checksum(data[3:22])
                    if data[22].to_bytes(1, 'big') != checksum:
                        raise ValueError('checksum error.')

                    _id = int.from_bytes(data[1:2], byteorder='big')
                    dt = "".join(data[3:18].decode('utf-8'))
                    dt = datetime.datetime.strptime(dt, "%y%m%d%H%M%S%f")
                    date = datetime.datetime.strftime(dt,"%Y-%m-%d")
                    __time = datetime.datetime.strftime(dt,"%H:%M:%S")
                    value = "".join(data[18:22].decode('utf-8'))
                    mm_per_parse = server_data['device']['wheel']*3.14/100
                    value = round(int(value)*mm_per_parse, 3)
                    # print(f"{dt}, {value}, {_id}")

                    query = f'INSERT INTO rotary.encoder (id, date, time, value) VALUES ("{_id}", "{date}", "{__time}", "{value}");'
                    cur.execute(query)
                    db.commit()
    
                except Exception as e:
                    logger.error(str(e))
                finally:
                    client_socket.close()
                    break


def main():
    app = Flask(__name__)
    
    @app.route('/')
    def board():

        query = f'SELECT * FROM rotary.encoder;'

        cur.execute(query)
        db.commit()

        datum = cur.fetchall()

        datum = list(datum)

        mm_per_parse = server_data['device']['wheel']*3.14/100
        for data in datum :
            num = datum.index(data)
            data = list(data)
            data.append(round(float(data[4])/mm_per_parse))
            datum[num] = tuple(data)
        # print(datum)
        datum = reversed(tuple(datum))
        
        return render_template('datum.html', datum = datum)

    @app.route('/search', methods = ['GET'])
    def search():
        if request.method == 'GET' :
            _id = request.args.get("ID")
            dt = request.args.get("DATE")
            if _id and dt :
                query = f'SELECT * FROM rotary.encoder where id = {_id} AND date = "{dt}";'
            elif _id and dt == '' :
                query = f'SELECT * FROM rotary.encoder where id = {_id};'
            elif _id == '' and dt :
                query = f'SELECT * FROM rotary.encoder where date = "{dt}";'
            else :
                return redirect("/")

            # print(query)
            cur.execute(query)
            db.commit()

            datum = cur.fetchall()

            datum = list(datum)
            mm_per_parse = server_data['device']['wheel']*3.14/100
            for data in datum :
                num = datum.index(data)
                data = list(data)
                data.append(round(float(data[4])/mm_per_parse))
                datum[num] = tuple(data)
            # print(datum)
            datum = reversed(tuple(datum))
            
            return render_template('datum.html', datum = datum)
        else :
            return redirect('/')
    th = SocketServer()
    th.daemon = True
    th.start()

    app.run(host=server_data['web']['host'], port=server_data['web']['port'])


if __name__ == '__main__':
    main()