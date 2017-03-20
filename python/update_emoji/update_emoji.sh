#!/bin/bash
BASEDIR=`cd "$(dirname "$0")"; pwd`
cd $BASEDIR

Env=$1
Phone=$2

date >> log/update_emoji.log
python update_emoji.py $Env $Phone >> log/update_emoji.log
