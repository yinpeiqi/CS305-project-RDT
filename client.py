from rdt import socket
import time

if __name__ == "__main__":

    MESSAGE = b'hello server'
    MESSAGE2 = b'22222222'
    MESSAGE3 = b'4444444444'
    client = socket()
    client.connect(("127.0.0.1", 8080))
    # client.send(MESSAGE)
    # client.send(MESSAGE2)
    # client.send(MESSAGE3)
    n = 13
    for i in range(0,n):
        client.send(bytes(("message "+str(i)), encoding='utf-8'))
    time.sleep(3)
    num = n
    while num > 0:
        num -= 1
        data = client.recv(2048)
        data = str(data) + "\n"
        print(data, end='')
    client.close()
