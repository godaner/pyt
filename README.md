# pyt

### Introduction

```
transparent agent
```

### Usage

##### shadowsocks-local,don't need change
> Download url: https://github.com/shadowsocks/go-shadowsocks2/releases

```
nohup ./go-shadowsocks2 -c 'ss://AEAD_CHACHA20_POLY1305:123qwe@127.0.0.1:1555' -socks :1080 -verbose  >  ssc.log  2>&1  &
```

##### client,change server.host

```
nohup ./cli.py ./cli.yaml  >  cli.log  2>&1  &
```

##### server,don't need change

```
nohup ./srv.py ./srv.yaml  >  srv.log  2>&1  &
```

##### shadowsocks-server,don't need change

```
nohup ./go-shadowsocks2 -s 'ss://AEAD_CHACHA20_POLY1305:123qwe@:3555' -verbose >  sss.log  2>&1  &
```
