from socket import *
import random, time


class UDPsocket(socket):
    def __init__(self, loss_rate=0.1, corruption_rate=0.1, delay_rate=0, delay=10):
        super().__init__(AF_INET, SOCK_DGRAM)
        self.loss_rate = loss_rate
        self.corruption_rate = corruption_rate
        self.delay_rate = delay_rate
        self.delay = delay
        self.time_out = 0.5

    def settimeout(self, value):
        self.time_out = value

    def recvfrom(self, bufsize=2048):
        if random.random() < self.delay_rate:
            time.sleep(self.time_out)
            return None

        data, addr = super().recvfrom(bufsize)
        if random.random() < self.loss_rate:
            return self.recvfrom(bufsize)
        if random.random() < self.corruption_rate:
            return self._corrupt(data), addr
        return data, addr

    def recv(self, bufsize=2048):
        data, addr = self.recvfrom(bufsize)
        return data

    def _corrupt(self, data: bytes) -> bytes:
        raw = list(data)
        for i in range(0, random.randint(0, 3)):
            pos = random.randint(0, len(raw) - 1)
            raw[pos] = random.randint(0, 255)
        return bytes(raw)
