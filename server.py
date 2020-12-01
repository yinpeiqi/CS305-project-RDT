from rdt import socket

if __name__ == "__main__":
    server = socket('SR')
    server.bind(("0.0.0.0",8000))
    while True:
        conn, client = server.accept()
        while True:
            data = conn.recv(2048)
            print(data)
            if not data:
                break
            conn.send(data)
        conn.close()
