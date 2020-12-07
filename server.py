from rdt import RDTSocket

if __name__ == "__main__":
    server = RDTSocket(mode='SR')
    server.bind(("0.0.0.0",8080))
    while True:
        conn, client = server.accept()
        f = open("read.txt", "w")
        while True:
            data = conn.recv(2048)
            print(str(data))
            f.write(str(data,encoding='utf-8'))
            f.flush()
            if not data:
                break
        f.close()
        conn.close()