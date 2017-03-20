#!/bin/bash
BASEDIR=`cd "$(dirname "$0")"; pwd`
cd $BASEDIR
#iDays=1
#DATE=`date -d "-$iDays days" "+%Y-%m-%d"`
#echo $DATE

#python send_email.py $DATE
python send_email.py
