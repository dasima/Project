#!/usr/bin/env python
#coding=utf-8


import sys
import os

# set default coding
reload(sys)
sys.setdefaultencoding('UTF-8')

# 运营数据库
defaultDB = {
    "name" : 'default',
    "host" : 'test01.mysql.rds.aliyuncs.com',
    "port" : 3306,
    "user" : 'test3',
    "password" : 'testy',
    "charset" : 'utf8',
    "db" : 'db_yunying_test'
}

# 测试数据库
testDB = {
    "name" : 'default',
    "host" : 'test01.mysql.rds.aliyuncs.com',
    "port" : 3306,
    "user" : 'test3',
    "password" : 'testy',
    "charset" : 'utf8',
    "db" : 'd_charles_svr'
}


# 正式数据库
onlineDB = {
    "name" : 'default',
    "host" : 'online.mysql.rds.aliyuncs.com',
    "port" : 3306,
    "user" : 'charles',
    "password" : 'svr123',
    "charset" : 'utf8',
    "db" : 'd_charles_svr_online'
}
