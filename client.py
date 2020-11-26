from rdt import socket

if __name__ == "__main__":

    MESSAGE = b'hello server'
    client = socket()
    client.connect(("127.0.0.1", 8000))
    client.send(MESSAGE)
    data = client.recv(2048)
    assert data == MESSAGE
    client.close()
