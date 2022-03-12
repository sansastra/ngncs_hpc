'''
William Orozco
worozco at ucdavis dot edu
February 2022

This script:
- Connects via SSH to the virtual machines through the gateways node1 and node2
- manipulates the flows from the ToR through RYU SDN controller app REST API OFCTL_REST
- handles MEMS optical switch reconfiguration through SCPI protocol

Experiment topology 3
vm1 -------- bridge1 ------------------bridge4 ----------- vm4
				|							|
				|____________   ____________|
				 ____________OTS____________
				|							|
				|							|
vm2 -------- bridge2                    bridge3 ----------- vm3

'''

'''
====================================
import libraries
====================================
'''

from ssh_flow_management import *
import json
import threading
import time

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

NUM_EXPERIMENTS = 1
IPERF_TIME = 20  # duration of the experiment, in seconds.
#Except for bandwidth steering (dual),the following times are 5+1, 10+1, 15+1 to compensate the delay of initialization steps
MAKE_BEFORE_BREAK_1 = 6 # open flow switch traffic to backup links before optical reconfiguration
RECONFIGURATION_1 = 11
MAKE_BEFORE_BREAK_2 = 16 # open_flow switch traffic to main links after optical reconfiguration
BW_IPERF = '10g'  # bandwidth for the experiment
#   test types: single_mbb_<suffix>, single_ots_<suffix>, dual_mbb_<suffix>, dual_ots_<suffix>
#TEST_TYPE = 'single_mbb_v3_1'
#TEST_TYPE = 'single_ost_v1'
TEST_TYPE = 'dual_mbb_v1'

TCP_CAPTURE=True

# ports for optical reconfiguration
PORTS_OTS_BEFORE = [[21, 22, 23, 24], [54, 53, 56, 55]]
PORTS_OTS_AFTER = [[22, 23], [55, 54]]

# Load credentials file
credentials = json.load(open('credentials.json'))

# define the URL of the sdn controller app ofctl_rest
OFCTL_REST_IP = credentials['ip']
ADD_FLOW_URI = credentials['add_flow']
CLEAR_FLOWS_URI = credentials['clear_flow']
DELETE_FLOWS_URI = credentials['delete_flow']

# datapath ID of virtual bridges in pica8 switch
DPID_BR1 = int(credentials['dpid'][0])
DPID_BR2 = int(credentials['dpid'][1])
DPID_BR3 = int(credentials['dpid'][2])
DPID_BR4 = int(credentials['dpid'][3])

# define the gateway and vm credentials for ssh
gateway_credentials = credentials['gateway_credentials']
vm_credentials = credentials['vm_credentials']

# IP of the optical switch for the TCP socket
ip_ots = credentials["ip_ots"]
port_ots = credentials["port_ots"]

# tcpdump directory, do not forget to create this in the server before running tcpdump remotely
TCP_TEST_DIRECTORY = credentials['tcpdump_file_datapath']

'''
===========================================

Experiment topology 2
vm1 -------- bridge1 ------------------bridge4 ----------- vm4 
				|							|
				|____________   ____________|
				 ____________OTS____________
				|							|
				|							|
vm2 -------- bridge2                    bridge3 ----------- vm3	

===========================================
'''
# Open TCP socket with Optical switch and create connections
s = ots_connect_tcp_socket(ip=ip_ots, port=port_ots)

# Connect to gateways (host servers) and virtual machines (guest vm)
gws, vms = connect_to_vms_pssh(gateway_credentials=gateway_credentials,
                               vm_credentials=vm_credentials)

#execute these dummy console commands on the servers to avoid a long execution time the next time another command is executed.
hostname(vms['1'])
hostname(vms['2'])
hostname(vms['3'])
hostname(vms['4'])

#run iperf out of the for loop, so it is executed only once.
#iperf_s(vms['3'])

#wait a few seconds for ssh connections to be ready
#time.sleep(3)



for i in range(0, NUM_EXPERIMENTS):
    print("*****starting experiment " + str(i + 1) + "*****")
    # clear flow tables for all bridges
    # Do not forget to check that all the bridges are connected to the controller.
    start=time.time()
    del_all_flows(DPID_BR1)
    del_all_flows(DPID_BR2)
    del_all_flows(DPID_BR3)
    del_all_flows(DPID_BR4)
    end=time.time()
    print("elapsed time for resetting flows: " + str(end - start))
    print("---reset flows on all bridges---")

    # create optical links
    start=time.time()
    ots_connect_port(s, port_in=PORTS_OTS_BEFORE[0], port_out=PORTS_OTS_BEFORE[1])
    end=time.time()
    print("elapsed time for resetting optical connections: " + str(end - start))
    print("---reset optical connections---")

    start = time.time()
    # link between servers 1 and 4 through bridges 1 and 4.
    if 'dual' in TEST_TYPE:  # run tcpdump on vm1 if dual test for bandwidth steering experiment
        edit_flows_vm1_vm4_short_path(action='ADD', priority=9)

    # link between servers 2 and 3 through bridges 2,1,4,3, passing through optical switch (long path)
    edit_flows_vm2_vm3_long_path(action='ADD', priority=8)
    end=time.time()
    print("elapsed time for installing initial flows on ToR: " + str(end - start))

    # Now create the array that will store the thread timers for reconfiguration.
    thread_instance = []

    '''
    Make before break
    '''
    start=time.time()
    # 1. Send the traffic to backup links.
    if 'mbb' in TEST_TYPE:
        openflow_switch_traffic_1 = threading.Timer(MAKE_BEFORE_BREAK_1,
                                                    edit_flows_vm2_vm3_long_path_backup,
                                                    args=("ADD", 10,))
        openflow_switch_traffic_1_1 = threading.Timer(MAKE_BEFORE_BREAK_1+1,
                                                    edit_flows_vm2_vm3_long_path,
                                                    args=("DELETE", 8,))
    # 2.  Reconfigure link between vm2 and vm3 by creating new links on optical switch
    # https://stackoverflow.com/questions/25734595/python-threading-confusing-code-int-object-is-not-callable
    reconfigure = threading.Timer(RECONFIGURATION_1,
                                  ots_connect_port,
                                  args=(s, PORTS_OTS_AFTER[0], PORTS_OTS_AFTER[1],))

    # 3. Send the traffic back to reconfigured link through optical switch.
    if 'mbb' in TEST_TYPE:
        openflow_switch_traffic_2 = threading.Timer(MAKE_BEFORE_BREAK_2,
                                                    edit_flows_vm2_vm3_long_path,
                                                    args=("ADD", 12,))
        openflow_switch_traffic_2_1 = threading.Timer(MAKE_BEFORE_BREAK_2+1,
                                                    edit_flows_vm2_vm3_long_path_backup,
                                                    args=("DELETE", 10,))

    end=time.time()
    print("elapsed time for initializing threading timers: " + str(end - start))
    # run packet capture
    # This works once you add the user to a group with permissions to run tcpdump without sudo
    # https://askubuntu.com/questions/530920/tcpdump-permissions-problem
    ####tcpdump_vm(vms['1'],endpoints='vm1vm4', test_type=TEST_TYPE,t=IPERF_TIME+3, directory=TCP_TEST_DIRECTORY, bw=BW_IPERF)

    if TCP_CAPTURE:
        # tcpdump on tx
        start=time.time()
        tcpdump_vm(vms['2'],
                   endpoints='vm2vm3\|tx',
                   test_type=TEST_TYPE,
                   t=IPERF_TIME + 3,
                   directory=TCP_TEST_DIRECTORY,
                   bw=BW_IPERF)
        if 'dual' in TEST_TYPE: #run tcpdump on vm1 if dual test for bandwidth steering experiment
            tcpdump_vm(vms['1'],
                       endpoints='vm1vm4\|tx',
                       test_type=TEST_TYPE,
                       t=IPERF_TIME + 3,
                       directory=TCP_TEST_DIRECTORY,
                       bw=BW_IPERF)
        end=time.time()
        print("elapsed time for executing tcpdump: " + str(end - start))
        # tcpdump on rx
        # tcpdump_vm(vms['3'],endpoints='vm2vm3\|rx', test_type=TEST_TYPE, t=IPERF_TIME+3,  directory=TCP_TEST_DIRECTORY, bw=BW_IPERF)


    start = time.time()
    # run iperf
    if 'dual' in TEST_TYPE:  # run tcpdump on vm1 if dual test for bandwidth steering experiment
        iperf_s(vms['4'])
    iperf_s(vms['3'])
    if 'dual' in TEST_TYPE:  # run tcpdump on vm1 if dual test for bandwidth steering experiment
        iperf_c(vms['1'], t=IPERF_TIME, b=BW_IPERF, ip_s='10.0.0.4')
    iperf_c(vms['2'], t=IPERF_TIME, b=BW_IPERF, ip_s='10.0.0.3')

    end = time.time()
    print("elapsed time for executing iperf commands: "+str(end-start))
    # start threads after running iperf and tcpdump for accurate reconfiguration at the desired time
    reconfigure.start()
    if 'mbb' in TEST_TYPE:
        openflow_switch_traffic_1.start()
        openflow_switch_traffic_1_1.start()
        openflow_switch_traffic_2.start()
        openflow_switch_traffic_2_1.start()

    thread_instance.extend([reconfigure])
    if 'mbb' in TEST_TYPE:
        thread_instance.extend([openflow_switch_traffic_1, openflow_switch_traffic_1_1,
                                openflow_switch_traffic_2, openflow_switch_traffic_2_1])
    #print(thread_instance)
    for thread in thread_instance:
        thread.join()

    time.sleep(IPERF_TIME+5)
    print("*****done experiment " + str(i+1) + "*****")
