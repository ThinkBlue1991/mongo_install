import os
import re
import subprocess
import argparse
import sys
from datetime import datetime

from fabric import Connection
from invoke import Responder

# 日志文件
FILE_NAME = 'ssh-{}.log'.format(datetime.now().strftime('%Y-%m-%d'))

INFO_LEVEL = {'INFO': 'INFO', 'ERROR': 'ERROR'}


def logging(level, msg):
    """
    记录错误信息的函数
    :param level: str,日志级别
    :param msg: str,日志信息
    :return:
    """
    base_dir = os.getcwd()
    full_filename = os.path.join(base_dir, FILE_NAME)

    command = "echo '{0} -- {1} -- {2}'  >> {3} ".format(INFO_LEVEL[level],
                                                         datetime.now().strftime('%Y-%m-%d-%H:%M:%S'), msg,
                                                         full_filename)
    subprocess.check_call(command, shell=True)


def ssh_connect(ip, user='root', password=None):
    """
    使用 ssh 连接服务器
    :param ip: str,目标服务器的ip地址
    :param user: str,一般ssh免密登录使用的是 root 用户
    :param password: str,目标服务器的密码，我们统一放入列表中
    :return:
    """
    if password:
        try:
            host = Connection(ip, user=user, connect_kwargs={'password': password, 'timeout': 30})
            host.run('ls', hide=True, warn=True)
            if host.is_connected:
                return host, True
        except Exception as error:
            host.close()
            return error, False


def parser_ssh_file(hostfile="./hostfile"):
    """
    解析配置文件信息
    :param hostfile: str, 配置文件路径
    :return:
    """
    nodes_info = []
    with open(hostfile, "rb+") as file:
        for line in file:
            info = line.decode().strip().split(',')
            if len(info) < 2 or not re.match(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$", info[0]):
                continue
            info_dict = dict()
            info_dict["ip"] = info[0]
            info_dict["password"] = info[1]
            nodes_info.append(info_dict)

    return nodes_info


def gen_master_ssh_key(master_node):
    """
    生成秘钥
    :param master_node: dict,主服务器的ip+password
    :return:
    """
    host, SUCCESS = ssh_connect(master_node["ip"], password=master_node["password"])
    if not SUCCESS:
        logging("ERROR", "{}-登录失败--FAILED".format(master_node["ip"]))
        return False

    # 启动ssh服务
    host.run("systemctl start sshd", hide=True, warn=True)

    # 执行 Linux命令，判断是否存在 id_rsa.pub文件
    command = 'find /root/.ssh/ -name "id_rsa.pub"'
    result = host.run(command, hide=True, warn=True)
    if len(result.stdout.strip()) == 0:
        id_rsa = Responder(
            pattern=r'/root/.ssh/id_rsa',
            response='/root/.ssh/id_rsa\n'
        )
        passphrase = Responder(
            pattern=r'passphrase',
            response='\r\n'
        )
        yes = Responder(
            pattern=r'(y/n)',
            response='y\n'
        )
        # 执行Linux生成秘钥的命令
        result = host.run("ssh-keygen -t rsa", hide=False, warn=True, in_stream=False,
                          watchers=[id_rsa, passphrase, yes])
        if not result.ok:
            logging("ERROR", "{0}-生成ssh证书失败--FAILED--{1}".format(master_node['ip'], result.stderr))
            host.close()
            return False
    else:
        logging("INFO", "{0}-ssh证书已经存在--SUCCESS".format(master_node['ip']))

    host.close()
    return True


def ssh_to_other(nodes_info):
    """
    把生成的证书分发给下面的免密的服务器
    :param nodes_info: list,节点列表
    :return:
    """
    logging("INFO", "开始证书文件分发...")

    for master in nodes_info:
        host, SUCCESS = ssh_connect(master["ip"], password=master["password"])
        if not SUCCESS:
            logging("ERROR", "{}-主机登录失败--FAILED".format(master['ip']))
            return False

        for node in nodes_info:
            password = Responder(
                pattern=r'password',
                response=node["password"] + '\r\n'
            )
            yes = Responder(
                pattern=r'(yes/no)',
                response='yes\r\n'
            )

            # 清除 known_hosts文件
            clean_command = "ssh-keygen -f '/root/.ssh/known_hosts' -R {}".format(node['ip'])
            host.run(clean_command, hide=True, warn=True, timeout=30)

            # 分发证书的 Linux命令
            scp_crt_command = "ssh-copy-id -i /root/.ssh/id_rsa.pub root@{}".format(node["ip"])
            result = host.run(scp_crt_command, pty=True, watchers=[password, yes], hide=True, warn=True, timeout=60)

            if result.ok:
                logging("INFO", "{}证书分发{}--SUCCESS".format(master["ip"], node["ip"]))

            else:
                logging("ERROR", "{0}--证书分发{1}--FAILED--{2}".format(master["ip"], node["ip"], result.stderr))

    host.close()

    return True


def check_ssh_login(nodes_info):
    """
    测试免密登录是否实现的函数
    :param nodes_info: list,节点服务器
    :return:
    """
    for master in nodes_info:

        host, SUCCESS = ssh_connect(master["ip"], password=master["password"])
        if not SUCCESS:
            logging("ERROR", "{0}登录失败--FAILED".format(master["ip"]))
            host.close()
            return False

        # 遍历节点服务器列表，对每一个ip进行测试
        for node in nodes_info:
            ssh_command = 'ssh {} echo "ok" '.format(node["ip"])
            try:
                result = host.run(ssh_command, pty=True, hide=True, warn=True, timeout=5)
                if result.ok:
                    logging("INFO", "{0}登录{1}成功--SUCCESS".format(master["ip"], node["ip"]))
                    continue
                else:
                    logging("INFO", "{0}登录{1}失败--FAILED--{2}".format(master["ip"], node["ip"], result.stderr))
                    return False
            except Exception as error:
                logging("INFO", "{0}登录{1}失败--FAILED--{2}".format(master["ip"], node["ip"], error))
    host.close()
    return True


def ssh_server(hostfile):
    """
    ssh server 入口
    :param hostfile: str,配置文件路径
    :return:
    """
    nodes_info = parser_ssh_file(hostfile=hostfile)

    logging("INFO", "共有{}个节点参与此次配置".format(len(nodes_info)))

    for node in nodes_info:
        gen_master_ssh_key(master_node=node)

    SUCCESS = ssh_to_other(nodes_info=nodes_info)

    if not SUCCESS:
        logging("ERROR", "证书分发失败--FAILED")

    return check_ssh_login(nodes_info=nodes_info)


if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(prog="parser", usage="%(prog)s [options]",
                                         description="parser ssh configure file",
                                         epilog="epilog")
        parser.add_argument("-f", "--file", action="store", dest="file_path", help="hostfile path")
        args = parser.parse_args(sys.argv[1:])
        logging("INFO", "ssh配置文件路径--{}--SUCCESS".format(args.file_path))

        if ssh_server(hostfile=args.file_path):
            msg = "ssh server 配置成功--SUCCESS"
            logging("INFO", msg)
            print(msg)
    except Exception as error:
        msg = "解析输入参数失败--FAILED--{0}".format(error)
        logging("ERROR", msg)
        print(msg)
