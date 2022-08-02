FLAG_PAYLOAD = 1 << 0
FLAG_SYN = 1 << 1
FLAG_FIN = 1 << 2
FLAG_ACK = 1 << 3


class package:
    flag: int
    seq: int
    ack: int
    payload: bytes

    def __init__(self, flag: int = 0, seq: int = 0, ack: int = 0, payload: bytes = bytes()):
        self.flag = flag
        self.seq = seq
        self.ack = ack
        self.payload = payload

    def eq_flag(self, flag: int = 0) -> int:
        return (self.flag & flag) == self.flag and (self.flag & flag) == flag


def serialize(obj: package) -> bytes:
    bs = bytes()
    bs += obj.flag.to_bytes(1, 'big')
    if (obj.flag & FLAG_PAYLOAD) == FLAG_PAYLOAD:
        bs += obj.payload
        return bs
    else:
        bs += obj.seq.to_bytes(4, 'big')
        bs += obj.ack.to_bytes(4, 'big')
        return bs


def un_serialize(bs) -> package:
    flag_bs = bs[:1]
    bs = bs[1:]
    flag = int.from_bytes(flag_bs, 'big')
    if (flag & FLAG_PAYLOAD) == FLAG_PAYLOAD:
        payload_bs = bs
        return package(flag=flag, payload=payload_bs)
    else:
        seq_bs = bs[:4]
        bs = bs[4:]
        seq = int.from_bytes(seq_bs, 'big')

        ack_bs = bs[:4]
        ack = int.from_bytes(ack_bs, 'big')
        return package(flag=flag, seq=seq, ack=ack)
