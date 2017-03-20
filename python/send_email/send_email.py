#!/usr/bin/python
# -*- coding=utf8 -*-

import sys
import smtplib
from email.mime.text import MIMEText
import threading
import time, datetime
from datetime import timedelta, date
import DefaultDbConfig
import Model

# to 
#mailto_list=["1065108329@qq.com"]
mailto_list=["10651xx29@qq.com", "106510xxx9@qq.com"]
# cc
mailcc_list=["106xx329@qq.com", "1065xx329@qq.com"]
#bcc
mailbcc_list=["10651xx29@qq.com"]

# setting 
mail_server="smtp.exmail.qq.com"
mail_user="19999999999@qq.com"
mail_pass="xxx123"

# server
def send_mail(to_list, cc_list, bcc_list, sub, content):
    msg = MIMEText(content, 'html', 'utf-8')
    msg["Accept-Language"] = "zh-CN"
    #msg["Accept-Charset"] = "ISO-8859, utf-8"
    msg["Accept-Charset"] = "utf-8"
    to_all = []
    msg['Subject'] = sub
    msg['From'] = mail_user
    msg['To'] = ";".join(to_list)
    #to_all.append(to_list)
    [to_all.append(i) for i in to_list]
    msg['Cc'] = ";".join(cc_list)
    [to_all.append(i) for i in cc_list]
    msg['Bcc'] = ";".join(bcc_list)
    [to_all.append(i)  for i in bcc_list]
    try:
        server = smtplib.SMTP()
        server.connect(mail_server)
        server.starttls()
        #server.esmtp_features["auth"] = "LOGIN PLAIN"
        server.login(mail_user, mail_pass)
        #server.sendmail(mail_user, to_list, msg.as_string())
        #server.sendmail(mail_user, [to_list, cc_list, bcc_list], msg.as_string())
        server.sendmail(mail_user, to_all, msg.as_string())
        server.close()
        return True
    except Exception, e:
        print str(e)
        return False

def buildMengmengContent(currentDate, total_mengmeng, today_mengmeng):
    s = '<tr>'
    s += '<td valign="top" align="center" width="80">' + str(currentDate) + '</td>'
    s += '<td valign="top" align="center" width="80">' + str(total_mengmeng) + '</td>'
    s += '<td valign="top" align="center" width="80">' + str(today_mengmeng) + '</td>'
    s += '</tr>'

    return s

def buildDistrictContent(m, city, date1):
    s = '<tr>'
    s += '<td valign="top" align="center" width="80">' + str(city) + '</td>'
    #total
    sql="select count(Fid) as total_toy from t_toy_district_stat where Fdid != 101 and Fcity = '" + str(city) + "';"
    total_toys = m.query(sql)
    toy = 0
    for total_toy in total_toys:
        toy = total_toy['total_toy']
        break
    s += '<td valign="top" align="center" width="80">' + str(toy) + '</td>'

    sql="select count(Fid) as total_toy3 from t_toy_district_stat where Fdid in (5, 6, 7, 102) and Fcity = '" + str(city) + "';"
    total_toy3s = m.query(sql)
    toy3 = 0
    for total_toy3 in total_toy3s:
        toy3 = total_toy3['total_toy3']
        break
    s += '<td valign="top" align="center" width="80">' + str(toy3) + '</td>'

    sql="select count(Fid) as total_mengmeng from t_toy_district_stat where Fdid = 20 and Fcity = '" + str(city) + "';"
    mengmeng = m.query(sql)
    total_mengmeng = 0
    for mm in mengmeng:
        total_mengmeng = mm['total_mengmeng']
        break
    s += '<td valign="top" align="center" width="80">' + str(total_mengmeng) + '</td>'

    sql="select count(Fid) as total_toy2 from t_toy_district_stat where Fdid in (1, 3, 4) and Fcity = '" + str(city) + "';"
    total_toy2s = m.query(sql)
    toy2 = 0
    for total_toy2 in total_toy2s:
        toy2 = total_toy2['total_toy2']
        break
    s += '<td valign="top" align="center" width="80">' + str(toy2) + '</td>'

    #today
    sql="select count(Fid) as today_toy from t_toy_district_stat where  Fdid != 101 and Fdate = '" + str(date1) + "' and Fcity = '" + str(city) + "';"
    today_toys = m.query(sql)
    t_toy = 0
    for today_toy in today_toys:
        t_toy = today_toy['today_toy']
        break
    s += '<td valign="top" align="center" width="80">' + str(t_toy) + '</td>'

    sql="select count(Fid) as today_toy3 from t_toy_district_stat where  Fdate = '" + str(date1) + "' and Fdid in (5, 6, 7, 102) and Fcity = '" + str(city) + "';"
    today_toy3s = m.query(sql)
    t_toy3 = 0
    for today_toy3 in today_toy3s:
        t_toy3 = today_toy3['today_toy3']
        break
    s += '<td valign="top" align="center" width="80">' + str(t_toy3) + '</td>'

    sql="select count(Fid) as today_mengmeng from t_toy_district_stat where  Fdate = '" + str(date1) + "' and Fdid = 20 and Fcity = '" + str(city) + "';"
    mengmeng = m.query(sql)
    today_mengmeng = 0
    for mm in mengmeng:
        today_mengmeng = mm['today_mengmeng']
        break
    s += '<td valign="top" align="center" width="80">' + str(today_mengmeng) + '</td>'

    sql="select count(Fid) as today_toy2 from t_toy_district_stat where  Fdate = '" + str(date1) + "' and Fdid in (1, 3, 4) and Fcity = '" + str(city) + "';"
    today_toy2s = m.query(sql)
    t_toy2 = 0
    for today_toy2 in today_toy2s:
        t_toy2 = today_toy2['today_toy2']
        break
    s += '<td valign="top" align="center" width="80">' + str(t_toy2) + '</td>'

    s += '</tr>'

    #print "content:%s"%s
    return s

def getDate():
    #return str(datetime.datetime.utcfromtimestamp(time.time())+datetime.timedelta(hours=8))
    return str(datetime.datetime.utcfromtimestamp(time.time()))

def send_warning_mail(title, info):
    nowTime = getDate()
    #print "nowTime:%s"%nowTime
    try:
        #t = threading.Thread(target=send_mail, args=(mailto_list, title, str(nowTime)+" | \n"+str(info)))
        t = threading.Thread(target=send_mail, args=(mailto_list, mailcc_list, mailbcc_list, title, "\n"+str(info)))
        t.start()
    except:pass

if __name__ == "__main__":
    m = Model.Model(DefaultDbConfig.defaultDB)
    if len(sys.argv) >= 1:
        emailContent = ""
        districtContent = """<h3>玩具分地区排行榜(2016年9月7号之后数据)</h3>
            <table width="800" border="0" cellspacing="0" cellpadding="4">
                <tr>
                    <th width="80" align="center" bgcolor="#CECFAD" height="20" style="font-size:14px">城市</th>
                    <th width="80" align="center" bgcolor="#CECFAD" height="20" style="font-size:14px">玩具激活总数</th>
                    <th width="80" align="center" bgcolor="#CECFAD" height="20" style="font-size:14px">3代玩具激活总数</th>
                    <th width="80" align="center" bgcolor="#CECFAD" height="20" style="font-size:14px">你猜啊猜激活总数</th>
                    <th width="80" align="center" bgcolor="#CECFAD" height="20" style="font-size:14px">2代玩具激活总数</th>
                    <th width="80" align="center" bgcolor="#CECFAD" height="20" style="font-size:14px">当天玩具激活数</th>
                    <th width="80" align="center" bgcolor="#CECFAD" height="20" style="font-size:14px">当天3代玩具激活数</th>
                    <th width="80" align="center" bgcolor="#CECFAD" height="20" style="font-size:14px">当天你猜啊猜激活数</th>
                    <th width="80" align="center" bgcolor="#CECFAD" height="20" style="font-size:14px">当天2代玩具激活数</th>
                </tr>
                      """

        newContent = """<h3>你猜啊猜激活数据统计</h3>
        <table width="300" border="0" cellspacing="0" cellpadding="4">
                <tr>
                    <th width="80" align="center" bgcolor="#CECFAD" height="20" style="font-size:14px">日期 </th>
                    <th width="80" align="center" bgcolor="#CECFAD" height="20" style="font-size:14px">你猜啊猜总激活数  </th>
                    <th width="80" align="center" bgcolor="#CECFAD" height="20" style="font-size:14px">当日激活数</th>
                </tr>
                      """
        todayContent = "【你猜啊猜激活数据】昨日:"

        count = 0 
        while count < 7:
            count = count + 1
            today1 = date.today() - timedelta(days=count)
            sql2 = "select Ftoday_mengmeng from t_toy_stat where Fdate like '%" + str(today1) +"%';"
            mengmeng2 = m.query(sql2)
            for mm2 in mengmeng2:
                today_mengmeng = mm2['Ftoday_mengmeng']
                break

            sql="select Ftotal_mengmeng from t_toy_stat where Fdate like '%" + str(today1) + "%';"
            mengmeng = m.query(sql)
            for mm in mengmeng:
                total_mengmeng = mm['Ftotal_mengmeng']
                break

            msg = buildMengmengContent(today1, total_mengmeng, today_mengmeng)
            newContent += msg
            if count == 1:
                todayContent += str(today_mengmeng)
                todayContent += ",累计:"
                todayContent += str(total_mengmeng)

        newContent += """</table>"""
#        send_warning_mail(todayContent, newContent)

        emailContent += newContent
        emailContent += "\n\n"
        
        date1 = date.today() - timedelta(days=1)
        sql3 = "select count(Fid) as count, Fcity from t_toy_district_stat group by Fcity order by count desc;"
        datas = m.query(sql3)
        for data in datas :
            city = data['Fcity']
            msg2 = buildDistrictContent(m, city, date1)
            districtContent += msg2

        districtContent += """</table>"""
#        send_warning_mail(todayContent, districtContent)
        
        emailContent += districtContent
        send_warning_mail(todayContent, emailContent)



