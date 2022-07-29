#!/usr/bin/env python3
import logging
import socket
import sys
import threading
import time
import traceback

import yaml


class Srv:
    def __init__(self, conf):
        self.conf = conf
        self.logger = logging.getLogger()
        self.remote_conns = []
        self.trans_conns = []
        try:
            self.server_host = self.conf["server"]["host"]
        except Exception as e:
            self.logger.info("get server host from config fail: {0}".format(e))
            raise e
        try:
            self.server_port = self.conf["server"]["port"]
        except Exception as e:
            self.logger.info("get server port from config fail: {0}".format(e))
            raise e
        try:
            self.local_host = self.conf["local"]["host"]
        except Exception as e:
            self.logger.info("get local host from config fail: {0}".format(e))
            raise e
        try:
            self.local_port = self.conf["local"]["port"]
        except Exception as e:
            self.logger.info("get local port from config fail: {0}".format(e))
            raise e

    def __str__(self):
        return str(self.conf)

    def start(self):
        self.logger.info("start server!")
        listen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen.bind((self.local_host, self.local_port))
        listen.listen()
        while 1:
            try:
                trans_conn, addr = listen.accept()
                threading.Thread(target=self.__handle_trans_conn, args=(trans_conn,)).start()
            except BaseException as e:
                self.logger.error("listen accept trans_conn err: {0}".format(e))
                try:
                    listen.shutdown(socket.SHUT_RDWR)
                    listen.close()
                except BaseException as ee:
                    ...
                self.__when_listen_close()
                raise e

    def __handle_trans_conn(self, trans_conn: socket.socket):
        trans_conn_addr = trans_conn.getpeername()
        remote_conn = socket.socket()
        try:
            remote_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            remote_conn.connect((self.server_host, self.server_port))
            remote_conn_addr = remote_conn.getsockname()
            self.remote_conns.append(remote_conn)
            self.logger.info("accept {}:{} <-> {}:{}".format(trans_conn_addr[0], trans_conn_addr[1], self.local_host,
                                                             self.local_port))
            self.logger.info("relay {}:{} <-> {}:{}".format(remote_conn_addr[0], remote_conn_addr[1], self.server_host,
                                                            self.server_port))
            threading.Thread(target=self.__handle_remote_conn, args=(trans_conn, remote_conn)).start()
            while 1:
                bs = trans_conn.recv(1024)
                if len(bs) == 0:
                    raise Exception("EOF")
                remote_conn.send(bs)
        except BaseException as e:
            self.logger.error(
                "closing accept {}:{} <-> {}:{}, {}".format(trans_conn_addr[0], trans_conn_addr[1], self.local_host,
                                                            self.local_port, e))
            try:
                self.logger.error(
                    "closing relay {}:{} <-> {}:{}, {}".format(remote_conn_addr[0], remote_conn_addr[1],
                                                               self.server_host,
                                                               self.server_port, e))
            except BaseException as ee:
                ...
            try:
                trans_conn.shutdown(socket.SHUT_RDWR)
                trans_conn.close()
            except BaseException as ee:
                ...
            try:
                remote_conn.shutdown(socket.SHUT_RDWR)
                remote_conn.close()
            except BaseException as ee:
                ...

    def __handle_remote_conn(self, trans_conn: socket.socket, remote_conn: socket.socket):
        try:
            while 1:
                bs = remote_conn.recv(1024)
                if len(bs) == 0:
                    raise Exception("EOF")
                trans_conn.send(bs)
        except BaseException as e:
            try:
                trans_conn.shutdown(socket.SHUT_RDWR)
                trans_conn.close()
            except BaseException as e:
                ...
            try:
                remote_conn.shutdown(socket.SHUT_RDWR)
                remote_conn.close()
            except BaseException as e:
                ...

    def __when_listen_close(self):
        for remote_conn in self.remote_conns:
            try:
                remote_conn.shutdown(socket.SHUT_RDWR)
                remote_conn.close()
            except BaseException as e:
                ...
        self.remote_conns = []
        for trans_conn in self.trans_conns:
            try:
                trans_conn.shutdown(socket.SHUT_RDWR)
                trans_conn.close()
            except BaseException as e:
                ...
        self.trans_conns = []


if __name__ == "__main__":
    if len(sys.argv) != 2:
        config_file = "./srv.yaml"
    else:
        config_file = sys.argv[1]
    with open(config_file, 'r') as f:
        conf = yaml.safe_load(f)
    lev = logging.INFO
    try:
        debug = conf['debug']
    except BaseException as e:
        debug = False
    if debug:
        lev = logging.DEBUG
    logging.basicConfig(level=lev,
                        format='%(asctime)s %(levelname)s %(pathname)s:%(lineno)d %(thread)s %(message)s')
    logger = logging.getLogger()
    srv = Srv(conf)
    logger.info("server info: {0}!".format(srv))
    while 1:
        try:
            srv.start()
        except KeyboardInterrupt as e:
            raise e
        except BaseException as e:
            logger.info("server err:{0} {1}!".format(e, traceback.format_exc()))
            logger.info("server will start in 5s...")
            time.sleep(5)
