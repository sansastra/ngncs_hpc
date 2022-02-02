'''
William Orozco
worozco at ucdavis dot edu
January 2022

This script:
- Connects via SSH to the virtual machines through the gateways node1 and node2
- manipulates the flows from the ToR through RYU SDN controller app REST API OFCTL_REST
- handles MEMS optical switch reconfiguration through SCPI protocol
'''

from  ssh_flow_management import *


'''
====================================
import libraries
====================================
'''
import json
import threading

'''
====================================
DEFINITIONS
====================================
'''

'''
define gateways and vms in the json file
gateways:   {ID: [IP, username, password]}
vms:        {ID: [IP, username, password, Gateway ID]} where gw id is the host server ID for the VM

'''
IPERF_TIME = 60  # duration of the experiment, in seconds
RECONFIGURATION_1 = 20
#MAKE_BEFORE_BREAK_2 = 30 #make before break 1 happens at t=0
RECONFIGURATION_2 = 40
BW_IPERF = '4g'  # bandwidth for the experiment

credentials = json.load(open('credentials.json'))

# define the URL of the sdn controller app ofctl_rest
OFCTL_REST_IP = credentials['ip']
ADD_FLOW_URI = credentials['add_flow']
CLEAR_FLOWS_URI = credentials['clear_flow']
DELETE_FLOWS_URI = credentials['delete_flow']

# datapath ID of virtual bridges in pica8 switch - TODO: GET THIS DATA AUTOMATICALLY
DPID_BR0 = int(credentials['dpid'][0])
DPID_BR1 = int(credentials['dpid'][1])

# define the gateway and vm credentials for ssh
gateway_credentials = credentials['gateway_credentials']
vm_credentials = credentials['vm_credentials']

# tcpdump directory
TCP_TEST_DIRECTORY = credentials['tcpdump_file_datapath']
#TCP_TEST_DIRECTORY = "Desktop/pcap_files/"


'''
===========================================
Experiment
===========================================
'''

# Initialize flows. Call before connecting to servers. Make before break approach
#TRUNK1 priority 10 and 5, trunk 2 priority 7.
del_all_flows(DPID_BR0)
del_all_flows(DPID_BR1)
add_flows_vm1_vm4_v2()

# Connect to gateways and virtual machines
gws, vms = connect_to_vms_pssh()

'''
Threading section - traffic reconfiguration with flow manipulation
'''
thread_instance = []

# Reconfigure from trunk1 to trunk2
#https://stackoverflow.com/questions/25734595/python-threading-confusing-code-int-object-is-not-callable
reconfigure = threading.Timer(RECONFIGURATION_1, del_flows_trunk1, args=(10,))
reconfigure.start()
thread_instance.append(reconfigure)

# Make trunk1 before break trunk2
#return_traffic = threading.Timer(MAKE_BEFORE_BREAK_2, del_flows_trunk1(10))
#return_traffic.start()
#thread_instance.append(return_traffic)

# Reconfigure from trunk2 to trunk1
reconfigure2 = threading.Timer(RECONFIGURATION_2, del_flows_trunk2, args=(7,))
reconfigure2.start()
thread_instance.append(reconfigure2)


'''
ssh section - running iperf, tcpdump
'''
# run packet capture
# This works once you add the user to a group with permissions to run tcpdump without sudo
# https://askubuntu.com/questions/530920/tcpdump-permissions-problem
tcpdump_vm(vms['1'],t=IPERF_TIME+3, directory=TCP_TEST_DIRECTORY, bw=BW_IPERF)

# run iperf
iperf_s(vms['4'])
iperf_c(vms['1'],t=IPERF_TIME,b=BW_IPERF)

for thread in thread_instance:
    thread.join()
