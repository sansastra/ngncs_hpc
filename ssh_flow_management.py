'''
Script to connect to the virtual machines through the gateways node1 and node2
jumpssh: blocking
https://pypi.org/project/jumpssh/

fabric: non blocking implementation with threads. Did not work.
https://www.fabfile.org/index.html

parallel ssh: non blocking

William Orozco
worozco at ucdavis dot edu
December 2021
'''


'''
====================================
import libraries
====================================
'''
import json
import multiprocessing
import threading
import requests
import socket
from fabric import Connection  # this library uses threading
from jumpssh import SSHSession  # this library is blocking
from pssh.config import HostConfig #This library worked.
from pssh.clients import ParallelSSHClient
import pssh.clients
import datetime

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
RECONFIGURATION_1=20
RECONFIGURATION_2=40
BW_IPERF = '5g'  # bandwidth for the experiment

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

# tcpdump directory
#TCP_TEST_DIRECTORY = credentials['tcpdump_file_datapath'],
TCP_TEST_DIRECTORY = "Desktop/pcap_files/"
'''
====================================
Section 1: SSH connection to the virtual machines.
====================================
'''

'''
This method will connect to the gateways and to the virtual machines through the gateways. 
    Gateway: host server
    virtual machine: hosted in the gateway

    This script is running on monitor1 server
    Current topology: 
                                     |----vm1
                        |---- node1  |
                        |            |----vm2
    monitor1 -------switch1
                        |            |----vm3
                        |---- node2  |
                                     |----vm4
'''


# Method using jumpssh
def connect_to_vms_jumpssh(gateway_credentials=gateway_credentials, vm_credentials=vm_credentials):
    gateway_session = {}
    vm_session = {}
    # 1. Create the ssh connection to the gateways (host servers)
    for i, val in enumerate(gateway_credentials.keys()):
        try:
            gateway_session[val] = SSHSession(host=gateway_credentials[val][0],
                                              username=gateway_credentials[val][1],
                                              password=gateway_credentials[val][2]).open()

        except:
            print('Could not connect to host server: ' + gateway_credentials[val][0])
    print('connected to host servers')
    # 2. Create the ssh connection to the virtual machines (guest servers)
    for i, val in enumerate(vm_credentials.keys()):
        try:
            # vm_credentials[val][3] has the host server ID, the key in the gateway sessions dict.
            vm_session[val] = gateway_session[str(vm_credentials[val][3])].get_remote_session(
                host=vm_credentials[val][0],
                username=vm_credentials[val][1],
                password=vm_credentials[val][2])
        except:
            print('Could not connect to guest vm: ' + vm_credentials[val][0])
    print('connected to guest vms')
    return gateway_session, vm_session

# https://stackoverflow.com/questions/51237956/python-how-do-i-authenticate-ssh-connection-with-fabric-module
# Method using fabric
def connect_to_vms_fabric(gateway_credentials=gateway_credentials, vm_credentials=vm_credentials):
    gateway_session = {}
    vm_session = {}
    # 1. Create the ssh connection to the gateways (host servers)
    for i, val in enumerate(gateway_credentials.keys()):
        try:
            gateway_session[val] = Connection(host=gateway_credentials[val][0],
                                              user=gateway_credentials[val][1],
                                              connect_kwargs={'password': gateway_credentials[val][2]})
        except:
            print('Could not connect to host server: ' + gateway_credentials[val][0])
    print('connected to host servers')
    # 2. Create the ssh connection to the virtual machines (guest servers)
    for i, val in enumerate(vm_credentials.keys()):
        try:
            # vm_credentials[val][3] has the host server ID, the key in the gateway sessions dict.
            vm_session[val] = Connection(
                host=vm_credentials[val][0],
                user=vm_credentials[val][1],
                connect_kwargs={'password': vm_credentials[val][2]},
                gateway=gateway_session[str(vm_credentials[val][3])])
        except:
            print('Could not connect to guest vm: ' + vm_credentials[val][0])
    print('connected to guest vms')
    return gateway_session, vm_session

# Method using parallel ssh
def connect_to_vms_pssh(gateway_credentials=gateway_credentials, vm_credentials=vm_credentials):
    gateway_session = {}
    vm_session = {}
    # 1. Create the ssh connection to the gateways (host servers)
    for i, val in enumerate(gateway_credentials.keys()):
        try:
            gateway_session[val] = \
                pssh.clients.ParallelSSHClient(
                    hosts=[gateway_credentials[val][0]],
                    host_config=[HostConfig(user=gateway_credentials[val][1],
                                            password=gateway_credentials[val][2])])

        except:
            print('Could not connect to host server: ' + gateway_credentials[val][0])
    print('connected to host servers')
    # 2. Create the ssh connection to the virtual machines (guest servers)
    for i, val in enumerate(vm_credentials.keys()):
        try:
            # vm_credentials[val][3] has the host server ID, the key in the gateway sessions dict.
            vm_session[val] = pssh.clients.ParallelSSHClient(
                hosts=[vm_credentials[val][0]],
                host_config=[HostConfig(user=vm_credentials[val][1],
                                        password=vm_credentials[val][2],
                                        proxy_host=gateway_credentials[str(vm_credentials[val][3])][0],
                                        proxy_user=gateway_credentials[str(vm_credentials[val][3])][1],
                                        proxy_password=gateway_credentials[str(vm_credentials[val][3])][2])]
            )
        except:
           print('Could not connect to guest vm: ' + vm_credentials[val][0])
    print('connected to guest vms')
    print('---done---')
    return gateway_session, vm_session


# run iperf client
def iperf_c(vm, t=IPERF_TIME, b=BW_IPERF, ip_s='10.0.0.4'):
    #output = vm.run_command('hostname')
    print('running iperf client')
    #for line in output[0].stdout:
    #    print(line)
    vm.run_command('iperf3 -c ' + ip_s + ' -t ' + str(t) + ' -b ' + str(b))
    print('---done---')
    return None


# run iperf server
def iperf_s(vm):
    #output = vm.run_command('hostname')
    print('running iperf server')
    #for line in output[0].stdout:
    #    print(line)
    vm.run_command('iperf3 -s -1')
    print('---done---')
    return None

# run hostname server
def hostname(vm):
    output = vm.run_command('hostname')
    print('running hostname on: ')
    for line in output[0].stdout:
        print(line)
    print('---done---')
    return None

# run tcpdump
# https://parallel-ssh.readthedocs.io/en/latest/advanced.html?highlight=sudo#run-with-sudo
def tcpdump_vm(vm, endpoints,
               sudo_password=vm_credentials['1'][2],
               test_type='single',
               directory=TCP_TEST_DIRECTORY,
               t=IPERF_TIME+3,
               bw=BW_IPERF,
               vm_nic='enp2s0',
               capture_size=96):
    #output = vm.run_command('hostname')
    print('running tcpdump')
    #for line in output[0].stdout:
    #    print(line)
    # filename structure: 'bandwidth|endpoints|test_type|mm_dd_yyyy-hh-mm-ss.pcap'
    # https://www.programiz.com/python-programming/datetime/strftime

    filename = bw + "\|"+endpoints + "\|" + test_type + "\|"+datetime.datetime.now().strftime("%m_%d_%Y-%H_%M_%S")+'.pcap'
    command='timeout ' + str(t)
    command+= ' tcpdump -i ' + vm_nic
    command+= ' -s '+ str(capture_size)
    command+= ' -w ' + directory
    command+= filename
    print(command)
    #out = vm.run_command(command)
    vm.run_command(command)
    print('---done---')
    return None

'''
===========================================
Section 2: HTTP requests to the OFCTL_REST.py app of the Ryu controller 
on controller1 server
===========================================
'''
# this method helps to create the payload required to add a flow.
def ofctl_flow_payload(dpid, action,
                       in_port, out_port,
                       ip_src, ip_dst, priority=10):
    if action == 'ADD':
        type_str_begin = '"instructions": [{"type": "APPLY_ACTIONS",'
        type_str_end = '}] '
        output_match = ''
    elif action == 'DELETE':
        type_str_begin = ''
        type_str_end = ''
        output_match = '"out_port": ' + str(out_port) + ','  # this field is not a valid match field, so should remove.

    payload = '{"dpid":' + str(dpid) + ',\
                "table_id": 0,\
                "priority": ' + str(priority) + ',\
                "match":{\
                    "in_port":' + str(in_port) + ',' \
              + output_match + \
              '"dl_type":0x0800,\
              "nw_src":"' + ip_src + '",\
                    "nw_dst":"' + ip_dst + '" \
                },' + type_str_begin + '\
                        "actions": [\
                            {\
                                "port": ' + str(out_port) + ',\
                                "type": "OUTPUT"\
                            }\
                        ]' \
              + type_str_end + \
              '}'

    # r = requests.post(url=OFCTL_REST_IP+ADD_FLOW_URI, data=payload)
    return payload


# TEMPORARY METHOD TO ADD THE FLOWS FOR VM1 TO VM4 through TRUNK1 (higher priority) and TRUNK2 (lower priority),
def add_flows_vm1_vm4():
    # Add flows for bridge 0:
    # Trunk1:
    flow1_payload = ofctl_flow_payload(action='ADD', dpid=DPID_BR1, in_port=1, out_port=5, ip_src='10.0.0.1',
                                       ip_dst='10.0.0.4', priority=10)
    flow2_payload = ofctl_flow_payload(action='ADD', dpid=DPID_BR1, in_port=5, out_port=1, ip_src='10.0.0.4',
                                       ip_dst='10.0.0.1', priority=10)
    # Trunk2:
    flow3_payload = ofctl_flow_payload(action='ADD', dpid=DPID_BR1, in_port=1, out_port=7, ip_src='10.0.0.1',
                                       ip_dst='10.0.0.4', priority=5)
    flow4_payload = ofctl_flow_payload(action='ADD', dpid=DPID_BR1, in_port=7, out_port=1, ip_src='10.0.0.4',
                                       ip_dst='10.0.0.1', priority=5)

    # Add flows for bridge 1:
    # Trunk1:
    flow5_payload = ofctl_flow_payload(action='ADD', dpid=DPID_BR4, in_port=6, out_port=4, ip_src='10.0.0.1',
                                       ip_dst='10.0.0.4', priority=10)
    flow6_payload = ofctl_flow_payload(action='ADD', dpid=DPID_BR4, in_port=4, out_port=6, ip_src='10.0.0.4',
                                       ip_dst='10.0.0.1', priority=10)
    # Trunk2:
    flow7_payload = ofctl_flow_payload(action='ADD', dpid=DPID_BR4, in_port=8, out_port=4, ip_src='10.0.0.1',
                                       ip_dst='10.0.0.4', priority=5)
    flow8_payload = ofctl_flow_payload(action='ADD', dpid=DPID_BR4, in_port=4, out_port=8, ip_src='10.0.0.4',
                                       ip_dst='10.0.0.1', priority=5)
    # Now add all the flows
    r = requests.post(url=OFCTL_REST_IP + ADD_FLOW_URI, data=flow1_payload)
    r = requests.post(url=OFCTL_REST_IP + ADD_FLOW_URI, data=flow2_payload)
    r = requests.post(url=OFCTL_REST_IP + ADD_FLOW_URI, data=flow3_payload)
    r = requests.post(url=OFCTL_REST_IP + ADD_FLOW_URI, data=flow4_payload)
    r = requests.post(url=OFCTL_REST_IP + ADD_FLOW_URI, data=flow5_payload)
    r = requests.post(url=OFCTL_REST_IP + ADD_FLOW_URI, data=flow6_payload)
    r = requests.post(url=OFCTL_REST_IP + ADD_FLOW_URI, data=flow7_payload)
    r = requests.post(url=OFCTL_REST_IP + ADD_FLOW_URI, data=flow8_payload)
    print('adding flows')
    return None

# TEMPORARY METHOD TO ADD THE FLOWS FOR VM1 TO VM4 through TRUNK1 (higher priority) and TRUNK2 (lower priority),
def add_flows_vm1_vm4_v2():
    # Trunk1:
    add_flows_trunk1(priority=10)
    add_flows_trunk1(priority=5)
    # Trunk2:
    add_flows_trunk2(priority=7)
    print('adding flows v2')
    return 0

# delete flows that match certain conditions.

# clear flows per bridge
def del_all_flows(dpid):
    r = requests.delete(url=OFCTL_REST_IP + CLEAR_FLOWS_URI + str(dpid))
    return None

# TEMPORARY METHOD TO DELETE THE FLOWS FOR VM1 TO VM4 BETWEEN TRUNK1
# must use delete_strict URI to consider deleting flows matching priority.
def del_flows_trunk1(priority=10):
    flow1_payload = ofctl_flow_payload(dpid=DPID_BR1, in_port=1, out_port=5, ip_src='10.0.0.1', ip_dst='10.0.0.4',
                                       action='DELETE', priority=priority)
    flow2_payload = ofctl_flow_payload(dpid=DPID_BR1, in_port=5, out_port=1, ip_src='10.0.0.4', ip_dst='10.0.0.1',
                                       action='DELETE', priority=priority)
    flow3_payload = ofctl_flow_payload(dpid=DPID_BR4, in_port=6, out_port=4, ip_src='10.0.0.1', ip_dst='10.0.0.4',
                                       action='DELETE', priority=priority)
    flow4_payload = ofctl_flow_payload(dpid=DPID_BR4, in_port=4, out_port=6, ip_src='10.0.0.4', ip_dst='10.0.0.1',
                                       action='DELETE', priority=priority)

    r = requests.post(url=OFCTL_REST_IP + DELETE_FLOWS_URI, data=flow1_payload)
    r = requests.post(url=OFCTL_REST_IP + DELETE_FLOWS_URI, data=flow2_payload)
    r = requests.post(url=OFCTL_REST_IP + DELETE_FLOWS_URI, data=flow3_payload)
    r = requests.post(url=OFCTL_REST_IP + DELETE_FLOWS_URI, data=flow4_payload)
    print('removing flows trunk1  with priority ' + str(priority))
    return


# TEMPORARY METHOD TO DELETE THE FLOWS FOR VM1 TO VM4 BETWEEN TRUNK2
# must use delete_strict URI to consider deleting flows matching priority.
def del_flows_trunk2(priority=7):
    flow1_payload = ofctl_flow_payload(dpid=DPID_BR1, in_port=1, out_port=7, ip_src='10.0.0.1', ip_dst='10.0.0.4',
                                       action='DELETE', priority=priority)
    flow2_payload = ofctl_flow_payload(dpid=DPID_BR1, in_port=7, out_port=1, ip_src='10.0.0.4', ip_dst='10.0.0.1',
                                       action='DELETE', priority=priority)
    flow3_payload = ofctl_flow_payload(dpid=DPID_BR4, in_port=8, out_port=4, ip_src='10.0.0.1', ip_dst='10.0.0.4',
                                       action='DELETE', priority=priority)
    flow4_payload = ofctl_flow_payload(dpid=DPID_BR4, in_port=4, out_port=8, ip_src='10.0.0.4', ip_dst='10.0.0.1',
                                       action='DELETE', priority=priority)

    r = requests.post(url=OFCTL_REST_IP + DELETE_FLOWS_URI, data=flow1_payload)
    r = requests.post(url=OFCTL_REST_IP + DELETE_FLOWS_URI, data=flow2_payload)
    r = requests.post(url=OFCTL_REST_IP + DELETE_FLOWS_URI, data=flow3_payload)
    r = requests.post(url=OFCTL_REST_IP + DELETE_FLOWS_URI, data=flow4_payload)
    print('removing flows trunk2 with priority ' + str(priority))
    return

# TEMPORARY METHOD TO ADD THE FLOWS FOR VM1 TO VM4 BETWEEN TRUNK1 ONLY
# must use delete_strict URI to consider deleting flows matching priority.
def add_flows_trunk1(priority=3):
    # Add flows for bridge 0:
    # Trunk1:
    flow1_payload = ofctl_flow_payload(action='ADD', dpid=DPID_BR1, in_port=1, out_port=5, ip_src='10.0.0.1',
                                       ip_dst='10.0.0.4', priority=priority)
    flow2_payload = ofctl_flow_payload(action='ADD', dpid=DPID_BR1, in_port=5, out_port=1, ip_src='10.0.0.4',
                                       ip_dst='10.0.0.1', priority=priority)

    # Add flows for bridge 1:
    # Trunk1:
    flow5_payload = ofctl_flow_payload(action='ADD', dpid=DPID_BR4, in_port=6, out_port=4, ip_src='10.0.0.1',
                                       ip_dst='10.0.0.4', priority=priority)
    flow6_payload = ofctl_flow_payload(action='ADD', dpid=DPID_BR4, in_port=4, out_port=6, ip_src='10.0.0.4',
                                       ip_dst='10.0.0.1', priority=priority)

    # Now add all the flows
    r = requests.post(url=OFCTL_REST_IP + ADD_FLOW_URI, data=flow1_payload)
    r = requests.post(url=OFCTL_REST_IP + ADD_FLOW_URI, data=flow2_payload)

    r = requests.post(url=OFCTL_REST_IP + ADD_FLOW_URI, data=flow5_payload)
    r = requests.post(url=OFCTL_REST_IP + ADD_FLOW_URI, data=flow6_payload)

    print('adding flows')
    return None

def add_flows_trunk2(priority=5):
    # Add flows for bridge 0:
    # Trunk1:
    flow1_payload = ofctl_flow_payload(action='ADD', dpid=DPID_BR1, in_port=1, out_port=7, ip_src='10.0.0.1',
                                       ip_dst='10.0.0.4', priority=priority)
    flow2_payload = ofctl_flow_payload(action='ADD', dpid=DPID_BR1, in_port=7, out_port=1, ip_src='10.0.0.4',
                                       ip_dst='10.0.0.1', priority=priority)

    # Add flows for bridge 1:
    # Trunk1:
    flow5_payload = ofctl_flow_payload(action='ADD', dpid=DPID_BR4, in_port=8, out_port=4, ip_src='10.0.0.1',
                                       ip_dst='10.0.0.4', priority=priority)
    flow6_payload = ofctl_flow_payload(action='ADD', dpid=DPID_BR4, in_port=4, out_port=8, ip_src='10.0.0.4',
                                       ip_dst='10.0.0.1', priority=priority)

    # Now add all the flows
    r = requests.post(url=OFCTL_REST_IP + ADD_FLOW_URI, data=flow1_payload)
    r = requests.post(url=OFCTL_REST_IP + ADD_FLOW_URI, data=flow2_payload)

    r = requests.post(url=OFCTL_REST_IP + ADD_FLOW_URI, data=flow5_payload)
    r = requests.post(url=OFCTL_REST_IP + ADD_FLOW_URI, data=flow6_payload)

    print('adding flows trunk 2 with priority ' + str(priority))
    return None

def edit_bidirectional_flows(dpid,in_port,out_port,ip_src,ip_dst,action='ADD',priority=1):
    forward_flow_payload = ofctl_flow_payload(action=action, dpid=dpid,
                                              in_port=in_port, out_port=out_port,
                                              ip_src=ip_src,ip_dst=ip_dst, priority=priority)

    reverse_flow_payload = ofctl_flow_payload(action=action, dpid=dpid,
                                              in_port=out_port, out_port=in_port,
                                              ip_src=ip_dst, ip_dst=ip_src, priority=priority)

    # Now add all the flows
    if action == 'ADD':
        URI = ADD_FLOW_URI
    else:
        URI = DELETE_FLOWS_URI
    r = requests.post(url=OFCTL_REST_IP + URI, data=forward_flow_payload)
    r = requests.post(url=OFCTL_REST_IP + URI, data=reverse_flow_payload)
    print(str(action)+' flows on bridge '+str(dpid) + " for ips@ports "
          + str(ip_src)+'@'+ str(in_port) + ', '
          + str(ip_dst)+'@'+ str(out_port)
          + ' with priority ' + str(priority))
    return None

def edit_flows_vm1_vm4_short_path(action='ADD',priority=9):
    # edit flows for bridge 1:
    edit_bidirectional_flows(action=action, dpid=DPID_BR1, in_port=1, out_port=5,
                             ip_src='10.0.0.1', ip_dst='10.0.0.4', priority=priority)
    # edit flows for bridge 4:
    edit_bidirectional_flows(action=action, dpid=DPID_BR4, in_port=6, out_port=4,
                             ip_src='10.0.0.1', ip_dst='10.0.0.4', priority=priority)
    return None

def edit_flows_vm2_vm3_long_path(action='ADD',priority=8):
    # edit flows for bridge 2:
    edit_bidirectional_flows(action=action, dpid=DPID_BR2, in_port=2, out_port=22,
                             ip_src='10.0.0.2', ip_dst='10.0.0.3', priority=priority)
    # edit flows for bridge 3:
    edit_bidirectional_flows(action=action, dpid=DPID_BR3, in_port=23, out_port=3,
                             ip_src='10.0.0.2', ip_dst='10.0.0.3', priority=priority)
    # edit flows for bridge 1:
    edit_bidirectional_flows(action=action, dpid=DPID_BR1, in_port=21, out_port=5,
                             ip_src='10.0.0.2', ip_dst='10.0.0.3', priority=priority)
    # edit flows for bridge 4:
    edit_bidirectional_flows(action=action, dpid=DPID_BR4, in_port=6, out_port=24,
                             ip_src='10.0.0.2', ip_dst='10.0.0.3', priority=priority)

    return None

def edit_flows_vm2_vm3_long_path_backup(action='ADD',priority=10):
    # edit flows for bridge 2:
    edit_bidirectional_flows(action=action, dpid=DPID_BR2, in_port=2, out_port=10,
                             ip_src='10.0.0.2', ip_dst='10.0.0.3', priority=priority)
    # edit flows for bridge 3:
    edit_bidirectional_flows(action=action, dpid=DPID_BR3, in_port=12, out_port=3,
                             ip_src='10.0.0.2', ip_dst='10.0.0.3', priority=priority)
    # edit flows for bridge 1:
    edit_bidirectional_flows(action=action, dpid=DPID_BR1, in_port=9, out_port=5,
                             ip_src='10.0.0.2', ip_dst='10.0.0.3', priority=priority)
    # edit flows for bridge 4:
    edit_bidirectional_flows(action=action, dpid=DPID_BR4, in_port=6, out_port=11,
                             ip_src='10.0.0.2', ip_dst='10.0.0.3', priority=priority)
    return None

def edit_flows_vm2_vm3_short_path(action='ADD', priority=6):
    # Add flows for bridge 2:
    edit_bidirectional_flows(action=action, dpid=DPID_BR2, in_port=2, out_port=7,
                             ip_src='10.0.0.2', ip_dst='10.0.0.3', priority=priority)
    # Add flows for bridge 3:
    edit_bidirectional_flows(action=action, dpid=DPID_BR3, in_port=8, out_port=3,
                             ip_src='10.0.0.2', ip_dst='10.0.0.3', priority=priority)
    return None

'''
**********************************************
Methods for opening a TCP socket and send commands to the optical switch. 
Protocol: SCPI
**********************************************
'''

#Open TCP socket
def ots_connect_tcp_socket(ip, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((ip, port))
    return s

#https://stackoverflow.com/questions/63214198/when-creating-bytes-with-b-prefix-before-string-what-encoding-does-python-use
def ots_connect_port(s, port_in, port_out):
    port_in_str = ','.join(str(i) for i in port_in)
    port_out_str = ','.join(str(i) for i in port_out)
    cmd = ':oxc:swit:conn:only (@{0}),(@{1}); stat?\r\n'.format(port_in_str, port_out_str)
    cmd = bytes(cmd, 'utf-8')
    s.sendall(cmd)
    #reply = s.recv(4096) #Reading from recv adds to the total execution time
    #return reply
    return None

def ots_disconnect_all(s):
    cmd=b':oxc:swit:disc:all\r\n'
    s.sendall(cmd)
    return None

