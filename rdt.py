from enum import Enum, auto
from queue import Queue
from threading import Thread
from time import time, sleep
from typing import Tuple
from packet import Packet
import udp

Address = Tuple[str, int]


class socket(udp.UDPsocket):
    # for a client, self.conn is the connection to server.
    # for a server, 'accept' will return conns[addr] which means the connection to client

    def __init__(self, mode='GBN'):
        super(socket, self).__init__()
        self.conn: Connection
        self.conns: dict[Address: Connection] = {}  # connection set for server
        self.new_conn: Queue[Connection] = Queue()
        self.mode = mode
        assert self.mode == 'GBN' or self.mode == 'SR'

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

        self.conn.send_packet_to_sending_list(packet=Packet(SYN=True, data=b''))
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
        self.conn.send_packet_to_sending_list(Packet(data=b'', FIN=True, seq=self.conn.seq, seq_ack=self.conn.ack), 0.0)
        self.conn.state = State.CLIENT_WAIT_FIN_1
        self.conn.seq_fin = self.conn.seq
        # shot down conn

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
        self.seq_fin = 0
        self.already_ack = 0
        self.swnd_size = 10
        self.max_time = 1.0
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
        s = "send  " + packet.__str__() + "  " + self.state.__str__() + "\n"
        print(s, end='')
        self.socket.sendto(packet.transform_to_byte(), self.client)

    def send_packet_to_sending_list(self, packet, send_time=0.0):
        self.sending_list.append([packet, send_time])

    def receive_packet(self, packet):
        s = "receive  " + packet.__str__() + "  " + self.state.__str__() + "\n"
        print(s, end='')
        if packet.checksum == Packet.calc_checksum(packet) and len(packet.payload) == packet.len:
            self.already_ack = packet.seq_ack
            self.packet_receive_queue.put(packet)
        else:
            s = "checksum error, reject " + packet.__str__() + "  " + "\n"
            print(s, end='')


class State(Enum):
    CLOSE = auto()
    CONNECT = auto()
    CLIENT_WAIT_SYN = auto()
    SERVER_WAIT_SYNACK = auto()
    CLIENT_WAIT_FIN_1 = auto()
    CLIENT_WAIT_FIN_2 = auto()
    CLIENT_TIME_WAIT = auto()
    SERVER_WAIT_FIN = auto()
    SERVER_LAST_ACK = auto()


class FSM(Thread):
    def __init__(self, conn):
        super().__init__()
        self.conn = conn
        self.alive = True
        self.finishing = False

    def run(self):

        while self.alive:

            # retransmit
            if self.conn.state != State.CLOSE:
                sending_list_copy = self.conn.sending_list.copy()
                self.conn.sending_list.clear()
                for i in range(len(sending_list_copy)):
                    packet, send_time = sending_list_copy[i]
                    if packet.seq >= self.conn.already_ack:
                        self.conn.sending_list.append([packet, send_time])
                if self.conn.socket.mode == 'GBN':
                    if len(self.conn.sending_list) != 0 and time() - self.conn.sending_list[0][1] > self.conn.max_time:
                        current_send = 0
                        for packet, send_time in self.conn.sending_list:
                            self.conn.sending_list[current_send][1] = time()
                            self.conn.send_packet(packet)
                            current_send += 1
                            if current_send == self.conn.swnd_size:
                                break

                else:
                    # TODO SR
                    pass

                sending_list_copy = self.conn.sending_list.copy()
                self.conn.sending_list.clear()
                for i in range(len(sending_list_copy)):
                    if i == self.conn.swnd_size:
                        break
                    packet, send_time = sending_list_copy[i]
                    if not packet.ACK or packet.SYN:
                        self.conn.sending_list.append([packet, send_time])

                # send the message in send waiting list
                # TODO add detail
                if len(self.conn.packet_send_queue.queue) != 0 and self.conn.state == State.CONNECT:
                    data = self.conn.packet_send_queue.get()
                    if type(data) == Packet:
                        data.seq = self.conn.seq
                        data.seq_ack = self.conn.ack
                        self.conn.seq += data.len
                        self.conn.send_packet_to_sending_list(data)
                    else:
                        packet = Packet(data=data, seq=self.conn.seq, seq_ack=self.conn.ack)
                        self.conn.seq += packet.len
                        self.conn.send_packet_to_sending_list(packet)

            # receive the message from receive waiting list
            try:
                packet = self.conn.packet_receive_queue.get(timeout=0.5)
            except:
                if self.conn.state == State.SERVER_WAIT_FIN and len(self.conn.sending_list) == 0:
                    self.conn.state = State.SERVER_LAST_ACK
                    self.conn.send_packet_to_sending_list(Packet(data=b'', FIN=True, seq=self.conn.seq, seq_ack=self.conn.ack), 0.0)
                elif self.conn.state == State.CLIENT_TIME_WAIT:
                    sleep(2)
                    self.conn.close()
                    self.alive = False

                print("NO packet")
                continue


            if self.conn.socket.mode == 'GBN':
                if packet.seq > self.conn.ack and self.conn.state not in (State.CLIENT_WAIT_FIN_2, State.CLIENT_WAIT_FIN_1) and not packet.FIN:
                    s = "come early, reject " + packet.__str__() + "\n"
                    print(s, end='')
                    continue
            else:
                # TODO SR
                pass

            # server receive first hand shake
            if packet.SYN and not packet.ACK:
                self.conn.state = State.SERVER_WAIT_SYNACK
                self.conn.ack = packet.seq + 1
                packet = Packet(data=b'', seq=self.conn.seq, seq_ack=self.conn.ack, SYN=True, ACK=True)
                self.conn.send_packet_to_sending_list(packet, 0.0)

            # client receive reply of second hand shake
            elif packet.SYN and packet.ACK:
                self.conn.state = State.CONNECT
                self.conn.seq = packet.seq_ack
                self.conn.ack = packet.seq + 1
                packet = Packet(data=b'', seq=self.conn.seq, seq_ack=self.conn.ack, ACK=True)
                self.conn.send_packet(packet)

            # server receive third hand shake
            elif packet.ACK and self.conn.state == State.SERVER_WAIT_SYNACK:
                self.conn.state = State.CONNECT
                self.conn.seq = packet.seq_ack

            # TODO FIN
            elif self.conn.state == State.CLIENT_WAIT_FIN_1 and packet.ACK and (packet.seq_ack == self.conn.seq_fin + 1):
                self.conn.state = State.CLIENT_WAIT_FIN_2
                self.conn.ack = max(self.conn.ack, packet.seq + 1)
                self.conn.seq += 1

            elif self.conn.state == State.SERVER_LAST_ACK and packet.ACK:
                self.conn.close()
                self.alive = False

            elif packet.FIN:
                if self.conn.state == State.CONNECT:
                    self.conn.state = State.SERVER_WAIT_FIN
                    self.conn.ack = max(self.conn.ack, packet.seq + 1)
                    self.conn.send_packet_to_sending_list(Packet(ACK=True, seq=self.conn.seq, seq_ack=self.conn.ack),
                                                          0.0)
                    self.conn.seq += 1

                elif self.conn.state == State.CLIENT_WAIT_FIN_2:
                    self.conn.state = State.CLIENT_TIME_WAIT
                    self.conn.ack = max(self.conn.ack, packet.seq + 1)
                    self.conn.send_packet_to_sending_list(Packet(ACK=True, seq=self.conn.seq, seq_ack=self.conn.ack),
                                                          0.0)
                    self.conn.seq += 1


            # if receive a reply
            elif packet.ACK and packet.len == 0 and self.conn.state == State.CONNECT:
                if self.conn.socket.mode == 'GBN':
                    self.conn.already_ack = max(self.conn.already_ack, packet.seq_ack)
                else:
                    # TODO SR
                    pass

            # receive a request
            elif not packet.ACK and self.conn.state == State.CONNECT:
                self.conn.ack = max(self.conn.ack, packet.seq + packet.len)
                self.conn.recv_queue.put(packet.payload)
                self.conn.send_packet_to_sending_list(Packet(ACK=True, seq=self.conn.seq, seq_ack=self.conn.ack), 0.0)
