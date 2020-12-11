from USocket import UnreliableSocket
from threading import Thread
from time import time, sleep
from typing import Tuple
from enum import Enum, auto
from queue import Queue

Address = Tuple[str, int]


class RDTSocket(UnreliableSocket):

    def __init__(self, rate=None, debug=True, mode='GBN'):
        super().__init__(rate=rate)
        self._rate = rate
        self._send_to = None
        self._recv_from = None
        self.debug = debug
        self.conn: Connection
        self.conns: dict[Address: Connection] = {}  # connection set for server
        self.new_conn: Queue[Connection] = Queue()
        self.mode = mode
        assert self.mode == 'GBN' or self.mode == 'SR'

    def accept(self):
        # server accept a connection and add it to conns
        # return conns[addr], addr

        def receive():
            while True:
                data, addr = self.recvfrom(65536)
                packet = Packet.read_from_byte(data)
                if packet.checksum == Packet.calc_checksum(packet) and len(packet.payload) == packet.len:
                    if addr not in self.conns and (not packet.SYN or packet.FIN):
                        continue
                    if addr not in self.conns:
                        self.conns[addr] = Connection(addr, self)
                        self.new_conn.put(self.conns[addr])

                    self.conns[addr].receive_packet(packet)

        self.receiver = Thread(target=receive)
        self.receiver.start()

        conn = self.new_conn.get()
        return conn, conn.client

    def connect(self, address: (str, int)):
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

    def recv(self, bufsize: int) -> bytes:
        # client recv message
        return self.conn.recv(bufsize)

    def send(self, data: bytes, flags: int = ...):
        # client send message
        self.conn.send(data, flags)

    def close(self):
        while len(self.conn.sending_list) != 0:
            sleep(1)
        if self.mode == 'SR':
            self.conn.unACK[self.conn.seq + 1] = True
        self.conn.send_packet_to_sending_list(Packet(data=b'', FIN=True, seq=self.conn.seq, seq_ack=self.conn.ack), 0.0)
        self.conn.state = State.CLIENT_WAIT_FIN_1
        self.conn.seq_fin = self.conn.seq

    def set_send_to(self, send_to):
        self._send_to = send_to

    def set_recv_from(self, recv_from):
        self._recv_from = recv_from


class Connection:
    def __init__(self, client, socket):
        self.client: Address = client
        self.socket = socket
        self.seq = 0
        self.ack = 0
        self.seq_fin = 0
        self.already_ack = 0
        self.swnd_size = 5
        self.min_swnd_size = 5
        self.max_time = 1.0
        self.connecting = True
        self.fin_cnt = 0
        self.max_fin_cnt = 20
        self.state = State.CLOSE
        self.close_timer = 0
        self.max_close_time = 10
        self.second_handshaking = None
        self.packet_send_queue = Queue()  # packet or data waiting to send
        self.packet_receive_queue: Queue[Packet] = Queue()  # packet waiting to receive
        self.sending_list = []  # already send but haven't reply
        if self.socket.mode == 'SR':
            self.unACK: dict[int: bool] = {}  # already send but unACK
            self.next_ack = 1  # if next_ack was receive then bring it to rece_queue
            self.receive_dict: dict[int: Packet] = {}  # already receive but haven't been read
        self.recv_queue: Queue[bytes] = Queue()  # message that already been receive
        self.fsm = FSM(self)
        self.fsm.start()
        self.rest_mess = None

    def close(self):
        # close connection of conns[addr]
        if self.client in self.socket.conns:
            del self.socket.conns[self.client]
        self.close_connection()
        pass

    def close_connection(self):
        self.state = State.FINISH
        self.connecting = False

    def recv(self, buffer_size):
        try:
            if self.rest_mess is None:
                mess = self.recv_queue.get(buffer_size/self.socket._rate)
                if len(mess) > buffer_size:
                    self.rest_mess = mess[buffer_size:]
                    mess = mess[:buffer_size]
            else:
                if len(self.rest_mess) > buffer_size:
                    mess = self.rest_mess[:buffer_size]
                    self.rest_mess = self.rest_mess[buffer_size:]
                else:
                    mess = self.rest_mess
                    self.rest_mess = None
        except:
            mess = False
        return mess
        # server recv message

    def send(self, data: bytes, flags=...):
        self.packet_send_queue.put(data)
        # server send message

    def send_packet(self, packet):
        if self.socket.debug:
            s = "send  " + packet.__str__() + "  " + self.state.__str__() + "\n"
            print(s, end='')
        self.socket.sendto(packet.transform_to_byte(), self.client)

    def send_packet_to_sending_list(self, packet, send_time=0.0):
        if self.socket.mode == 'SR' and packet.seq + packet.len not in self.unACK:
            self.unACK[packet.seq + packet.len] = True
        self.sending_list.append([packet, send_time])

    def receive_packet(self, packet):
        if self.socket.debug:
            s = "receive  " + packet.__str__() + "  " + self.state.__str__() + "\n"
            print(s, end='')
        if packet.checksum == Packet.calc_checksum(packet) and len(packet.payload) == packet.len:
            self.already_ack = packet.seq_ack
            self.packet_receive_queue.put(packet)
        else:
            if self.socket.debug:
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
    FINISH = auto()


class FSM(Thread):
    def __init__(self, conn):
        super().__init__()
        self.conn = conn
        self.sent = 0

    def run(self):

        notReceive = 0

        while True:

            if self.conn.state == State.FINISH and self.conn.socket.debug:
                print("Finish\n", end='')
                break

            # retransmit
            if self.conn.state != State.CLOSE:

                sending_list_copy = self.conn.sending_list.copy()
                self.conn.sending_list.clear()
                hit = 0

                if self.conn.socket.mode == 'GBN':
                    for i in range(len(sending_list_copy)):
                        packet, send_time = sending_list_copy[i]
                        if packet.seq >= self.conn.already_ack:
                            self.conn.sending_list.append([packet, send_time])
                        else:
                            hit += 1

                elif self.conn.socket.mode == 'SR':
                    for i in range(len(sending_list_copy)):
                        packet, send_time = sending_list_copy[i]
                        expect_ack = packet.seq + packet.len
                        if packet.FIN:
                            expect_ack += 1
                        if self.conn.unACK[expect_ack] and not (
                                self.conn.state in (State.SERVER_LAST_ACK, State.CLIENT_TIME_WAIT) and packet.len > 0):
                            self.conn.sending_list.append([packet, send_time])
                        else:
                            hit += 1

                self.conn.swnd_size = max(self.conn.min_swnd_size, hit*2)
                print(hit, self.conn.swnd_size,len(self.conn.sending_list))

                tot_data = 0
                if len(self.conn.sending_list) != 0 and time() - self.conn.sending_list[0][1] > self.conn.max_time:
                    self.sent = 0
                    for packet, send_time in self.conn.sending_list:
                        self.conn.sending_list[self.sent][1] = time()
                        self.conn.send_packet(packet)
                        tot_data += packet.len
                        self.sent += 1
                        if self.sent == self.conn.swnd_size:
                            break
                    if self.conn.socket._rate is not None:
                        sleep(tot_data*0.2/self.conn.socket._rate)

                sending_list_copy = self.conn.sending_list.copy()
                self.conn.sending_list.clear()
                for i in range(len(sending_list_copy)):
                    packet, send_time = sending_list_copy[i]
                    if not packet.ACK or packet.SYN:
                        self.conn.sending_list.append([packet, send_time])

                temp = 0
                # send the message in send waiting list
                while len(self.conn.packet_send_queue.queue) != 0 and self.conn.state == State.CONNECT and len(self.conn.sending_list)<self.conn.swnd_size*2:
                    temp+=1
                    data = self.conn.packet_send_queue.get()
                    packet = Packet(data=data, seq=self.conn.seq, seq_ack=self.conn.ack)
                    self.conn.seq += packet.len
                    self.conn.send_packet_to_sending_list(packet)
                    # print("temp: "+str(temp)+"len: "+str(len(self.conn.packet_send_queue.queue))+" sending_list: "+str(len(self.conn.sending_list)))


            receive_cnt = 0
            while receive_cnt < max(self.conn.swnd_size,200):
                # print(receive_cnt)
                receive_cnt += 1

                # receive the message from receive waiting list
                try:
                    packet = self.conn.packet_receive_queue.get(timeout=0.2)
                    if not (self.conn.state == State.SERVER_LAST_ACK and packet.ACK):
                        self.conn.fin_cnt = 0
                    notReceive = 0
                except:
                    if self.conn.state == State.SERVER_LAST_ACK:
                        if self.conn.socket.mode == 'GBN':
                            self.conn.send_packet_to_sending_list(
                                Packet(ACK=True, seq=self.conn.seq - 1, seq_ack=self.conn.ack), 0.0)
                        elif self.conn.socket.mode == 'SR':
                            self.conn.send_packet_to_sending_list(
                                Packet(ACK=True, seq=self.conn.seq, seq_ack=self.conn.ack), 0.0)
                        self.conn.fin_cnt += 1
                        if self.conn.fin_cnt > self.conn.max_fin_cnt:
                            self.conn.close()
                            break

                    elif self.conn.state == State.SERVER_WAIT_FIN:
                        self.conn.state = State.SERVER_LAST_ACK
                        if self.conn.socket.mode == 'SR':
                            self.conn.unACK[self.conn.seq + 1] = True
                        self.conn.send_packet_to_sending_list(
                            Packet(data=b'', FIN=True, seq=self.conn.seq, seq_ack=self.conn.ack), 0.0)

                    elif self.conn.state == State.CLIENT_TIME_WAIT:
                        self.conn.send_packet_to_sending_list(
                            Packet(ACK=True, seq=self.conn.seq - 1, seq_ack=self.conn.ack), 0.0)
                        if time() - self.conn.close_timer > self.conn.max_close_time:
                            self.conn.close()

                    elif self.conn.state == State.CONNECT:
                        notReceive += 1
                        if notReceive > 200:
                            self.conn.close_connection()
                            break

                    if self.conn.socket.debug:
                        print("NO packet\n", end='')
                    if receive_cnt < 5:
                        continue
                    else:
                        print(receive_cnt)
                        break

                if self.conn.socket.mode == 'GBN':
                    if packet.seq > self.conn.ack \
                            and self.conn.state not in (State.CLIENT_WAIT_FIN_2, State.CLIENT_WAIT_FIN_1) \
                            and not packet.FIN and not packet.ACK:
                        if self.conn.socket.debug:
                            s = "come early, reject " + packet.__str__() + "\n"
                            print(s, end='')
                        continue

                # server receive first hand shake
                if packet.SYN and not packet.ACK and self.conn.state == State.CLOSE:
                    self.conn.state = State.SERVER_WAIT_SYNACK
                    self.conn.ack = packet.seq + 1
                    self.conn.send_packet_to_sending_list(
                        Packet(data=b'', seq=self.conn.seq, seq_ack=self.conn.ack, SYN=True, ACK=True), 0.0)

                # client receive reply of second hand shake
                elif packet.SYN and packet.ACK and self.conn.state == State.CLIENT_WAIT_SYN:
                    self.conn.state = State.CONNECT
                    if self.conn.socket.mode == 'SR':
                        self.conn.unACK[self.conn.seq] = False
                    self.conn.seq = packet.seq_ack
                    self.conn.ack = packet.seq + 1
                    self.second_handshaking = Packet(data=b'', seq=self.conn.seq, seq_ack=self.conn.ack, ACK=True)
                    self.conn.send_packet(self.second_handshaking)

                # there is an error in the third hand shake
                elif packet.len > 0 and self.conn.state == State.SERVER_WAIT_SYNACK and not packet.ACK:
                    self.conn.send_packet(
                        Packet(data=b'', seq=self.conn.seq, seq_ack=self.conn.ack, SYN=True, ACK=True))

                # there is an error in the third hand shake
                elif packet.SYN and packet.ACK and self.conn.state == State.CONNECT:
                    self.conn.send_packet(self.second_handshaking)

                # server receive third hand shake
                elif packet.ACK and self.conn.state == State.SERVER_WAIT_SYNACK:
                    self.conn.state = State.CONNECT
                    if self.conn.socket.mode == 'SR':
                        self.conn.unACK[self.conn.seq] = False
                    self.conn.seq = packet.seq_ack

                # FIN
                elif self.conn.state == State.CLIENT_WAIT_FIN_1 and packet.ACK and (
                        packet.seq_ack == self.conn.seq_fin + 1):
                    self.conn.state = State.CLIENT_WAIT_FIN_2
                    self.conn.ack = max(self.conn.ack, packet.seq + 1)
                    self.conn.seq += 1

                elif self.conn.state == State.SERVER_LAST_ACK and packet.ACK:
                    self.conn.close()
                    break

                elif packet.FIN:
                    if self.conn.state == State.CONNECT:
                        self.conn.state = State.SERVER_WAIT_FIN
                        self.conn.ack = max(self.conn.ack, packet.seq + 1)
                        self.conn.send_packet_to_sending_list(
                            Packet(ACK=True, seq=self.conn.seq, seq_ack=self.conn.ack), 0.0)
                        self.conn.seq += 1

                    elif self.conn.state == State.CLIENT_WAIT_FIN_2:
                        self.conn.state = State.CLIENT_TIME_WAIT
                        self.conn.ack = max(self.conn.ack, packet.seq + 1)
                        self.conn.send_packet_to_sending_list(
                            Packet(ACK=True, seq=self.conn.seq, seq_ack=self.conn.ack), 0.0)
                        self.conn.seq += 1
                        self.conn.close_timer = time()


                # if receive a reply
                elif packet.ACK and packet.len == 0 and self.conn.state == State.CONNECT:
                    if self.conn.socket.mode == 'GBN':
                        self.conn.already_ack = max(self.conn.already_ack, packet.seq_ack)
                    elif self.conn.socket.mode == 'SR':
                        self.conn.unACK[packet.seq_ack] = False

                # receive a request
                elif not packet.ACK and self.conn.state == State.CONNECT:
                    if self.conn.socket.mode == 'GBN':
                        if packet.seq == self.conn.ack:
                            self.conn.recv_queue.put(packet.payload)
                        self.conn.ack = max(self.conn.ack, packet.seq + packet.len)
                        self.conn.send_packet(Packet(ACK=True, seq=self.conn.seq, seq_ack=self.conn.ack))
                    elif self.conn.socket.mode == 'SR':
                        self.conn.receive_dict[packet.seq] = packet
                        expect_ack = packet.seq + packet.len
                        if packet.FIN:
                            expect_ack += 1
                        self.conn.send_packet(Packet(ACK=True, seq=self.conn.seq, seq_ack=expect_ack))

            if self.conn.socket.mode == 'SR' and self.conn.state == State.CONNECT:
                while self.conn.next_ack in self.conn.receive_dict:
                    self.conn.recv_queue.put(self.conn.receive_dict[self.conn.next_ack].payload)
                    self.conn.ack = self.conn.next_ack
                    self.conn.next_ack += self.conn.receive_dict[self.conn.next_ack].len


class Packet:
    """
    Reliable Data Transfer Segment Format:

    | EMPTY |  SYN  |  FIN  |  ACK  |  SEQ  |  SEQ ACK |  LEN  |  CHECKSUM |  PAYLOAD  |
    |5 bits | 1 bit | 1 bit | 1 bit | 4 byte|  4 byte  | 4 byte|   2 byte  |    LEN    |

    """

    def __init__(self, SYN=False, ACK=False, FIN=False, seq=0, seq_ack=0, data=b''):
        self.SYN = SYN
        self.ACK = ACK
        self.FIN = FIN
        self.seq = seq
        self.seq_ack = seq_ack
        self.len = len(data)
        self.payload = data
        self.checksum = Packet.calc_checksum(self)

    @staticmethod
    def calc_checksum(packet):
        data = b''
        flag: int = packet.SYN * 4 + packet.ACK * 2 + packet.FIN * 1
        data += int.to_bytes(flag, 2, byteorder='big')
        data += int.to_bytes(packet.seq, 4, byteorder='big')
        data += int.to_bytes(packet.seq_ack, 4, byteorder='big')
        data += int.to_bytes(packet.len, 4, byteorder='big')
        data += packet.payload
        sum = 0
        count = 0
        for byte in data:
            if count % 2 == 0:
                sum += 256 * int(byte)
            else:
                sum += byte
            count += 1
        sum = -(sum % 65536)
        return (sum & 65535)

    def transform_to_byte(self) -> bytes:
        data = b''

        flag: int = self.SYN * 4 + self.ACK * 2 + self.FIN * 1

        data += int.to_bytes(flag, 2, byteorder='big')
        data += int.to_bytes(self.seq, 4, byteorder='big')
        data += int.to_bytes(self.seq_ack, 4, byteorder='big')
        data += int.to_bytes(self.len, 4, byteorder='big')
        data += int.to_bytes(self.checksum, 2, byteorder='big')
        data += self.payload

        return data

    @staticmethod
    def read_from_byte(data: bytes) -> 'Packet':
        """Parse raw bytes into an RDT Segment Packet"""
        packet = Packet()

        flag = int.from_bytes(data[0:2], byteorder='big')
        packet.SYN, packet.ACK, packet.FIN = flag & 4 != 0, flag & 2 != 0, flag & 1 != 0
        packet.seq = int.from_bytes(data[2:6], byteorder='big')
        packet.seq_ack = int.from_bytes(data[6:10], byteorder='big')
        packet.len = int.from_bytes(data[10:14], byteorder='big')
        packet.checksum = int.from_bytes(data[14:16], byteorder='big')
        packet.payload = data[16:]

        return packet

    def __str__(self):
        res = ''
        if self.SYN:
            res += "SYN, "
        if self.ACK:
            res += "ACK, "
        if self.FIN:
            res += "FIN, "
        res += "[seq={}, ack={}, len={}, data={}]".format(self.seq, self.seq_ack, self.len, self.payload)
        return res