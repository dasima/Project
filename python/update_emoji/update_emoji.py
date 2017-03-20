#!/usr/bin/env python
#coding=utf-8

import sys
import os
os.environ['PYTHON_EGG_CACHE'] = '/tmp/aaa'
import warnings
sys.path.append('.')
import DefaultDbConfig
import json
import Model
import datetime
import time
import urllib
import log
import logging

# set default coding
reload(sys)
sys.setdefaultencoding('UTF-8')
warnings.filterwarnings("ignore")


def build_message(uid):
    """ 构建消息内容. """

    url = {}
    url['from_uid'] = '1'
    url['to_uid'] = uid
    url['push_type'] = 'update_resource'
    msg = {}
    #resource_type = [5]
    #msg['type'] = json.dumps(resource_type)
    msg['type'] = 5
    #msg['type'] = '5'
    url['content'] = json.dumps(msg)
    logging.info(url)
    return url


def push_message(data, env):
    """ 推送消息给im server. """

    PUSH_URL = "http://10.116.xxx.xx1:10080/cl_sendopmsg?"
    #PUSH_URL_ONLINE = "http://10.116.xxx.xxx:10080/cl_sendopmsg?"
    PUSH_URL_ONLINE = "http://10.116.xxx.xxx:10080/cl_sendopmsg?"

    logging.info(env)
    url_code = urllib.urlencode(data)
    if env == 'dev':
        send_url = PUSH_URL
    else:
        send_url = PUSH_URL_ONLINE
    cmd = 'wget "' + send_url + url_code + '" -O update_emoji_result.txt'
    logging.info(cmd)
    os.system(cmd)


if __name__ == "__main__":
    log.init_log("./log/update_emoji", console=True)
    m = Model.Model(DefaultDbConfig.defaultDB)
    user_model = Model.Model(DefaultDbConfig.testDB)
    user_model_online = Model.Model(DefaultDbConfig.onlineDB)
    env = sys.argv[1]
    if env == 'dev':
        m = user_model
    else:
        m = user_model_online
    
    if len(sys.argv) >= 3:
        # 用于测试
        phone_num = sys.argv[2]
        sql2 = ("select Fuid from t_user where Fuser_type = '1' and FBindPhone = " + phone_num + " limit 1;")
    else:
        TimeStr = (datetime.datetime.fromtimestamp(time.time()).
                   strftime('%Y-%m-%d %H:%M'))
        sql2 = "select Fuid from t_user where Fuser_type = '1' limit 11;"
        #sql2 = "select Fuid from t_user where Fuser_type = '1';"
    user_list = m.query(sql2)
    logging.info(sql2)
    if not user_list:
        logging.warn("not found user:")
    else:
        count = 0
        for user in user_list:
            if(count >= 1000):
                time.sleep(1)
                count = 0
                count += 1
            else:
                count += 1
            url = build_message(user['Fuid'])
            push_message(url, env)
            logging.info(user)

    logging.info("------run over!------")

