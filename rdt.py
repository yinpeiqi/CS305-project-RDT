from enum import Enum
from threading import Thread
from typing import Tuple
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
        # client recv message
        pass

    def send(self, data: bytes, flags: int = ...):
        # client send message
        pass


class Connection():
    def __init__(self, client, socket):
        self.client = client
        self.socket = socket
        self.seq = 0
        self.ack = 0
        self.fsm = FSM(self)
        self.fsm.start()
        pass

    def close(self):
        # close connection of conns[addr]
        pass

    def recv(self, buffer_size):
        # server recv message
        pass

    def send(self, data: bytes, flags: int = ...):
        # server send message
        pass


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
