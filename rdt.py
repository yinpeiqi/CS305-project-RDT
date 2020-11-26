from enum import Enum
from queue import Queue
from threading import Thread
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

    def connect(self, address: Address):
        # client connect to server, create conn
        self.conn = Connection(address, self)
        pass

    def accept(self):
        # server accept a connection and add it to conns
        # return conns[addr], addr
        pass

    def close(self):
        # shot down conn
        pass

    def recv(self, buffer_size):
        return self.conn.recv(buffer_size)
        # client recv message
        pass

    def send(self, data: bytes, flags: int = ...):
        self.conn.send(data, flags)
        # client send message
        pass


class Connection():
    def __init__(self, client, socket):
        self.client = client
        self.socket = socket
        self.seq = 0
        self.ack = 0
        self.packet_send_queue: Queue[Packet] = Queue()
        self.packet_receive_queue: Queue[Packet] = Queue()
        self.fsm = FSM(self)
        self.fsm.start()
        pass

    def close(self):
        # close connection of conns[addr]
        pass

    def recv(self, buffer_size):
        return self.packet_receive_queue.get(timeout=0.5)
        # server recv message
        pass

    def send(self, data: bytes, flags: int = ...):
        packet = Packet(data=data)
        self.packet_send_queue.put(packet)
        # server send message
        pass

    def send_packet(self):
        self.socket.sendto(self.packet_send_queue.get().transform_to_byte(), self.client)

    def receive_packet(self, buffer_size):
        self.packet_receive_queue.put(self.socket.recvfrom(buffer_size))

class State(Enum):
    CLOSE = 0
    LISTING = 1


class FSM(Thread):

    def __init__(self, conn):
        super().__init__()
        self.conn = conn
        self.state = State.CLOSE

    def run(self):
        alive = True
        # do all operations
