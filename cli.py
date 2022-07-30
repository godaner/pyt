#!/usr/bin/env python3
import logging
import socket
import sys
import threading
import time
import traceback

import yaml


class Cli:
    def __init__(self, conf):
        self._logger = logging.getLogger()
        self._conf = conf
        self._app_conns = []
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
            self._local_port = self._conf["local"]["port"]
        except Exception as e:
            raise SystemExit(e)
        try:
            self._local_host = self._conf["local"]["host"]
        except Exception as e:
            raise SystemExit(e)

    def __str__(self):
        return str(self._conf)

    def start(self):
        self._logger.info("start client")
        listen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen.bind((self._local_host, self._local_port))
        listen.listen()
        self._logger.info(
            "listen app conn {}:{}".format(self._local_host, self._local_port))
        try:
            while 1:
                app_conn, addr = listen.accept()
                self._app_conns.append(app_conn)
                threading.Thread(target=self._handle_app_conn, args=(app_conn,)).start()
        except BaseException as e:
            self._logger.error(
                "closing listen app conn {}:{}, {}".format(self._local_host, self._local_port, e))
            try:
                listen.shutdown(socket.SHUT_RDWR)
                listen.close()
            except BaseException as ee:
                ...
            self._when_listen_close()
            raise e

    def _when_listen_close(self):
        for app_conn in self._app_conns:
            try:
                app_conn.shutdown(socket.SHUT_RDWR)
                app_conn.close()
            except BaseException as e:
                ...
        self._app_conns = []
        for trans_conn in self._trans_conns:
            try:
                trans_conn.shutdown(socket.SHUT_RDWR)
                trans_conn.close()
            except BaseException as e:
                ...
        self._trans_conns = []

    def _handle_app_conn(self, app_conn: socket.socket):
        app_conn_addr = app_conn.getpeername()
        trans_conn = socket.socket()
        try:
            trans_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            trans_conn.connect((self._server_host, self._server_port))
            trans_conn_addr = trans_conn.getsockname()
            self._trans_conns.append(trans_conn)
            self._logger.info(
                "accept {}:{} <-> {}:{}".format(app_conn_addr[0], app_conn_addr[1], self._local_host, self._local_port))
            self._logger.info("relay {}:{} <-> {}:{}".format(trans_conn_addr[0], trans_conn_addr[1], self._server_host,
                                                             self._server_port))
            threading.Thread(target=self._handle_trans_conn, args=(app_conn, trans_conn)).start()
            while 1:
                bs = app_conn.recv(40960)
                if len(bs) == 0:
                    raise Exception("EOF")
                trans_conn.send(bs)
        except BaseException as e:
            self._logger.error(
                "closing accept {}:{} <-> {}:{}, {}".format(app_conn_addr[0], app_conn_addr[1], self._local_host,
                                                            self._local_port, e))
            try:
                self._logger.error(
                    "closing relay {}:{} <-> {}:{}, {}".format(trans_conn_addr[0], trans_conn_addr[1],
                                                               self._server_host,
                                                               self._server_port, e))
            except BaseException as ee:
                ...
            try:
                app_conn.shutdown(socket.SHUT_RDWR)
                app_conn.close()
            except BaseException as e:
                ...
            try:
                trans_conn.shutdown(socket.SHUT_RDWR)
                trans_conn.close()
            except BaseException as e:
                ...

    def _handle_trans_conn(self, app_conn: socket.socket, trans_conn: socket.socket):
        try:
            while 1:
                bs = trans_conn.recv(40960)
                if len(bs) == 0:
                    raise Exception("EOF")
                app_conn.send(bs)
        except BaseException as e:
            try:
                app_conn.shutdown(socket.SHUT_RDWR)
                app_conn.close()
            except BaseException as e:
                ...
            try:
                trans_conn.shutdown(socket.SHUT_RDWR)
                trans_conn.close()
            except BaseException as e:
                ...


if __name__ == "__main__":
    if len(sys.argv) != 2:
        config_file = "./cli.yaml"
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
    cli = Cli(conf)
    logger.info("cli info: {0}".format(cli))
    while 1:
        try:
            cli.start()
        except (SystemExit, KeyboardInterrupt) as e:
            raise e
        except BaseException as e:
            logger.info("cli err: {0}".format(traceback.format_exc()))
            logger.info("cli will start in 5s...")
            time.sleep(5)
