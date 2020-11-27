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
        self.checksum = Packet.calc_checksum(self.payload)


    @staticmethod
    def calc_checksum(payload:bytes):
        sum = 0
        count = 0
        for byte in payload:
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

        try:
            assert packet.len == len(packet.payload)
            assert packet.checksum == Packet.calc_checksum(packet.payload)

            return packet
        except AssertionError as e:
            raise  ValueError from e


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

if __name__ == "__main__":
    packet = Packet(False, True, True, 1, 1, b'\xff\xcc\xdd')
    print(packet)
    data = packet.transform_to_byte()
    for b in data:
        print(b, end=' ')
    print()

    rec_packet = Packet.read_from_byte(data)
    data = rec_packet.transform_to_byte()
    for b in data:
        print(b, end=' ')
    print()