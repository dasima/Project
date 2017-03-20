#!/usr/bin/env python
#coding=utf-8


import sys
import os
import warnings
import MySQLdb
import MySQLdb.cursors
sys.path.append('.')
import DefaultDbConfig
import json

# set default coding
reload(sys)
sys.setdefaultencoding('UTF-8')
warnings.filterwarnings("ignore")

class Model:
    def __init__(self, dbs):
        self.dbsource = dbs
        self.host = self.dbsource['host']
        self.port = self.dbsource['port']
        self.charset =  self.dbsource['charset']
        self.user = self.dbsource['user']
        self.password = self.dbsource['password']
        self.dbName = self.dbsource['db']
        self.tableName = None
        self.fullTable = None
        self.keys = []
        self.fields = []
        self.debug = False
        self.con = None

    def __del__(self):
        if not self.con is None:
            self.con.close()
            self.con = None
 
    def _readconf(self):
        if self.dbsource['name'] != "default":
            self.host = self.dbsource['host']
            self.port = self.dbsource['port']
            self.charset =  self.dbsource['charset']
            self.user = self.dbsource['user']
            self.password = self.dbsource['password']
            #self.dbName = self.dbsource['db']

    def _createCon(self):
        self._readconf()
        self.con = MySQLdb.Connect(host = self.host, port = self.port, db = self.dbName, user = self.user, passwd = self.password, charset = self.charset)
        self.con.autocommit(True)
        if self.con.open == False:
            self.con = None
            raise None

    def query(self, sql):
        "select data from database by using string fromat sql" 
        fullTable = ''
        if sql.find('__TABLE__') and not self.tableName is None:
            fullTable = "`" + self.dbName + "`.`" + self.tableName + "`"

        sql = sql.replace('__TABLE__', fullTable)
        if self.debug:
            print sql

        try:
            if self.con is None:
                self._createCon()
            cursor = self.con.cursor(cursorclass = MySQLdb.cursors.DictCursor)
        except Exception, e:
            if self.debug:
                print e
            return {}

        try:
            cursor.execute(sql)
            #self.con.commit(sql)
            all_data = cursor.fetchall()
            cursor.close()
            return all_data
        except Exception, e:
            cursor.close()
            if self.debug:
                print e
            return {}

    def save(self, data, replace = True):
        "add new data into database or update existed data in database"
        if not self.tableName is None:
            fullTable = "`" + self.dbName + "`.`" + self.tableName + "`"
        else:
            raise None

        field  = ""
        value  = ""
        update = ""
        is_first = True
        for col in data:
            if len(self.fields) != 0 and col not in self.fields:
                continue
            if is_first:
                is_first = False
                field  += "`" + col + "`"
                value  += "'" + str(data[col]) + "'"
                if col not in self.keys:
                    update += "`" + col + "`=VALUES(`" + col + "`)"
            else:
                is_first = False
                field  += ", `" + col + "`"
                value  += ", '" + str(data[col]) + "'"
                if col not in self.keys:
                    update += ", `" + col + "`=VALUES(`" + col + "`)"
        update = update.strip(',')
        if not replace:
            sql = "INSERT INTO %s (%s) VALUES (%s)" % (fullTable, field, value)
        else : 
            sql = "INSERT INTO %s (%s) VALUES (%s) ON DUPLICATE KEY UPDATE %s" % (fullTable, field, value, update)
        if self.debug:
            print sql

        try:
            if self.con is None:
                self._createCon()
            cursor = self.con.cursor(cursorclass = MySQLdb.cursors.DictCursor)
        except Exception, e:
            if self.debug:
                print e
            return False

        try:
            lines = cursor.execute(sql)
            #self.con.commit(sql)
            cursor.close()
            if lines >= 0:
                return True
            return False
        except Exception, e:
            cursor.close()
            if self.debug:
                print e
            return False

    def saveMult(self, mult_data):
        "add new data into database or update existed data in database with batch operation"
        if not self.tableName is None:
            fullTable = "`" + self.dbName + "`.`" + self.tableName + "`"
        else:
            raise None

        field  = ""
        update = ""
        mult_value  = ""
        big_first = True
        for key, data in mult_data.items():
            if big_first:
                first = True
                for key2, t_v in data.items():
                    if len(self.fields) != 0 and key2 not in self.fields:
                        continue
                    if first:
                        field +="`" + key2 + "`"
                        if key2 not in self.keys:
                            update += "`" + key2 + "`=VALUES(`" + key2 + "`)"
                    else:
                        field += ", `" + key2 + "`"
                        if key2 not in self.keys:
                            update += ", `" + key2 + "`=VALUES(`" + key2 + "`)"
                    update = update.strip(",")
                    first = False
            value  = ""
            is_first = True
            for col in data:
                if len(self.fields) != 0 and col not in self.fields:
                    continue
                if is_first:
                    value  += "('" + str(data[col]) + "'"
                else:
                    value  += ", '" + str(data[col]) + "'"
                is_first = False
            if '' != value:
                value += ")"
            if big_first and '' != value:
                mult_value += value
            elif '' != value:
                mult_value += "," + value

            big_first = False

        if '' == mult_value:
            return False

        sql = "INSERT INTO %s (%s) VALUES %s ON DUPLICATE KEY UPDATE %s" % (fullTable, field, mult_value, update)
        if self.debug:
            print sql

        try:
            if self.con is None:
                self._createCon()
            cursor = self.con.cursor(cursorclass = MySQLdb.cursors.DictCursor)
        except Exception, e:
            if self.debug:
                print e
            return False

        try:
            lines = cursor.execute(sql)
            #self.con.commit(sql)
            cursor.close()
            if lines >= 0:
                return True
            return False
        except Exception, e:
            cursor.close()
            if self.debug:
                print e
            return False

    def execute(self, sql):
        "execute your own sql for insert or update"
        fullTable = ''
        if sql.find('__TABLE__') and not self.tableName is None:
            fullTable = "`" + self.dbName + "`.`" + self.tableName + "`"

        sql = sql.replace('__TABLE__', fullTable)
        if self.debug:
            print sql

        try:
            if self.con is None:
                self._createCon()
            cursor = self.con.cursor(cursorclass = MySQLdb.cursors.DictCursor)
        except Exception, e:
            if self.debug:
                print e
            return False

        try:
            lines = cursor.execute(sql)
            #self.con.commit(sql)
            cursor.close()
            if lines >= 0:
                return True
            return False
        except Exception, e:
            cursor.close()
            if self.debug:
                print e
            return False

    def down_check_file(self, file_prefix, day):
        file = file_prefix + "."+day
        log_dir = "/home/disk1/log_rank_results/"
        file_path = log_dir + file
        if not os.path.exists(file_path):
            #cmd = "cd /home/disk1/log_rank_results &&  wget '"+url+"' -O "+file
            cmd = "./stat_scripts/down_log_file.sh %s %s" % (file_prefix,day)
            print cmd
            os.system(cmd)

        cmd = "cd /home/disk1/log_rank_results && wc -l "+file
        line = os.popen(cmd).read()
        line = line.split()
        print line
        if int(line[0]) < 5:
            now = datetime.datetime.fromtimestamp(int(time.time())).strftime('%Y-%m-%d %H:%M:%S')
            content = now +' : ' + file + ' is not ready'
            print content
            mail = MailModel()
            mail.send_mail(content)
            time.sleep(3600)
            self.task(params)
            return False
        
        return True
    
    
    

    
    
 
