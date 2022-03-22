
'''
William Orozco
worozco at ucdavis dot edu
March 2022

This script:
- runs on monitor1
- Connects via ssh to controller1 and runs tcpdump
- Installs 2 flows on br1 and 2 flows on br4 per iteration. 200 iterations.

* Considering that Ryu app OFCTL_REST is already running on controller1
'''

'''
====================================
import libraries
====================================
'''

from ssh_flow_management import *
from pssh.config import HostConfig #This library worked.
from pssh.clients import ParallelSSHClient
import pssh.clients
import json
import threading
import time

credentials = json.load(open('credentials.json'))

#connect to controller1
controller1 = pssh.clients.ParallelSSHClient(hosts=[credentials["gateway_credentials"]["3"][0]],
                                             host_config=
                                             [HostConfig(user=credentials["gateway_credentials"]["3"][1],
                                                         password=credentials["gateway_credentials"]["3"][2])])

del_all_flows(DPID_BR1)
del_all_flows(DPID_BR2)
del_all_flows(DPID_BR3)
del_all_flows(DPID_BR4)
#run tcpdump on controller1 and save the file
tcpdump_vm(controller1, endpoints='',
               test_type='',
               directory=TCP_TEST_DIRECTORY,
               t=10,
               bw='flow_delay',
               vm_nic='enx000ec682b8bc',
               capture_size=1500)

for i in range(0,100):
    edit_flows_vm1_vm4_short_path(priority=i)
    if (i%20==0):
        print('iteration '+str(i))

print('***done***')
