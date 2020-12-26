# from rdt import RDTSocket
#
# if __name__ == "__main__":
#     server = RDTSocket(rate=10240, mode='SR')
#     server.bind(("0.0.0.0",8080))
#     while True:
#         conn, client = server.accept()
#         f = open("read.txt", "w")
#         while True:
#             data = conn.recv(1024)
#             print(str(data))
#             f.write(str(data,encoding='utf-8'))
#             f.flush()
#             if not data:
#                 break
#
#         f.close()
#         conn.close()

# from rdt import RDTSocket
# import time
#
# if __name__=='__main__':
#     server = RDTSocket()
#     server.bind(('127.0.0.1', 9999))
#
#     while True:
#         conn, client_addr = server.accept()
#         start = time.perf_counter()
#         while True:
#             data = conn.recv(2048)
#             print(data)
#             if data:
#                 conn.send(data)
#             else:
#                 break
#         '''
#         make sure the following is reachable
#         '''
#         conn.close()
#         print(f'connection finished in {time.perf_counter()-start}s')


from rdt import RDTSocket
from socket import socket, AF_INET, SOCK_DGRAM, SOCK_STREAM
import time

if __name__=='__main__':
    server = RDTSocket()
    # server = socket(AF_INET, SOCK_STREAM) # check what python socket does
    server.bind(('127.0.0.1', 9999))
    # server.listen(0) # check what python socket does

    while True:
        conn, client_addr = server.accept()
        start = time.perf_counter()
        while True:
            data = conn.recv(2048)
            if data:
                conn.send(data)
            else:
                break
        '''
        make sure the following is reachable
        '''
        conn.close()
        print(f'connection finished in {time.perf_counter()-start}s')