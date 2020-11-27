from enum import Enum, auto
from queue import Queue
from threading import Thread
from time import time
from typing import Tuple
from packet import Packet
import udp

Address = Tuple[str, int]


class socket(udp.UDPsocket):
    # for a client, self.conn is the connection to server.
    # for a server, 'accept' will return conns[addr] which means the connection to client

    def __init__(self):
        super(socket, self).__init__()
        self.conn: Connection
        self.conns: dict[Address: Connection] = {}  # connection set for server
        self.new_conn: Queue[Connection] = Queue()

    def connect(self, address: Address):
        # client connect to server, create conn
        self.conn = Connection(address, self)

        def receive():
            while self.conn.connecting == True:
                try:
                    data, addr = self.recvfrom(65536)
                    self.conn.receive_packet(Packet.read_from_byte(data))
                except:
                    pass

        self.receiver = Thread(target=receive)
        self.receiver.start()

        self.conn.send_packet(packet=Packet(SYN=True, data=b'\xAC'))
        self.conn.state = State.CLIENT_WAIT_SYN

    def accept(self):
        # server accept a connection and add it to conns
        # return conns[addr], addr

        def receive():
            while True:
                data, addr = self.recvfrom(65536)
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
        # TODO unfinished
        self.conn.send_packet(Packet(data=b'client FIN', FIN=True))
        self.conn.state = State.CLIENT_WAIT_FIN_1
        # shot down conn
        pass

    def recv(self, buffer_size):
        # client recv message
        return self.conn.recv(buffer_size)

    def send(self, data: bytes, flags: int = ...):
        # client send message
        self.conn.send(data, flags)


class Connection:
    def __init__(self, client, socket):
        self.client = client
        self.socket = socket
        self.seq = 0
        self.ack = 0
        self.connecting = True
        self.state = State.CLOSE
        self.packet_send_queue = Queue()  # packet or data waiting to send
        self.packet_receive_queue: Queue[Packet] = Queue()  # packet waiting to receive
        self.sending_list = []  # already send but haven't reply
        self.recv_queue: Queue[bytes] = Queue()  # message that already been receive
        self.fsm = FSM(self)
        self.fsm.start()

    def close(self):
        # close connection of conns[addr]
        # TODO unfinished
        if self.client in self.socket.conns:
            del self.socket.conns[self.client]
        self.close_connection()
        pass

    def close_connection(self):
        # TODO unfinished
        self.state = State.CLOSE
        self.connecting = False

    def recv(self, buffer_size):
        return self.recv_queue.get()
        # server recv message

    def send(self, data: bytes, flags=...):
        self.packet_send_queue.put(data)
        # server send message

    def send_packet(self, packet):
        print("send ", packet, self.state)
        self.socket.sendto(packet.transform_to_byte(), self.client)
        self.sending_list.append([packet, time()])

    def receive_packet(self, packet):
        print("receive ", packet, self.state)
        self.packet_receive_queue.put(packet)


class State(Enum):
    CLOSE = auto()
    CONNECT = auto()
    CLIENT_WAIT_SYN = auto()
    CLIENT_WAIT_FIN_1 = auto()
    CLIENT_WAIT_FIN_2 = auto()
    SERVER_WAIT_FIN = auto()


class FSM(Thread):
    def __init__(self, conn):
        super().__init__()
        self.conn = conn

    def run(self):
        alive = True

        while alive:
            # send the message in send waiting list
            # TODO add detail
            try:
                if len(self.conn.packet_send_queue.queue) == 0 and self.conn.state == State.CONNECT:
                    data = self.conn.packet_send_queue.get(timeout=0.5)
                    if type(data) == Packet:
                        data.seq = self.conn.seq
                        data.seq_ack = self.conn.ack
                        self.conn.seq += data.len
                        self.conn.send_packet(data)
                    else:
                        packet = Packet(data=data, seq=self.conn.seq, seq_ack=self.conn.ack)
                        self.conn.seq += packet.len
                        self.conn.send_packet(packet)
            except:
                pass

            # receive the message from receive waiting list
            try:
                packet = self.conn.packet_receive_queue.get(timeout=0.5)
            except:
                continue

            # server receive first hand shake
            if packet.SYN and not packet.ACK and self.conn.state == State.CLOSE:
                self.conn.state = State.CONNECT
                self.conn.ack = packet.seq + 1
                self.conn.send_packet(Packet(data=b'ac', seq=self.conn.seq, seq_ack=self.conn.ack, SYN=True, ACK=True))
            # client receive reply of second hand shake
            elif packet.SYN and packet.ACK and self.conn.state == State.CLIENT_WAIT_SYN:
                self.conn.state = State.CONNECT
                self.conn.seq = packet.seq_ack
                self.conn.ack = packet.seq + 1
                self.conn.send_packet(Packet(data=b'ac', seq=self.conn.seq, seq_ack=self.conn.ack))


            # elif self.conn.state == State.CONNECT:
            self.conn.recv_queue.put(packet.payload)
