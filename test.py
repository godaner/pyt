#!/usr/bin/env python3
import socket
import threading
import time
import traceback

import sock

p = 22222


def listen():
    try:

        lis = sock.sock(socket.AF_INET, socket.SOCK_STREAM)
        lis.bind(("127.0.0.1", 22222))
        lis.listen()
        while 1:
            c, a = lis.accept()
            print("accept:")
            print("accept:", c.getsockname())
            print("accept:", c.getpeername())
    except BaseException as e:
        print(traceback.format_exc())
        # c.close()
        # lis.close()


def connect():
    try:
        s = sock.sock(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", 22222))
        print("connect")
        print("connect", s.getsockname())
        print("connect", s.getpeername())
    except BaseException as e:
        print(traceback.format_exc())
        # s.close()


def main():
    threading.Thread(target=listen).start()
    time.sleep(1)
    connect()


if __name__ == "__main__":
    main()
