#!/usr/bin/env python2
# Copyright (C) 2019 Intel Corporation
# SPDX-License-Identifier: BSD-3-Clause
import sys
import os
import argparse
import subprocess

FNULL = open(os.devnull, 'w')
cur_dir = os.getcwd()

supported_cpus = (
    "85",   # SKX/CLX
)

ocr_read = {
    "85": "cpu/event=0xbb,umask=0x1,offcore_rsp=0x7bc0007f7,name=read/",
}

ocr_write = {
    "85": "cpu/event=0xb7,umask=0x1,offcore_rsp=0x7bc000002,name=write/",
}

uncore_imc_read = {
    "85": "uncore_imc_INDEX/event=0x10,umask=0x0,name=UNC_M_RPQ_INSERTS_IMC_INDEX/",
}

uncore_imc_write = {
    "85": "uncore_imc_INDEX/event=0x20,umask=0x0,name=UNC_M_WPQ_INSERTS_IMC_INDEX/",
}

core_all_loads = {
    "85": "cpu/event=0xd0,umask=0x81,name=MEM_INST_RETIRED.ALL_LOADS/",
}

core_all_stores = {
    "85": "cpu/event=0xd0,umask=0x82,name=MEM_INST_RETIRED.ALL_STORES/",
}

class PerfRun(object):
    """Control a perf process"""
    def __init__(self):
        self.perf = None

    def execute(self, r):
        self.perf = subprocess.Popen(r, stdout=FNULL)

    def wait(self):
        ret = 0
        if self.perf:
            ret = self.perf.wait()
        return ret

def task_args(cpu, measure_time, pid):
    if pid == -1:
        return [perf, "stat", "-a", "--per-thread", "-e", ocr_read[cpu],\
                "-e", core_all_stores[cpu], "-o", os.path.join(cur_dir, "logs", "task.log"),\
                "--", "sleep", "%d" % (measure_time)]
    return [perf, "stat", "-p", "%d" % (pid), "-e", ocr_read[cpu], "-e", core_all_stores[cpu],\
            "-o", os.path.join(cur_dir, "logs", str(pid), "task.log"),\
            "--", "sleep", "%d" %(measure_time)]

def start_task(cpu, measure_time, pid):
    if pid == -1:
        lp = os.path.join(cur_dir, "logs", "task.log")
    else:
        lp = os.path.join(cur_dir, "logs", str(pid), "task.log")

    if path_exists(lp):
        os.remove(lp)

    task = PerfRun()
    # collect per-task offcore_response reads/writes, and MEM_INST_RETIRED.ALL_LOADS/ALL_STORES
    task.execute(task_args(cpu, measure_time, pid))
    return task

def all_stores_args(cpu, measure_time, pid, log_path):
    return [perf, "stat", "-a", "-e", core_all_stores[cpu], "-o", log_path,\
            "--", "sleep", "%d" %(measure_time)]

def collect_all_stores(cpu, measure_time, pid):
    if pid == -1:
        lp = os.path.join(cur_dir, "logs", "system.log")
    else:
        lp = os.path.join(cur_dir, "logs", str(pid), "system.log")

    if path_exists(lp):
        os.remove(lp)

    store = PerfRun()
    # collect system wide LOADS/STORES
    store.execute(all_stores_args(cpu, measure_time, pid, lp))
    return store

exists_cache = dict()

def path_exists(s):
    if s in exists_cache:
        return exists_cache[s]
    found = os.path.exists(s)
    exists_cache[s] = found
    return found

def multiple_imc(cpu, l):
    i = 0
    while True:
        if i == 12:
            break
        path = "/sys/devices/uncore_imc_" + "%d" % (i)
        if path_exists(path):
            l.append("-e")
            s = uncore_imc_read[cpu]
            s = s.replace("INDEX", str(i))
            l.append(s)

            l.append("-e")
            s = uncore_imc_write[cpu]
            s = s.replace("INDEX", str(i))
            l.append(s)
        i += 1

def unc_imc_args(cpu, measure_time, pid, log_path):
    if path_exists("/sys/devices/uncore_imc"):
        return [perf, "stat", "-e", uncore_imc_read[cpu], "-e", uncore_imc_write[cpu],\
                "-o", log_path, "--", "sleep", "%d" % (measure_time)], 0

    if path_exists("/sys/devices/uncore_imc_0"):
        l = [perf, "stat"]
        multiple_imc(cpu, l);
        l.append("-o")
        l.append(log_path)
        l.append("--")
        l.append("sleep")
        l.append("%d" % (measure_time))
        return l, 1

    print("Can't find uncore imc box. Missing kernel support?")
    sys.exit(-1)

def start_unc_imc(cpu, measure_time, pid):
    if pid == -1:
        lp = os.path.join(cur_dir, "logs", "unc.log")
    else:
        lp = os.path.join(cur_dir, "logs", str(pid), "unc.log")
        l_dir = os.path.join(cur_dir, "logs", str(pid))

    if path_exists(lp):
        os.remove(lp)

    unc = PerfRun()
    l, mult_imc = unc_imc_args(cpu, measure_time, pid, lp)

    if pid != -1 and not path_exists(l_dir):
            os.makedirs(l_dir, 0o755)

    unc.execute(l)
    return unc, mult_imc

def get_cpu_model():
    m = os.popen('lscpu | grep "Model:"').read().split(':')[1].strip()
    return m

def get_pid_max():
    m = os.popen('cat /proc/sys/kernel/pid_max').read().strip()
    return int(m)

def tool_installed(name):
    try:
        devnull = open(os.devnull)
        subprocess.Popen([name], stdout=devnull, stderr=devnull).communicate()
    except OSError as e:
        if e.errno == os.errno.ENOENT:
            return False
    return True

p_id = -1
m_time = 5

cpu_model = get_cpu_model()
if cpu_model not in supported_cpus:
    sys.exit("CPU not supported!")

perf = "perf"
if not tool_installed(perf):
    sys.exit("perf not available. Please install it first.")

p = argparse.ArgumentParser(description='Collect per-task memory read/write bandwidth.')
p.add_argument('-p', '--pid', type=int, help='task PID to be monitored, default -1 for all tasks')
p.add_argument('-t', '--time', type=int, help='measure time in seconds, default 5s')

args = p.parse_args()
if args.pid != "":
    p_id = int(args.pid)
    if p_id > get_pid_max() or p_id < -1:
        sys.exit("Invalid PID: %d" % p_id)
if args.time != "":
    m_time = int(args.time)
    if m_time <= 0:
        sys.exit("Invalid measure time: %d" % m_time)

log_dir = os.path.join(cur_dir, "logs")
if not os.path.exists(log_dir):
    os.mkdir(log_dir)

unc_prun, multi_imc = start_unc_imc(cpu_model, m_time, p_id)
task_prun = start_task(cpu_model, m_time, p_id)
store_prun = collect_all_stores(cpu_model, m_time, p_id)

unc_prun.wait()
task_prun.wait()
store_prun.wait()

sys.exit(multi_imc)
