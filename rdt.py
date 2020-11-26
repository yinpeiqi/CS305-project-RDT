from typing import Tuple

import udp

class socket(udp.UDPsocket):
    def __init__(self):
        super(socket, self).__init__()

    def connect(self, address: Tuple[str, int]) -> int:
        pass

    def accept(self):
        pass

    def close(self):
        pass

    def recv(self, buffer_size):
        pass

    def send(self, data: bytes):
        pass