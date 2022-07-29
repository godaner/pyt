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
        self.logger = logging.getLogger()
        self.conf = conf
        self.app_conns = []
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
            self.local_port = self.conf["local"]["port"]
        except Exception as e:
            self.logger.info("get local port from config fail: {0}".format(e))
            raise e
        try:
            self.local_host = self.conf["local"]["host"]
        except Exception as e:
            self.logger.info("get local host from config fail: {0}".format(e))
            raise e

    def __str__(self):
        return str(self.conf)

    def start(self):
        listen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen.bind((self.local_host, self.local_port))
        listen.listen()
        try:
            while 1:
                app_conn, addr = listen.accept()
                self.app_conns.append(app_conn)
                threading.Thread(target=self.__handle_app_conn, args=(app_conn,)).start()
        except BaseException as e:
            try:
                listen.shutdown(socket.SHUT_RDWR)
                listen.close()
            except BaseException as ee:
                ...
            self.__when_listen_close()
            raise e

    def __when_listen_close(self):
        for app_conn in self.app_conns:
            try:
                app_conn.shutdown(socket.SHUT_RDWR)
                app_conn.close()
            except BaseException as e:
                ...
        self.app_conns = []
        for trans_conn in self.trans_conns:
            try:
                trans_conn.shutdown(socket.SHUT_RDWR)
                trans_conn.close()
            except BaseException as e:
                ...
        self.trans_conns = []

    def __handle_app_conn(self, app_conn: socket.socket):
        app_conn_addr = app_conn.getpeername()
        trans_conn = socket.socket()
        try:
            trans_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            trans_conn.connect((self.server_host, self.server_port))
            trans_conn_addr = trans_conn.getsockname()
            self.trans_conns.append(trans_conn)
            self.logger.info(
                "accept {}:{} <-> {}:{}".format(app_conn_addr[0], app_conn_addr[1], self.local_host, self.local_port))
            self.logger.info("relay {}:{} <-> {}:{}".format(trans_conn_addr[0], trans_conn_addr[1], self.server_host,
                                                            self.server_port))
            threading.Thread(target=self.__handle_trans_conn, args=(app_conn, trans_conn)).start()
            while 1:
                bs = app_conn.recv(1024)
                if len(bs) == 0:
                    raise Exception("EOF")
                trans_conn.send(bs)
        except BaseException as e:
            self.logger.error(
                "closing accept {}:{} <-> {}:{}, {}".format(app_conn_addr[0], app_conn_addr[1], self.local_host,
                                                            self.local_port, e))
            try:
                self.logger.error(
                    "closing relay {}:{} <-> {}:{}, {}".format(trans_conn_addr[0], trans_conn_addr[1], self.server_host,
                                                               self.server_port, e))
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

    def __handle_trans_conn(self, app_conn: socket.socket, trans_conn: socket.socket):
        try:
            while 1:
                bs = trans_conn.recv(1024)
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
        except KeyboardInterrupt as e:
            raise e
        except BaseException as e:
            logger.info("cli err: {0}".format(traceback.format_exc()))
            logger.info("cli will start in 5s...")
            time.sleep(5)
