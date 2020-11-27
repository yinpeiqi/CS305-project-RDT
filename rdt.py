from enum import Enum
from queue import Queue
from threading import Thread
from time import time
from typing import Tuple
from packet import Packet
import udp

Address = Tuple[str, int]


class socket(udp.UDPsocket):
    def __init__(self):
        super(socket, self).__init__()
        self.state = State.CLOSE
        self.conn: Connection
        self.conns: dict[Address: Connection] = {}
        self.new_conn: Queue[Connection] = Queue()


    def connect(self, address: Address):
        # client connect to server, create conn
        self.conn = Connection(address, self)

        def receive():
            while self.conn.connecting == True:
                try:
                    data, addr = self.recvfrom(2048)
                    self.conn.receive_packet(Packet.read_from_byte(data))
                except:
                    pass

        self.receiver = Thread(target=receive)
        self.receiver.start()

        self.conn.send_packet(packet=Packet(SYN=True,data=b'\xFF'))
        self.conn.state = State.WAIT_SYN


    def accept(self):
        # server accept a connection and add it to conns
        # return conns[addr], addr
        self.state = State.LISTING
        def receive():
            while True:
                data, addr = self.recvfrom(2048)
                if addr not in self.conns:
                    self.conns[addr] = Connection(addr, self)
                    self.new_conn.put(self.conns[addr])
                packet = Packet.read_from_byte(data)
                self.conns[addr].receive_packet(packet)
        self.receiver = Thread(target=receive)
        self.receiver.start()
        conn = self.new_conn.get()
        return conn, conn.client


    def close(self):
        # shot down conn
        pass


    def recv(self, buffer_size):
        # client recv message
        return self.conn.recv(buffer_size)


    def send(self, data: bytes, flags: int = ...):
        # client send message
        self.conn.send(data, flags)


class Connection():
    def __init__(self, client, socket):
        self.client = client
        self.socket = socket
        self.seq = 0
        self.ack = 0
        self.connecting = True
        self.state = State.CLOSE
        self.packet_send_queue: Queue[Packet] = Queue()      # packet waiting to send
        self.packet_receive_queue: Queue[Packet] = Queue()   # packet waiting to receive
        self.sending_list = []                               # already send but haven't reply
        self.recv_queue: Queue[bytes] = Queue()              # message that already been receive
        self.fsm = FSM(self)
        self.fsm.start()


    def close(self):
        # close connection of conns[addr]
        pass


    def recv(self, buffer_size):
        return self.recv_queue.get()
        # server recv message


    def send(self, data: bytes, flags: int = ...):
        packet = Packet(data=data)
        self.packet_send_queue.put(packet)
        # server send message


    def send_packet(self, packet):
        print("send ",packet)
        self.socket.sendto(packet.transform_to_byte(), self.client)
        self.sending_list.append([packet, time()])


    def receive_packet(self, packet):
        print("receive ",packet)
        self.packet_receive_queue.put(packet)


class State(Enum):
    CLOSE = 0
    LISTING = 1
    WAIT_SYN = 2



class FSM(Thread):
    def __init__(self, conn):
        super().__init__()
        self.conn = conn
        self.state = State.CLOSE


    def run(self):
        alive = True

        while alive:
            try:
                if len(self.conn.packet_send_queue.queue) == 0 :
                    packet = self.conn.packet_send_queue.get(timeout=0.5)
                    self.conn.send_packet(packet)
            except:
                pass

            try:
                packet = self.conn.packet_receive_queue.get()
            except:
                continue
            self.conn.recv_queue.put(packet.payload)
