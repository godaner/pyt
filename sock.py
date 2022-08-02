import logging
import queue
import socket
import threading
import traceback

import transitions

import protocol

# status
STATUS_CLOSED = "STATUS_CLOSED"
# STATUS_LISTEN = "LISTEN"
STATUS_SYN_SENT = "STATUS_SYN_SENT"
STATUS_SYN_RCVD = "STATUS_SYN_RCVD"
STATUS_ESTABLISHED = "STATUS_ESTABLISHED"
STATUS_FIN_WAIT_1 = "STATUS_FIN_WAIT_1"
STATUS_FIN_WAIT_2 = "STATUS_FIN_WAIT_2"
STATUS_TIME_WAIT = "STATUS_TIME_WAIT"
STATUS_CLOSE_WAIT = "STATUS_CLOSE_WAIT"
STATUS_LAST_ACK = "STATUS_LAST_ACK"

# event
EVENT_CLI_SEND_SYN1 = "EVENT_CLI_SEND_SYN1"
EVENT_SRV_RECV_SYN1_AND_SEND_SYN2 = "EVENT_SRV_RECV_SYN1_AND_SEND_SYN2"
EVENT_CLI_RECV_SYN2_AND_SEND_SYN3 = "EVENT_CLI_RECV_SYN2_AND_SEND_SYN3"
EVENT_SRV_RECV_SYN3 = "EVENT_SRV_RECV_SYN3"

EVENT_SEND_FIN1 = "EVENT_SEND_FIN1"
EVENT_RECV_FIN1_AND_SEND_FIN2 = "EVENT_RECV_FIN1_AND_SEND_FIN2"
EVENT_RECV_FIN2 = "EVENT_RECV_FIN2"
EVENT_SEND_FIN3 = "EVENT_SEND_FIN3"
EVENT_RECV_FIN3_AND_SEND_FIN4 = "EVENT_RECV_FIN3_AND_SEND_FIN4"
EVENT_RECV_FIN4 = "EVENT_RECV_FIN4"

EVENT_WAIT_2MSL = "EVENT_WAIT_2MSL"

BUF_SIZE = 548

type_cli = 0x00000001
type_srv = 0x00000002


class innerSock(socket.socket):

    def __init__(self, sock: socket.socket, peer_addr) -> None:
        self._t = type_srv
        self._seq = 0
        self._sock = sock
        self._peer_addr = peer_addr
        self._logger = logging.getLogger()
        self._cli_wait_syn2_event = threading.Event()
        self._fsm = transitions.Machine(model=self,
                                        states=[STATUS_CLOSED, STATUS_SYN_RCVD, STATUS_SYN_SENT, STATUS_ESTABLISHED,
                                                STATUS_FIN_WAIT_1,
                                                STATUS_FIN_WAIT_2, STATUS_TIME_WAIT, STATUS_CLOSE_WAIT,
                                                STATUS_LAST_ACK],
                                        initial=STATUS_CLOSED)
        # SYN
        self._fsm.add_transition(trigger=EVENT_CLI_SEND_SYN1, source=STATUS_CLOSED, dest=STATUS_SYN_SENT,
                                 before=self._cli_send_syn1)
        self._fsm.add_transition(trigger=EVENT_SRV_RECV_SYN1_AND_SEND_SYN2, source=[STATUS_CLOSED, STATUS_SYN_RCVD],
                                 dest=STATUS_SYN_RCVD,
                                 before=self._srv_recv_syn1_and_send_syn2)

        self._fsm.add_transition(trigger=EVENT_CLI_RECV_SYN2_AND_SEND_SYN3,
                                 source=[STATUS_SYN_SENT, STATUS_ESTABLISHED],
                                 dest=STATUS_ESTABLISHED,
                                 before=self._cli_recv_syn2_and_send_syn3)
        self._fsm.add_transition(trigger=EVENT_SRV_RECV_SYN3, source=[STATUS_SYN_RCVD, STATUS_ESTABLISHED],
                                 dest=STATUS_ESTABLISHED,
                                 before=self._srv_recv_syn3)

        # FIN
        '''
        self._fsm.add_transition(trigger=EVENT_SEND_FIN1, source=STATUS_ESTABLISHED, dest=STATUS_FIN_WAIT_1,
                                 before=self._send_fin1)
        self._fsm.add_transition(trigger=EVENT_RECV_FIN1_AND_SEND_FIN2, source=STATUS_ESTABLISHED,
                                 dest=STATUS_CLOSE_WAIT,
                                 before=self._recv_fin1_and_send_fin2)

        self._fsm.add_transition(trigger=EVENT_RECV_FIN2, source=STATUS_FIN_WAIT_1, dest=STATUS_FIN_WAIT_2,
                                 before=self._recv_fin2)
        self._fsm.add_transition(trigger=EVENT_SEND_FIN3, source=STATUS_CLOSE_WAIT, dest=STATUS_LAST_ACK,
                                 before=self._send_fin3)

        self._fsm.add_transition(trigger=EVENT_RECV_FIN3_AND_SEND_FIN4, source=STATUS_FIN_WAIT_2, dest=STATUS_TIME_WAIT,
                                 before=self._recv_fin3_and_send_fin4)
        self._fsm.add_transition(trigger=EVENT_RECV_FIN4, source=STATUS_LAST_ACK, dest=STATUS_CLOSED,
                                 before=self._recv_fin4)

        self._fsm.add_transition(trigger=EVENT_WAIT_2MSL, source=STATUS_TIME_WAIT, dest=STATUS_CLOSED,
                                 before=self._wait_2msl)
        '''

    def get_ori_socket(self) -> socket.socket:
        return self._sock

    def _cli_send_syn1(self) -> None:
        self._seq += 1
        self._logger.debug("_cli_send_syn1, seq: {}".format(self._seq))
        bs = protocol.serialize(protocol.package(flag=protocol.FLAG_SYN, seq=1))
        self._sock.sendto(bs, self._peer_addr)

    def _srv_recv_syn1_and_send_syn2(self, pkg: protocol.package) -> None:
        if self._fsm.is_state(STATUS_CLOSED, self):
            self._logger.debug("_srv_recv_syn1_and_send_syn2, seq: {}".format(pkg.seq))
            self._seq += 1
        bs = protocol.serialize(
            protocol.package(flag=protocol.FLAG_SYN | protocol.FLAG_ACK, seq=self._seq, ack=pkg.seq + 1))
        self._sock.sendto(bs, self._peer_addr)

    def _cli_recv_syn2_and_send_syn3(self, pkg: protocol.package) -> None:
        if self._fsm.is_state(STATUS_SYN_SENT, self):
            self._logger.debug("_cli_recv_syn2_and_send_syn3, seq: {}, ack: {}".format(pkg.seq, pkg.ack))
            if pkg.ack != self._seq + 1:
                raise Exception(
                    "_cli_recv_syn2_and_send_syn3 ack err, want ack: {}, pkg ack: {}".format(self._seq + 1, pkg.ack))
            self._seq += 1
            self._cli_wait_syn2_event.set()
        bs = protocol.serialize(protocol.package(flag=protocol.FLAG_ACK, seq=pkg.ack, ack=self._seq))
        self._sock.sendto(bs, self._peer_addr)

    def _srv_recv_syn3(self, pkg: protocol.package,
                       accept_queue: queue.Queue) -> None:
        if self._fsm.is_state(STATUS_SYN_RCVD, self):
            self._logger.debug("_srv_recv_syn3, seq: {}, ack: {}".format(pkg.seq, pkg.ack))
            if pkg.ack != self._seq + 1:
                raise Exception(
                    "_srv_recv_syn3 ack err, want ack: {}, pkg ack:{}".format(self._seq + 1, pkg.ack))
            self._seq += 1
            accept_queue.put(self)

    def recv_pkg(self, bs: bytes, accept_queue: queue.Queue = None):
        pkg = protocol.un_serialize(bs)
        if pkg.eq_flag(protocol.FLAG_SYN):
            self.trigger(EVENT_SRV_RECV_SYN1_AND_SEND_SYN2, pkg)
            return
        if pkg.eq_flag(protocol.FLAG_SYN | protocol.FLAG_ACK):
            self.trigger(EVENT_CLI_RECV_SYN2_AND_SEND_SYN3, pkg)
            return
        if (self._fsm.is_state(STATUS_SYN_RCVD, self) or self._fsm.is_state(STATUS_ESTABLISHED, self)) and pkg.eq_flag(
                protocol.FLAG_ACK):
            self.trigger(EVENT_SRV_RECV_SYN3, pkg, accept_queue)
            return
        self._logger.error("can not find pkg handle")

    def connect(self, address) -> None:
        self._t = type_cli
        self.trigger(EVENT_CLI_SEND_SYN1)
        threading.Thread(target=self._connect_recv_bs, args=()).start()
        self._cli_wait_syn2_event.wait(500)
        if not self._cli_wait_syn2_event.is_set():
            raise Exception("wait sync2 timeout")

    def _connect_recv_bs(self):
        while 1:
            bs, _ = self._sock.recvfrom(BUF_SIZE)
            try:
                self.recv_pkg(bs)
            except BaseException as e:
                self._logger.error("connect sock recv bs err: {0}".format(traceback.format_exc()))

    def getpeername(self):
        return self._peer_addr

    def getsockname(self):
        try:
            return self._sock.getsockname()
        except BaseException as e:
            return ("unknown", "unknown")

    def recv(self, bufsize: int, flags: int = ...) -> bytes:
        pass

    def send(self, data: bytes, flags: int = ...) -> int:
        pass

    def shutdown(self, how: int) -> None:
        self._sock.shutdown(how)

    def close(self) -> None:
        return self._sock.close()


class sock(socket.socket):
    def __init__(self, family: int = ..., type: int = ...) -> None:
        if family != socket.AF_INET or type != socket.SOCK_STREAM:
            raise Exception("only support AF_INET + SOCK_STREAM")
        self._listen_or_connect = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._addr_mapping_socket = {}
        self._accept_queue = queue.Queue(100)
        self._logger = logging.getLogger()

    def bind(self, address) -> None:
        return self._listen_or_connect.bind(address)

    def listen(self, __backlog: int = ...) -> None:
        threading.Thread(target=self._listen_recv_bs, args=()).start()

    def _listen_recv_bs(self):
        while 1:
            bs, peer_addr = self._listen_or_connect.recvfrom(BUF_SIZE)
            if len(bs) == 0:
                raise Exception("EOF")
            inner_sock = self._addr_mapping_socket.get(peer_addr)
            if inner_sock is None:
                inner_sock = innerSock(self._listen_or_connect, peer_addr)
                self._addr_mapping_socket[peer_addr] = inner_sock
            try:
                inner_sock.recv_pkg(bs, self._accept_queue)
            except BaseException as e:
                self._logger.error("inner sock recv bs err: {0}".format(traceback.format_exc()))

    def accept(self):
        s = self._accept_queue.get()
        return s, s.getpeername()

    def connect(self, address) -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._listen_or_connect = innerSock(s, address)
        self._listen_or_connect.connect(address)

    def getpeername(self):
        return self._listen_or_connect.getpeername()

    def getsockname(self):
        return self._listen_or_connect.getsockname()

    def recv(self, bufsize: int, flags: int = ...) -> bytes:
        return self._listen_or_connect.recvfrom(bufsize, flags)

    def send(self, data: bytes, flags: int = ...) -> int:
        return self._listen_or_connect.send(data, flags)

    def shutdown(self, how: int) -> None:
        self._listen_or_connect.shutdown(how)

    def close(self) -> None:
        return self._listen_or_connect.close()
