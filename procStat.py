#coding=utf-8
#liyunzhi@le.com

import os
import glob
import time
import shutil
import getopt
import sys
import re
import numpy
import pylab
import json
import csv

def LOG(aLogStr):
    print(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())+':'+aLogStr)

def execCmd(cmd):
    LOG(cmd)
    o = os.popen(cmd)
    r = o.read()
    o.close()
    return r

def adbShellCmd(cmd):
    return execCmd('adb shell ' + '\"' + cmd + '\"')

kswapdStart = 0
def parseProc():
    global kswapdStart
    matchPs = r"(\w+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\w+)\s+\w+\s+(\w)\s+(.*)"

    procList = []
    procs = adbShellCmd('ps').splitlines()
    for line in procs:
        proc = {}
        match =re.match(matchPs, line)
        if (match == None):
            continue

        proc['user'],proc['pid'],proc['ppid'],proc['vss'],proc['rss'],proc['wchan'],proc['stat'],proc['name'] = match.groups()

        if (proc['name'].startswith('kswapd')):
            ret = adbShellCmd('cat /proc/%s/stat'%proc['pid']).split()
            kswapdRtTotal = int(ret[14]) + int(ret[13])
            if (kswapdStart == 0):
                kswapdStart = kswapdRtTotal
            kswapdRun = kswapdRtTotal - kswapdStart
            proc['kswapdRT'] = kswapdRun
        procList.append(proc)
    return procList

def countUserProc():
    usrProcNo = 0
    sysProcNo = 0

    procList = parseProc()
    for proc in procList:
        if re.match('u[0-9]', proc['user']) != None:
            usrProcNo += 1
        if (proc['name'].startswith('kswapd')):
            kswapdRunTime = proc['kswapdRT']

    sysProcNo = procList.__len__() - usrProcNo
    #return usrProcNo, sysProcNo
    return dict(usrProc=usrProcNo, sysProc=sysProcNo, kswapdRunTime=kswapdRunTime)

def getOOMScore():
    oomCmd = r"""ls /proc|grep ^[1-9]|while read l;do read comm < /proc/$l/comm;read oom < /proc/$l/oom_score_adj;if [ $oom -gt 0 ]; then printf "%d\\t%s\\t%d\\n" $l $comm $oom;fi;done"""
    oom = []
    ret = adbShellCmd(oomCmd).splitlines()
    oom = [x for x in ret if (x.__len__() > 0 and x.split()[0].isdigit())]

    oomList = []
    for line in oom:
        proc = {}
        line = line.split()
        proc['pid'] = int(line[0])
        proc['comm'] = line[1]
        proc['oom_score'] = int(line[2])
        oomList.append(proc)

    oomList.sort(key=lambda x: x['oom_score'])
    return oomList

def oomScoreStet(oomList = None):
    if oomList == None:
        oomList = getOOMScore()

    oomStat = {}

    for x in oomList:
        lambda x:x['oom_score']

def getMemInfo():
    ret = adbShellCmd('cat /proc/meminfo').splitlines()
    memInfo = {}
    for line in  ret:
        line = line.split()
        try:
            item,value = line[0:2]
            memInfo[item] = value
        except:
            pass
    return memInfo

def getVmStat():
    ret = adbShellCmd('cat /proc/vmstat').splitlines()
    vmstat = {}
    for line in  ret:
        line = line.split()
        try:
            item,value = line[0:2]
            vmstat[item] = value
        except:
            pass
    return vmstat

def getLmkStat():
    ret = adbShellCmd('cat /sys/module/lowmemorykiller/parameters/lmk_stat*').splitlines()
    try:
        lmk_stat_kill, lmk_stat_kill_level, lmk_stat_unkill = [x for x in ret if x.__len__() > 0]
    except:
        return dict()
    return dict(lmk_stat_kill = lmk_stat_kill,
                 lmk_stat_kill_level=lmk_stat_kill_level,
                 lmk_stat_unkill=lmk_stat_unkill)

def getAllSysInfo():
    vmstat = getVmStat()
    meminfo = getMemInfo()
    proc = countUserProc()
    lmkstat = getLmkStat()

    procInfo = dict()
    procInfo.update(vmstat)
    procInfo.update(meminfo)
    procInfo.update(proc)
    procInfo.update(lmkstat)

    return procInfo

def logging(tag, path = './', interval = 1, duration = 1800):
    localtime = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
    os.chdir(path)
    path = os.path.join(path, tag+'_'+localtime+'.csv')
    LOG('Logging into file'+path)
    fd = open(path, 'w+')
    csvwrt = csv.DictWriter(fd, fieldnames=None,dialect='unix')

    starttime = time.time()
    curtime = starttime
    endtime = starttime + duration


    while (curtime < endtime) :

        curtime = time.time()
        logitem = dict(time=(curtime-starttime).__round__(2))
        logitem.update(getAllSysInfo())

        if csvwrt.fieldnames == None:
            csvwrt.fieldnames = logitem.keys()
            csvwrt.writeheader()

        csvwrt.writerow(logitem)

        while (time.time() < curtime + interval):
            time.sleep(0.01)

    fd.close()

if __name__ == '__main__':
    logging(tag='mem')
