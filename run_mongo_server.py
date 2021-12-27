import os
import json
import subprocess
from datetime import datetime

# 日志文件
FILE_NAME = 'mongodb-{}.log'.format(datetime.now().strftime('%Y-%m-%d'))

INFO_LEVEL = {'INFO': 'INFO', 'DEBUG': 'DEBUG', 'ERROR': 'ERROR'}


def logging(level, msg):
    """
    记录错误信息的函数
    :param level: str,日志的级别
    :param msg: str,日志信息
    :return:
    """
    base_dir = os.getcwd()
    full_filename = os.path.join(base_dir, FILE_NAME)

    command = "echo {0} -- {1} -- {2}  >> {3} ".format(INFO_LEVEL[level],
                                                       datetime.now().strftime('%Y-%m-%d-%H:%M:%S'), msg,
                                                       full_filename)
    subprocess.check_call(command, shell=True)


def gen_config(json_config, prefix, PWD='./'):
    """
    生成配置文件
    :param json_config: dict,配置的json格式
    :param prefix: str,配置文件前缀
    :param PWD: str,配置文件所在的路径
    :return:
    """
    for item in json_config[prefix]:
        dest = os.path.join(PWD, '{0}_{1}_{2}.config'.format(prefix, item["IP"], item["role"]))
        src = os.path.join(PWD, '{0}.cfg.sample'.format(prefix))

        with open(src, 'r') as sample_file:
            with open(dest, 'w+') as config_file:
                for line in sample_file:
                    if line.find('systemLog_path') != -1:
                        config_file.write(line.replace('systemLog_path', item['systemLog_path']))
                    elif line.find('storage_dbPath') != -1:
                        config_file.write(line.replace('storage_dbPath', item['storage_dbPath']))
                    elif line.find('processManagement_pidFilePath') != -1:
                        config_file.write(
                            line.replace('processManagement_pidFilePath', item['processManagement_pidFilePath']))
                    elif line.find('net_port') != -1:
                        config_file.write(line.replace('net_port', str(item['net_port'])))
                    elif line.find('replication_replSetName') != -1:
                        config_file.write(line.replace('replication_replSetName', item['replication_replSetName']))
                    elif line.find('sharding_configDB') != -1:
                        config_file.write(line.replace('sharding_configDB', item['sharding_configDB']))
                    elif line.find('wiredTiger_engineConfig_cacheSizeGB') != -1:
                        config_file.write(line.replace('wiredTiger_engineConfig_cacheSizeGB',
                                                       str(item['wiredTiger_engineConfig_cacheSizeGB'])))
                    else:
                        config_file.write(line)


def release_mongod_tasks(json_config, PWD='./'):
    """
    启动mongod进程
    :param json_config: dict,配置信息
    :param PWD:str,配置文件所在的路径
    :return:
    """
    try:
        # 启动configsvr
        print("******************************开始启动config进程******************************")
        for task in json_config["configsvr"]:
            log_dir = os.path.dirname(task["systemLog_path"])
            pid_dir = os.path.dirname(task["processManagement_pidFilePath"])
            db_dir = task["storage_dbPath"]
            mkdir_command = 'ssh {0} "mkdir -p {1};mkdir -p {2};mkdir -p {3};chown mongod:mongod {3}"'.format(
                task["IP"], log_dir, pid_dir, db_dir, db_dir)

            logging("DEBUG", "release_mongod_tasks--创建config server 数据目录--{}".format(mkdir_command))
            subprocess.check_call(mkdir_command, shell=True)

            up_command = 'ssh {0} "mongod --config {1}"'.format(task["IP"],
                                                                os.path.join(PWD, 'configsvr_{0}_{1}.config'.format(
                                                                    task["IP"], task["role"])))

            logging("DEBUG", "release_mongod_tasks--启动config server进程--{}".format(up_command))
            subprocess.check_call(up_command, shell=True)
        print("******************************config进程启动成功******************************")

        # 启动shardsvr
        print("******************************开始启动shard进程******************************")
        for task in json_config["shardsvr"]:
            log_dir = os.path.dirname(task["systemLog_path"])
            pid_dir = os.path.dirname(task["processManagement_pidFilePath"])
            db_dir = task["storage_dbPath"]
            mkdir_command = 'ssh {0} "mkdir -p {1};mkdir -p {2};mkdir -p {3};chown mongod:mongod {3}"'.format(
                task["IP"], log_dir, pid_dir,
                db_dir, db_dir)

            logging("DEBUG", "release_mongod_tasks--创建shard数据目录--{}".format(mkdir_command))
            subprocess.check_call(mkdir_command, shell=True)

            up_command = 'ssh {0} "systemctl stop mongod; mongod --config {1}"'.format(task["IP"],
                                   os.path.join(PWD,'shardsvr_{0}_{1}.config'.format(task["IP"], task["role"])))

            logging("DEBUG", "release_mongod_tasks--启动shard进程--{}".format(up_command))
            subprocess.check_call(up_command, shell=True)
        print("******************************shard进程启动成功******************************")

        return True
    except Exception as error:
        logging("ERROR", "release_mongod_tasks--进程启动失败--FAILED:{}".format(error))
        raise


def release_mongos_tasks(json_config, PWD='./'):
    """
    启动mongos进程
    :param json_config: dict,配置信息
    :param PWD:str,配置文件所在的路径
    :return:
    """
    try:
        # 启动mongos
        print("******************************开始启动mongos进程******************************")
        for task in json_config["mongos"]:
            log_dir = os.path.dirname(task["systemLog_path"])
            pid_dir = os.path.dirname(task["processManagement_pidFilePath"])
            mkdir_command = 'ssh {0} "mkdir -p {1};mkdir -p {2}"'.format(task["IP"], log_dir, pid_dir)

            logging("DEBUG", "release_mongos_tasks--创建mongos数据目录--{}".format(mkdir_command))
            subprocess.check_call(mkdir_command, shell=True)

            up_command = 'ssh {0} "mongos --config {1}"'.format(task["IP"],
                                                                os.path.join(PWD, 'mongos_{0}_{1}.config'.format(
                                                                    task["IP"], task["role"])))

            logging("DEBUG", "release_mongos_tasks--启动mongos进程--{}".format(up_command))
            subprocess.check_call(up_command, shell=True)
        print("******************************mongos进程启动成功******************************")
        return True
    except Exception as error:
        logging("ERROR", "release_mongos_tasks--mongos进程启动失败--FAILED:{}".format(error))
        raise


def init_configsrv(json_config):
    """
    初始化config server进程
    :param json_config: dict,配置信息
    :return:
    """
    try:
        msg = 'rs.initiate({_id:"replconfig",configsvr:true,members:'
        count = 0
        members = '[ '
        for configsvr in json_config["configsvr"]:
            members = members + '{_id:' + str(count) + ', host: ' + '"{0}:{1}"'.format(configsvr["IP"],
                                                                                       configsvr["net_port"]) + '},'
            count += 1
        msg += members[:-1] + ']})'

        return msg
    except Exception as error:
        print(error)
        raise


def init_shards(json_config):
    """
    初始化shard server进程
    :param json_config: dict,配置信息
    :return:
    """
    try:
        msg_list = list()
        for shard in json_config["shardsvr"]:
            msg = 'rs.initiate({{_id:"{0}",members:[{{_id:0,host:"{1}:{2}"}}]}})'.format(
                shard["replication_replSetName"],
                shard["IP"], shard["net_port"])
            msg_list.append(msg)

        return msg_list
    except Exception as error:
        print(error)
        raise


def init_mongos(json_config):
    """
    汇总shard信息，组合addshard的信息
    :param json_config: dict,配置信息
    :return:
    """
    try:
        msg_list = list()
        for shard in json_config["shardsvr"]:
            msg = 'sh.addShard("{0}/{1}:{2}")'.format(shard["replication_replSetName"], shard["IP"], shard["net_port"])

            msg_list.append(msg)

        return msg_list
    except Exception as error:
        print(error)
        raise


def init_mongod(json_config):
    """
    初始化mongo进程，包括config server,shard server,mongos server
    :param json_config: dict,配置信息
    :return:
    """
    try:
        print("******************************开始初始化config节点******************************")
        confidsvr_command = init_configsrv(json_config=json_config)
        if confidsvr_command is not None:
            host = json_config["configsvr"][0]["IP"]
            port = json_config["configsvr"][0]["net_port"]

            config_shell = "mongo --host {0} --port {1} --eval '{2};rs.isMaster()'".format(host, port,
                                                                                           confidsvr_command)

            logging("DEBUG", "init_mongod--初始化config server--{}".format(config_shell))

            subprocess.check_call(config_shell, shell=True)
        print("******************************config节点初始化成功******************************")

        print("******************************开始初始化shard节点******************************")
        shards_command = init_shards(json_config=json_config)
        if shards_command is not None:
            i = 0
            for shard in json_config["shardsvr"]:
                host = shard["IP"]
                port = shard["net_port"]
                shard_shell = "mongo --host {0} --port {1} --eval '{2}'".format(host, port, shards_command[i])
                i += 1

                logging("DEBUG", "init_mongod--初始化shard--{}".format(shard_shell))

                subprocess.check_call(shard_shell, shell=True)
        print("******************************shard节点初始化成功******************************")
        return True
    except Exception as error:
        logging("ERROR", "init_mongod--初始化失败--{}".format(error))
        raise


def add_shards(json_config):
    """
    向mongos进程中添加shard信息
    :param json_config: dict,配置信息
    :return:
    """
    try:
        print("******************************开始向mongos中添加shard******************************")
        mongos_command = init_mongos(json_config=json_config)
        if mongos_command is not None:
            host = json_config["mongos"][0]["IP"]
            port = json_config["mongos"][0]["net_port"]

            for mongos in mongos_command:
                shard_shell = "mongo --host {0} --port {1} --eval '{2}'".format(host, port, mongos)
                logging("DEBUG", "add_shards--mongos增加shard--{}".format(shard_shell))
                subprocess.check_call(shard_shell, shell=True)
        print("******************************向mongos中添加shard成功，共添加{0}个shard******************************".format(
            len(mongos_command)))
        return True
    except Exception as error:
        logging("ERROR", "add_shards--mongos增加shard失败--{}".format(error))
        raise


if __name__ == '__main__':
    try:
        config = './config.json'
        PWD = os.getcwd()

        with open(config, 'r') as jsonfile:
            json_config = json.load(jsonfile)

        print("******************************开始生成配置文件******************************")
        gen_config(json_config=json_config, PWD=PWD, prefix='configsvr')
        gen_config(json_config=json_config, PWD=PWD, prefix='shardsvr')
        gen_config(json_config=json_config, PWD=PWD, prefix='mongos')
        print("******************************配置文件生成成功******************************")

        # 启动config和shard进程
        print("******************************开始启动和初始化服务******************************")
        if release_mongod_tasks(json_config=json_config, PWD=PWD) and init_mongod(json_config=json_config):
            # 启动mongos进程
            if release_mongos_tasks(json_config=json_config, PWD=PWD) and add_shards(json_config=json_config):
                print("******************************SUCCESS******************************")
    except Exception as error:
        logging("ERROR", "mongodb 构建失败,进行回滚: {0}".format(error))
        print("******************************FAILED******************************")