from sys import byteorder
import RPi.GPIO as GPIO #라즈베리파이 GPIO 사용
import time
import datetime
import socket           #socket(네트워크 연결) 객체 사용
import argparse         #argparse(클래스 생성) 객체 사용
import sqlite3          #sqlite3(db) 객체 사용
from functools import wraps             #wraps 객체 사용
from contextlib import contextmanager   #contextmanager 객체 사용
import subprocess
from rotary_encoder import Encoder      #Encoder 사용
from utils import get_protocol_data     #?
import yaml

#핀번호 설정
PIN_ENCODER_A = 16 
PIN_ENCODER_B = 20

PIN_RESET_BUTTON = 18
PIN_ACTIVE_SIGNAL = 21

LED_PIN = 26

#초기값 설정
ACTIVATE_STATUS = 0

ENCODER = None

#웹 설정
with open('main.yaml') as f:

    device_data = yaml.load(f, Loader=yaml.FullLoader)

_id = device_data['_id']
IP = device_data['IP']
PORT = device_data['port']
DB_FILE = device_data['db']

def reset_counter():
    pass


client_socket = None

def send_data_to_server(data):
    global client_socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #소켓객체 생성
    #오류 처리 문구
    try:
        client_socket.connect((IP, PORT))   #소켓 객체를 지정한 IP,port에 연결
        client_socket.send(data)            #data를 전송
    except ValueError as e: #ValueError이라는 오류가 발생했을 경우 오류 문구를 'e'에 저장 
        print(f'{e}')
        raise

def receive_data_from_server():
    try:
        global client_socket
        data = client_socket.recv(512)
        print(data)
        return data
    except OSError as e: #OSError이라는 오류가 발생했을 경우 오류 문구를 'e'에 저장 
        print(f'{e}: {IP} {PORT}')

def time_synchronization(data) :
    try:
        dt_str = []
        for i in range(len(data)) :
            dt_str.append(str(chr(data[i])))
        dt_str = "".join(dt_str[3:18])
        dt = datetime.datetime.strptime(dt_str, '%y%m%d%H%M%S%f')
        dt = dt.strftime('%Y-%m-%d %H:%M:%S.000')
        print(dt)
        subprocess.call(["date", "-s", dt])
    except ValueError as e: #ValueError이라는 오류가 발생했을 경우 오류 문구를 'e'에 저장 
        print(f'{e}: {IP} {PORT}')

def set_working_status(value):
    #PIN_ACTIVE_SIGNAL에 들어온 값이 0이 아닐 경우에 실행
    if GPIO.input(PIN_ACTIVE_SIGNAL):
        date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.000') #날짜시간 저장
        ENCODER.value = 0   #버튼을 누른 시점을 0으로 초기화
        ACTIVATE_STATUS = 1 #실행되고 있다는 flag 생성
    #PIN_ACTIVE_SIGNAL에 들어온 값이 0일 경우에 실행
    else:
        date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.000')
        ACTIVATE_STATUS = 0 #실행되지 않는다는 flag 생성
    print(f'{date} | {"activate" if ACTIVATE_STATUS else "deactivate"} | {ENCODER.value}')
    GPIO.output(LED_PIN, False if ACTIVATE_STATUS else True) #실행버튼 동작에 따라 LED점등

    if not ACTIVATE_STATUS:

        #시간 동기화 요청
        dt = f'{0:> 15d}'
        value = f'{0:> 4d}'
        command_T = get_protocol_data(dt, value, "T", _id)
        send_data_to_server(command_T)
        flag = 0

        #시간 동기화
        data_r = receive_data_from_server()
        if data_r:
            if data_r[2] == ord("T"):
                time_synchronization(data_r)
                print("시간동기화 완료")
                flag = 1
                data_r = None

        dt = datetime.datetime.now().strftime('%y%m%d%H%M%S000')
        value = f'{abs(ENCODER.value):> 4d}' #각도를 특정형식으로 저장
        data = get_protocol_data(dt, value, "C", _id) #시간과 각도를 엮어서 data에 저장
        # time.sleep(2)
        print(data)
        
        if flag == 1:
            try:
                send_data_to_server(data) #data를 서버에 전송
        # 연결이 가능한 상태일 경우 보내지 못한 데이터 전송 시도
        # 전송에 성공한 데이터는 삭제
                data = db_select()
                # data = [('210310151620000', 168), ('210310151625000', 356)]
                for dt, value in data:
                    value = f'{value:> 4d}'
                    data = get_protocol_data(dt, value, "S", _id)
                    print(data)
                    try:
                        send_data_to_server(data)
                        db_delete(dt)
                    except OSError as e:
                        return                    
            except OSError as e:
                db_insert(dt, int(value)) #db_insert함수 실행
                return
        else :
            db_insert(dt, int(value))

#라즈베리파이 설정
def init():
    #리셋버튼 설정(눌렸을 때 작동)
    GPIO.setup(PIN_RESET_BUTTON, GPIO.IN)
    GPIO.add_event_detect(
        PIN_RESET_BUTTON, GPIO.FALLING,
        callback=reset_counter,
        bouncetime=50)
    #실행신호 설정
    GPIO.setup(PIN_ACTIVE_SIGNAL, GPIO.IN)
    GPIO.add_event_detect(
        PIN_ACTIVE_SIGNAL, GPIO.BOTH,
        callback=set_working_status,
        bouncetime=50)

def main():
    global ENCODER
    ENCODER = Encoder(PIN_ENCODER_A, PIN_ENCODER_B)
    GPIO.setup(LED_PIN, GPIO.OUT)
    GPIO.output(LED_PIN, False)
    init()
    try:
        #참일 경우 1초 일시정지 
        while True:
            time.sleep(1)
    #KeyboardInterrupt 오류 발생시 보드초기화
    except KeyboardInterrupt:
        GPIO.cleanup()


@contextmanager
#db생성
def db_context(db_file):
    con = sqlite3.connect(db_file) #sqlite3와 db_file연결
    cur = con.cursor() #con으로부터 cursor 생성
    db_create(cur) #db생성함수 실행
    yield cur #cur값 내뱉고 함수 종료(이후 작동X)
    con.commit() #확정 갱신
    con.close()

#db 생성 쿼리문을 이용해 db 생성 
def db_create(cur): 
    cur.execute('''CREATE TABLE IF NOT EXISTS data  
    (datetime TEXT, pulse INTEGER)''')

#db 추가 쿼리문을 이용해 db에 데이터 추가 
def db_insert(dt, pulse):
    with db_context(DB_FILE) as cur:
        cur.execute(f'''INSERT INTO data VALUES('{dt}', {pulse})''')

#db 선택 쿼리문을 이용해 db에서 데이터 10개 선택
def db_select(num=10):
    with db_context(DB_FILE) as cur:
        cur.execute(f'''SELECT * FROM data limit 10''')
        result = cur.fetchall() #불러온 data를 result에 저장
    return result

#db 삭제 쿼리문을 이용해 db 삭제 
def db_delete(dt):
    with db_context(DB_FILE) as cur:
        cur.execute(f'''DELETE FROM data WHERE datetime in ({dt})''')

#'parse'라는 클래스와 하위 명령어 생성 및 축약어 설정
if __name__ == '__main__':
    parse = argparse.ArgumentParser()
    parse.add_argument('-a', '--host', default='localhost', type=str,
                       help='Server IP Address')
    parse.add_argument('-p', '--port', default=5090, type=int,
                       help='Server Port Number')

    parse.add_argument('--reset', action='store_true', help='DB Reset')
    parse.add_argument('--db-file', type=str, default='pulse.db',
                       help='DB File')

    arguments = parse.parse_args()
    IP = arguments.host
    PORT = arguments.port
    DB_FILE = arguments.db_file

    main()
