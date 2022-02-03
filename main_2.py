'''
William Orozco
worozco at ucdavis dot edu
January 2022

This script:
- Connects via SSH to the virtual machines through the gateways node1 and node2
- manipulates the flows from the ToR through RYU SDN controller app REST API OFCTL_REST
- handles MEMS optical switch reconfiguration through SCPI protocol

Experiment topology 2
vm1 -------- bridge0 ------------------bridge1 ----------- vm4
				|							|
				|							|
				|							|
				|							|
vm2 -------- bridge2 ------------------bridge3 ----------- vm3

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
RECONFIGURATION_1 = 30
#MAKE_BEFORE_BREAK_2 = 30 #make before break 1 happens at t=0
RECONFIGURATION_2 = 40
BW_IPERF = '10g'  # bandwidth for the experiment

credentials = json.load(open('credentials.json'))

# define the URL of the sdn controller app ofctl_rest
OFCTL_REST_IP = credentials['ip']
ADD_FLOW_URI = credentials['add_flow']
CLEAR_FLOWS_URI = credentials['clear_flow']
DELETE_FLOWS_URI = credentials['delete_flow']

# datapath ID of virtual bridges in pica8 switch - TODO: GET THIS DATA AUTOMATICALLY
DPID_BR0 = int(credentials['dpid'][0])
DPID_BR1 = int(credentials['dpid'][1])
DPID_BR2 = int(credentials['dpid'][2])
DPID_BR3 = int(credentials['dpid'][3])

# define the gateway and vm credentials for ssh
gateway_credentials = credentials['gateway_credentials']
vm_credentials = credentials['vm_credentials']

# tcpdump directory, do not forget to create this in the server before running tcpdump remotely
TCP_TEST_DIRECTORY = credentials['tcpdump_file_datapath']
#TCP_TEST_DIRECTORY = "Desktop/pcap_files/"


'''
===========================================

Experiment topology 2
vm1 -------- bridge0 ------------------bridge1 ----------- vm4 
				|							|
				|							|
				|							|
				|							|
vm2 -------- bridge2 ------------------bridge3 ----------- vm3 	

===========================================
'''
# clear flow tables for all bridges
# Do not forget to check that all the bridges are connected to the controller.
del_all_flows(DPID_BR0)
del_all_flows(DPID_BR1)
del_all_flows(DPID_BR2)
del_all_flows(DPID_BR3)

# Initialize flows. Call before connecting to servers. Make before break approach

# link between servers 1 and 4 througn bridges 0 and 1.
add_flows_trunk1(priority=10)

# link between servers 2 and 3 througn bridges 2,0,1,3 (long path)
edit_flows_vm2_vm3_long_path(action='ADD',priority=8)
# link between servers 2 and 3 througn bridges 2,3 (short path)
edit_flows_vm2_vm3_short_path(action='ADD',priority=6)
# link between servers 2 and 3 througn bridges 2,0,1,3 (long path), lower priority
#edit_flows_vm2_vm3_long_path(action='ADD',priority=4)

# Connect to gateways and virtual machines
gws, vms = connect_to_vms_pssh()

# Now create the threads for reconfiguration.
thread_instance = []

# Reconfigure link between vm2 and vm3 from long path to short path by deleting all flows with priority 8
#https://stackoverflow.com/questions/25734595/python-threading-confusing-code-int-object-is-not-callable
reconfigure = threading.Timer(RECONFIGURATION_1, edit_flows_vm2_vm3_long_path, args=('DELETE',8,))
reconfigure.start()
thread_instance.append(reconfigure)

# Reconfigure back link between vm2 and vm3 to long path from short path by deleting all flows with priority 6
#reconfigure2 = threading.Timer(RECONFIGURATION_2, edit_flows_vm2_vm3_short_path, args=('DELETE',6,))
#reconfigure2.start()
#thread_instance.append(reconfigure2)


# run packet capture
# This works once you add the user to a group with permissions to run tcpdump without sudo
# https://askubuntu.com/questions/530920/tcpdump-permissions-problem
tcpdump_vm(vms['1'],t=IPERF_TIME+3, directory=TCP_TEST_DIRECTORY, bw=BW_IPERF)
tcpdump_vm(vms['2'],t=IPERF_TIME+3, directory=TCP_TEST_DIRECTORY, bw=BW_IPERF)


# run iperf
iperf_s(vms['4'])
iperf_s(vms['3'])
iperf_c(vms['1'], t=IPERF_TIME, b=BW_IPERF, ip_s='10.0.0.4')
iperf_c(vms['2'], t=IPERF_TIME, b=BW_IPERF, ip_s='10.0.0.3')

for thread in thread_instance:
    thread.join()
