#!/usr/bin/env python
#coding=utf-8

# orm, map to file_day_counter table

import sys
import threading
import redis
import random
import json

# set default coding
reload(sys)
sys.setdefaultencoding('UTF-8')

class MyConnectionPool(object):
    __instance = None
    __connection_pool = None
    # used to synchronize code
    __lock = threading.Lock()

    def __init__(self):
        "disable the __init__ method"

    @staticmethod
    def getInstance(chost, cport, cdb = 0, cpassword = None):
        if not MyConnectionPool.__instance:
            MyConnectionPool.__lock.acquire()
            if not MyConnectionPool.__instance:
                MyConnectionPool.__instance = object.__new__(MyConnectionPool)
                object.__init__(MyConnectionPool.__instance)
                MyConnectionPool.__connection_pool = redis.ConnectionPool(max_connections = 20, host=chost, port=cport, db=cdb, password=cpassword)
            MyConnectionPool.__lock.release()
        return MyConnectionPool.__connection_pool

class RedisCacheClient:
    def __init__(self, host, port, db = 0, password = None):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.connection = None
        pool = MyConnectionPool.getInstance(self.host, self.port, self.db, self.password)
        self.connection_pool = pool
        self.debug = False
        self.rc = redis.Redis(connection_pool=self.connection_pool)

    def __del__(self):
        try:
            self.reset()
        except:
            pass
    
    def reset(self):
        if self.connection:
            self.connection_pool.release(self.connection)
            self.connection = None
    
    def create(self):
        if self.connection is None:
            self.connection = self.connection_pool.get_connection('python_job', None)
        
    def mySet(self, name, value, days = 730):
        expire_time = 3600 * 24 * days
        try:
            self.create()
            self.rc.setex(name, str(value), expire_time)
            self.reset()
        except Exception, e:
            if self.debug:
                print e
            return False
        return True
    
    def myGet(self, name):
        try:
            self.create()
            ret = self.rc.get(name)
            self.reset()
            return ret
        except Exception, e:
            if self.debug:
                print e
            return None
        return None

    def myLpush(self, name, *values):
        try:
            self.rc.lpush(name, *values);
        except Exception, e:
            if self.debug:
                print e
            return False
        return True
    def myRpop(self, name):
        try:
            r = self.rc.rpop(name)
        except Exception, e:
            if self.debug:
                print e
            return None
        return r
    
    def MyLlen(self, name):
        try:
            r = self.rc.llen(name)
        except Exception, e:
            if self.debug:
                print e
        return r
        
    def myDel(self, name):
        try:
            self.create()
            self.rc.delete(name)
            self.reset()
        except Exception, e:
            if self.debug:
                print e
            return False
        return True

    def myExists(self, name):
        exist = False
        try:
            self.create()
            exist = self.rc.exists(name)
            self.reset()
        except Exception, e:
            if self.debug:
                print e
            return False
        return exist

    def myHset(self, name, cache_map, days = 730):
        expire_time = 3600 * 24 * days
        try:
            self.create()
            self.rc.hmset(name, cache_map)
            self.rc.expire(name, expire_time)
            self.reset()
        except Exception, e:
            if self.debug:
                print e
            return False
        return True

    def myHget(self, name, field):
        try:
            self.create()
            ret = self.rc.hget(name, field)
            self.reset()
            return ret
        except Exception, e:
            if self.debug:
                print e
            return None
        return None

if __name__ == '__main__':
    c = RedisCacheClient('9d3876543e4090.m.cnsza.kvstore.aliyuncs.com', 6379, 0, "9xjdl8677090e4090:charles518518")
    c.debug = True
    v = c.myGet('user_1')
    print v
    
    decodejson = json.loads(v)
    print decodejson
