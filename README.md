### 介绍
本脚本主要完成mongodb sharding cluster的配置和启动过程。


### 前提
- 各个节点都已经安装完成mongodb
- 各个节点有共享的文件系统，所有的节点全部挂载在相同的挂载点，以moosefs为例
```shell script
mkdir -p /mnt/mfs
mfsmount -H mfsmaster -P 9421 /mnt/mfs
```

共享文件系统可以自由选择，只要保证各个节点能够访问同一个目录即可。

### 脚本介绍
####  `run_ssh_server.py`
配置各个节点的无密钥登录，便于对mongodb集群的配置

目前，只支持对`root`用户的无密钥登录配置过程

其中，`hostfile`为需要配置的节点和密码集合，格式如下
```text
IP1,PASSWORD1
IP2,PASSWORD2
IP3,PASSWORD3
```

#### `run_mongo_server.py`
主要功能是根据`config.json`来生成对应的配置文件，然后根据各个节点的角色配置来启动对应的mongo服务进程。

-  `config.json`

为json格式，主要分为三部分，分别为configsvr,shard,mongos。
针对不同服务的配置不同，填写对应的节点和参数配置。

样本配置文件中，一共在三个节点上配置了3个config server，3个mongos server和6个shard server

- `configsvr.cfg.sample`

configsvr服务的配置样本

- `shardsvr.cfg.sample`

shardsvr服务的配置样本

- `mongos.cfg.sample`

mongos服务的配置样本


### 日志

`run_ssh_server`服务会生成ssh-`date` .log的日志文件

`run_mongo_server`服务会生成mongodb-`date` .log的日志文件


### 开始
```shell script

# 安装依赖
pip3 install -r requirement.txt

python3 run_ssh_server.py -f hostfile

# 上一步执行成功之后，才执行下一步

python3 run_mongo_server.py -f config.json create
python3 run_mongo_server.py -f config.json start
```

### 关闭服务
```shell script
python3 run_mongo_server.py -f config.json stop
```
### 其他

此次脚本只要针对mongodb常用的配置项来完成配置和启动任务

monogodb配置项很多，可以根据不同的需求来调整脚本配置。

