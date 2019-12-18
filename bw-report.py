#!/usr/bin/env python2
# Copyright (C) 2019 Intel Corporation
# SPDX-License-Identifier: BSD-3-Clause

import sys
import os
import subprocess
import argparse
import shutil
from signal import signal, SIGINT

# all time in seconds
DEFAULT_MEASURE_TIME = 1000
DEFAULT_INTERVAL = 5

FNULL = open(os.devnull, 'w')
cur_dir = os.getcwd()
exists_cache = dict()

def path_exists(s):
    if s in exists_cache:
        return exists_cache[s]
    found = os.path.exists(s)
    exists_cache[s] = found
    return found

def collect_system_bw(all_stores_dict, pid):
    if pid == -1:
        lp = os.path.join(cur_dir, "logs", "system.log")
    else:
        lp = os.path.join(cur_dir, "logs", str(pid), "system.log")

    if not path_exists(lp):
        sys.exit("No %s found, something wrong!\n" % lp)

    fd = open(lp)
    t = 0.0
    while True:
        try:
            l = fd.readline()
            if not l:
                break
            l = l.split()

            if len(l) == 2:
                if l[1] == "MEM_INST_RETIRED.ALL_STORES":
                    all_stores_dict[0] = int(l[0].replace(',', ''))

            if len(l) == 4 and l[1] == "seconds":
                t = float(l[0])
        except IOError:
            break

    fd.close()
    return t

def collect_task_bw(read_dict, all_stores_dict, pid):
    if pid == -1:
        lp = os.path.join(cur_dir, "logs", "task.log")
    else:
        lp = os.path.join(cur_dir, "logs", str(pid), "task.log")

    if not path_exists(lp):
        sys.exit("No %s found, something wrong!\n" % lp)

    fd = open(lp)
    t = 0.0
    start_time = ""

    while True:
        try:
            l = fd.readline()
            if not l:
                break
            l = l.split()

            if pid != -1:
                if len(l) == 2:
                    if l[1] == "read":
                        read_dict[str(pid)] = int(l[0].replace(',', ''))
                    if l[1] == "MEM_INST_RETIRED.ALL_STORES":
                        all_stores_dict[str(pid)] = int(l[0].replace(',', ''))
            else:
                if len(l) == 3:
                    if l[2] == "read":
                        read_dict[l[0]] = int(l[1].replace(',', ''))
                    if l[2] == "MEM_INST_RETIRED.ALL_STORES":
                        all_stores_dict[l[0]] = int(l[1].replace(',', ''))
            if len(l) == 4 and l[1] == "seconds":
                t = float(l[0])
            if len(l) == 8 and l[1] == "started":
                start_time = str(l[6])
        except IOError:
            break

    fd.close()
    return start_time, t

def collect_imc_bw(pid):
    if pid == -1:
        lp = os.path.join(cur_dir, "logs", "unc.log")
    else:
        lp = os.path.join(cur_dir, "logs", str(pid), "unc.log")

    if not path_exists(lp):
        sys.exit("No %s found, something wrong!\n" % lp)

    fd = open(lp)
    read_bw = 0
    write_bw = 0
    t = 0.0

    while True:
        try:
            l = fd.readline()
            if not l:
                break
            l = l.split()
            if len(l) == 3:
                if "RPQ" in l[2]:
                    read_bw = float(l[0].replace(',', '')) * 1000000
                else:
                    write_bw = float(l[0].replace(',', '')) * 1000000
            if len(l) == 4:
                t = float(l[0])
        except IOError:
            break

    fd.close()
    return read_bw, write_bw, t

def collect_multi_imc_bw(pid):
    if pid == -1:
        lp = os.path.join(cur_dir, "logs", "unc.log")
    else:
        lp = os.path.join(cur_dir, "logs", str(pid), "unc.log")

    if not path_exists(lp):
        sys.exit("No %s found, something wrong!\n" % lp)

    fd = open(lp)
    read_total = 0
    write_total = 0
    t = 0.0

    while True:
        try:
            l = fd.readline()
            if not l:
                break
            l = l.split()
            if len(l) == 2:
                if "RPQ" in l[1]:
                    read_total += float(l[0].replace(',', ''))
                else:
                    write_total += float(l[0].replace(',', ''))
            if len(l) == 4:
                t = float(l[0])
        except IOError:
            break

    fd.close()
    return float(read_total) * 64, float(write_total) * 64, t

def get_pid_max():
    m = os.popen('cat /proc/sys/kernel/pid_max').read().strip()
    return int(m)

def parse_args(cmd_d):
    ap = argparse.ArgumentParser(description='Report per-task memory read/write bandwidth.')
    ap.add_argument('-p', '--pid', type=int, nargs='*', default=-1,\
            help='task PID to monitor, multi PIDs with space in between, default -1 for all tasks')
    ap.add_argument('-t', '--time', type=int, default=1000,\
            help='measure time in seconds, 0 for infinite, default 1000s')
    ap.add_argument('-i', '--interval', type=int, default=5,\
            help='refresh interval in seconds, default 5s')

    args = ap.parse_args()
    if args.pid != -1:
        num_tasks = len(args.pid)

        for pid in args.pid:
            if pid > get_pid_max() or pid < -1:
                sys.exit("Invalid PID: %d" % pid)

            cmd = ["./bw-collect.py"]
            cmd.append("--pid")
            cmd.append(str(pid))
            cmd_d[str(pid)] = cmd
    else:
        pid = -1
        cmd = ["./bw-collect.py"]
        cmd.append("--pid")
        cmd.append(str(pid))

    if args.time > 0:
        m_time = args.time
    elif args.time == 0:
        m_time = sys.maxint if (sys.version == 2) else sys.maxsize
    else:
        print("Invalid measure time(%d), using default(1000s)." % args.time)
        m_time = DEFAULT_MEASURE_TIME

    if args.interval:
        if args.interval > 0 and args.interval < m_time:
            i = args.interval
        else:
            print("Invalid interval(%d), using default(5s)." % args.interval)
            i = DEFAULT_INTERVAL
    else:
        i = DEFAULT_INTERVAL if(m_time > DEFAULT_INTERVAL) else m_time

    if pid == -1:
        cmd.append("--time")
        cmd.append(str(i))
        cmd_d[str(pid)] = cmd
    else:
        for pid in cmd_d:
            cmd = cmd_d[str(pid)]
            cmd.append("--time")
            cmd.append(str(i))
            cmd_d[str(pid)] = cmd

    print("")
    print("Monitoring %s for %d seconds, refreshing in every %d seconds."\
            % ("all tasks" if(pid == -1) else "%d task(s)" % num_tasks, m_time, i))

    return  pid, m_time, i

def clean_logs(pid):
    if pid == -1:
        if path_exists(os.path.join(cur_dir, "logs", "task.log")):
            os.remove(os.path.join(cur_dir, "logs", "task.log"))
        if path_exists(os.path.join(cur_dir, "logs", "unc.log")):
            os.remove(os.path.join(cur_dir, "logs", "unc.log"))
        if path_exists(os.path.join(cur_dir, "logs", "system.log")):
            os.remove(os.path.join(cur_dir, "logs", "system.log"))
    else:
        if path_exists(os.path.join(cur_dir, "logs", str(pid))):
            shutil.rmtree(os.path.join(cur_dir, "logs", str(pid)))

    # remove logs folder if it's empty
    if not os.listdir(os.path.join(cur_dir, "logs")):
       os.rmdir(os.path.join(cur_dir, "logs")) 

def calc_print_bw(pid, multi_imc):
    run = 1

    task_read_dict = {}
    task_all_stores_dict = {}
    start_time, task_time = collect_task_bw(task_read_dict, task_all_stores_dict, pid)

    system_all_stores_dict = {}
    system_time = collect_system_bw(system_all_stores_dict, pid)

    if multi_imc == 1:
        imc_read_bw, imc_write_bw, imc_time = collect_multi_imc_bw(pid)
    else:
        imc_read_bw, imc_write_bw, imc_time = collect_imc_bw(pid)

    if task_time == 0.0 or imc_time == 0.0 or system_time == 0.0:
        sys.exit("Measured time is 0, retry please!")

    imc_read_sec = imc_read_bw / (1024*1024) / imc_time
    imc_write_sec = imc_write_bw / (1024*1024) / imc_time

    for k in sorted(task_read_dict, key=task_read_dict.__getitem__, reverse=True):
        v = float(task_read_dict[k] * 64)
        task_read_sec = v / (1024*1024) / task_time
        r = task_read_sec / imc_read_sec

        task_write_sec = 0.0

        task_name = ""
        # when "perf stat -a --per-thread..", k looks like "python2-47361",
        # need to extract pid out from the string
        if pid == -1:
            task_pid = k.split('-')[-1]
        if k in task_all_stores_dict and system_all_stores_dict[0] > 0:
            f = float(task_all_stores_dict[k]) / float(system_all_stores_dict[0])
            task_write_sec = f * imc_write_sec

            # when 'perf stat --per-thread' for all tasks, get task name from task_pid instead of k
            if pid == -1:
                task_name = k.split('-')[0]
            else:
                # if failed to get the task_name, do not print for this task
                args = ['cat', '/proc/%s/comm' % k]
                try:
                    task_name = subprocess.check_output(args, stderr=FNULL).strip()
                    if sys.version_info.major > 2:
                        task_name = task_name.decode()
                except subprocess.CalledProcessError:
                    run = 0
                    break

            # only print for tasks that read/write BW ratio is not 0.0
            if(r > 0.0005 or f > 0.0005):
                print("%8s%10.1f MiB/s%10.1f MiB/s%8s%16s%10.1f MiB/s%7.1f%%%10.1f MiB/s%9.1f%%" \
                % (start_time, imc_read_sec, imc_write_sec, task_pid if pid == -1 else k, \
                task_name, task_read_sec, r * 100.0, task_write_sec, f * 100.0))

    clean_logs(pid)
    return run

def get_terminal_resolution():
    rows, columns = os.popen('stty size', 'r').read().split()
    return columns, rows

# main() starts
time = 0
cmd_dict = {}

p_id, measure_time, interval = parse_args(cmd_dict)

if p_id == -1:
    print("!!! NOTE: Tasks with 0.0 Task/iMC read & write BW Ratio are not listed.")

def sighandler(sig, frame):
    clean_logs(p_id)
    print("")
    exit("Monitoring interrupted by SIGINT or user CTRL-C. Logs cleared.")

signal(SIGINT, sighandler)

print("")
print("%8s%16s%16s%8s%16s%16s%8s%16s%10s" %("Time", "iMCReadBW", "iMCWriteBW", "PID", "TaskName", \
        "TaskReadBW", "ReadBW%", "*TaskWriteBW", "*WriteBW%"))

while time < measure_time:
    procs = []
    for p in sorted(cmd_dict, key=cmd_dict.__getitem__, reverse=True):
        proc = subprocess.Popen(cmd_dict[p], stderr=FNULL)
        procs.append((p, proc))

    for p, proc in procs:
        out, err = proc.communicate()
        if err:
            # 'perf stat' failed means process stopped, remove it from cmd_dict[p, cmd]
            del cmd_dict[p]
            clean_logs(p)
            continue

        running = calc_print_bw(int(p), 1)
        if running == 0:
            # task stopped, remove it from cmd_dict[p, cmd]
            del cmd_dict[p]

    time = time + interval


print("Done!")
