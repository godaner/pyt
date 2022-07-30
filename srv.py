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
        self._conf = conf
        self._logger = logging.getLogger()
        self._remote_conns = []
        self._trans_conns = []
        try:
            self._server_host = self._conf["server"]["host"]
        except Exception as e:
            raise SystemExit(e)
        try:
            self._server_port = self._conf["server"]["port"]
        except Exception as e:
            raise SystemExit(e)
        try:
            self._local_host = self._conf["local"]["host"]
        except Exception as e:
            raise SystemExit(e)
        try:
            self._local_port = self._conf["local"]["port"]
        except Exception as e:
            raise SystemExit(e)

    def __str__(self):
        return str(self._conf)

    def start(self):
        self._logger.info("start server")
        listen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen.bind((self._local_host, self._local_port))
        listen.listen()
        self._logger.info(
            "listen trans conn {}:{}".format(self._local_host, self._local_port))
        while 1:
            try:
                trans_conn, addr = listen.accept()
                threading.Thread(target=self._handle_trans_conn, args=(trans_conn,)).start()
            except BaseException as e:
                self._logger.error(
                    "closing listen trans conn {}:{}, {}".format(self._local_host, self._local_port, e))
                try:
                    listen.shutdown(socket.SHUT_RDWR)
                    listen.close()
                except BaseException as ee:
                    ...
                self._when_listen_close()
                raise e

    def _handle_trans_conn(self, trans_conn: socket.socket):
        trans_conn_addr = trans_conn.getpeername()
        remote_conn = socket.socket()
        try:
            remote_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            remote_conn.connect((self._server_host, self._server_port))
            remote_conn_addr = remote_conn.getsockname()
            self._remote_conns.append(remote_conn)
            self._logger.info("accept {}:{} <-> {}:{}".format(trans_conn_addr[0], trans_conn_addr[1], self._local_host,
                                                              self._local_port))
            self._logger.info(
                "relay {}:{} <-> {}:{}".format(remote_conn_addr[0], remote_conn_addr[1], self._server_host,
                                               self._server_port))
            threading.Thread(target=self._handle_remote_conn, args=(trans_conn, remote_conn)).start()
            while 1:
                bs = trans_conn.recv(1024)
                if len(bs) == 0:
                    raise Exception("EOF")
                remote_conn.send(bs)
        except BaseException as e:
            self._logger.error(
                "closing accept {}:{} <-> {}:{}, {}".format(trans_conn_addr[0], trans_conn_addr[1], self._local_host,
                                                            self._local_port, e))
            try:
                self._logger.error(
                    "closing relay {}:{} <-> {}:{}, {}".format(remote_conn_addr[0], remote_conn_addr[1],
                                                               self._server_host,
                                                               self._server_port, e))
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

    def _handle_remote_conn(self, trans_conn: socket.socket, remote_conn: socket.socket):
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

    def _when_listen_close(self):
        for remote_conn in self._remote_conns:
            try:
                remote_conn.shutdown(socket.SHUT_RDWR)
                remote_conn.close()
            except BaseException as e:
                ...
        self._remote_conns = []
        for trans_conn in self._trans_conns:
            try:
                trans_conn.shutdown(socket.SHUT_RDWR)
                trans_conn.close()
            except BaseException as e:
                ...
        self._trans_conns = []


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
    logger.info("server info: {0}".format(srv))
    while 1:
        try:
            srv.start()
        except (SystemExit, KeyboardInterrupt) as e:
            raise e
        except BaseException as e:
            logger.info("server err:{0} {1}".format(e, traceback.format_exc()))
            logger.info("server will start in 5s...")
            time.sleep(5)
