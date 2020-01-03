# Per-Task Memory Bandwidth Monitoring
The Python scripts are created to provide a way for monitoring and reporting per-task memory read/write bandwidth consumption on Linux.

## Examples
1. Monitoring memory bandwidth consumption of specfied task(s):
![](https://github.com/intel/PerTaskMemBWMonitoring/blob/master/img/Screenshot_1.PNG)

2. Monitoring memory bandwidth consumption of all tasks:
![](https://github.com/intel/PerTaskMemBWMonitoring/blob/master/img/Screenshot_2.PNG)

## How it works
Using Linux profiling tool "perf", related PMU counters are read out from core/uncore/offcore registers and saved to log files(by bw-collect.py), then per-task memory read/write bandwidth are calculated out from the saved statistic data and printed out(by bw-report.py).

#### Per-task read bandwidth
Per-task read bandwidth are calculated as(MB/s):

``per-task memory read BW(MB/s) = all cache line reads from offcore_rsp * 64 / measure time / 1024*1024``

where bit definitions for offcore_rsp MSR can be found in Chapter 18.3.2 of Intel SDM.

#### Per-task write bandwidth
Since there's no direct PMU counts available so far for per-task write bandwidth, we are estimating it with the total memory write operations(UNC_M_WPA_INSERTS) and ratio of per-task/total memory write instructions retired, which translates into:

``per-task write BW(MB/s) = (Per-task MEM_INST_RETIRED.ALL_STORES / total MEM_INST_RETIRED.ALL_STORES) * all UNC_M_WPQ_INSERTS * 64 / measure time / 1024*1024``

## Setup
#### Prerequisites
* perf
* Python2 or Python3

__Python2(>=2.7)__ or __Python3(>=3.6)__, and Linux profiling tool __perf__ are needed to work with these scripts. Make sure both are installed.

#### Download scripts and run as root
Note that __root__ priviledge is needed to run these scripts. To get help info:
```
# ./bw-report.py -h
usage: bw-report.py [-h] [-p [PID [PID ...]]] [-t TIME] [-i INTERVAL]

Report per-task memory read/write bandwidth.

optional arguments:
  -h, --help            show this help message and exit
  -p [PID [PID ...]], --pid [PID [PID ...]]
                        task PID to monitor, multi PIDs with space in between,
                        default -1 for all tasks
  -t TIME, --time TIME  measure time in seconds, 0 for infinite, default 1000s
  -i INTERVAL, --interval INTERVAL
                        refresh interval in seconds, default 5s
```

## Supported CPUs
| CPU Family | Micro Architecture | Family/Model | Support Verified |
| :-----------------------: | :---------------: | :---------------: | :---------: |
| Xeon-SP | Sky Lake | 06/85 | YES |
| Xeon-SP | Cascade Lake | 06/85 | YES |

## Verified Linux Release
![](https://github.com/intel/PerTaskMemBWMonitoring/blob/master/img/Verified_Release.PNG)

