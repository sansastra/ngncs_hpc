'''
Script to connect to the virtual machines through the gateways node1 and node2
jumpssh: blocking
https://pypi.org/project/jumpssh/

fabric: non blocking
https://www.fabfile.org/index.html

William Orozco
worozco@ucdavis.edu
December 2021
'''


'''
====================================
import libraries
====================================
'''
import json
import multiprocessing
import threading  # threading does not work
import requests
from fabric import Connection  # this library is non blocking but uses threading
from jumpssh import SSHSession  # this library is blocking
from pssh.config import HostConfig
from pssh.clients import ParallelSSHClient
import pssh.clients
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

IPERF_TIME = 60
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

#Method using jumpssh
def connect_to_vms_jumpssh(gateway_credentials = gateway_credentials, vm_credentials = vm_credentials):
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


def close_all_ssh(vms, gws):
    # close vms first
    for vm in vms:
        vm.close()
    print('closing ssh vm')
    # then close gws
    for gw in gws:
        gw.close()
    print('closing ssh gateways')
    return None

# https://stackoverflow.com/questions/51237956/python-how-do-i-authenticate-ssh-connection-with-fabric-module
# Method using fabric
def connect_to_vms_fabric(gateway_credentials = gateway_credentials, vm_credentials = vm_credentials):
    gateway_session = {}
    vm_session = {}
    # 1. Create the ssh connection to the gateways (host servers)
    for i, val in enumerate(gateway_credentials.keys()):
        try:
            gateway_session[val] = Connection(host=gateway_credentials[val][0],
                                              user=gateway_credentials[val][1],
                                              connect_kwargs={'password':gateway_credentials[val][2]})
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

def connect_to_vms_pssh(gateway_credentials = gateway_credentials, vm_credentials = vm_credentials):
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
        #try:
            # vm_credentials[val][3] has the host server ID, the key in the gateway sessions dict.
        vm_session[val] = pssh.clients.ParallelSSHClient(
                hosts=[vm_credentials[val][0]],
                host_config=[HostConfig(user=vm_credentials[val][1],
                                        password=vm_credentials[val][2],
                                        proxy_host=gateway_credentials[str(vm_credentials[val][3])][0],
                                        proxy_user=gateway_credentials[str(vm_credentials[val][3])][1],
                                        proxy_password=gateway_credentials[str(vm_credentials[val][3])][2])]
            )
        '''
                pssh.clients.ParallelSSHClient(
                    hosts=[vm_credentials[val][0]],
                    host_config=[user=vm_credentials[val][1],
                                 password =vm_credentials[val][2],
                                 proxy_host=gateway_credentials[str(vm_credentials[val][3])][0]])
                                 '''
        #except:
        #    print('Could not connect to guest vm: ' + vm_credentials[val][0])
    print('connected to guest vms')
    return gateway_session, vm_session

# gws, vms = connect_to_vms_jumpssh()

# print(vms[4].get_cmd_output('iperf3 -s'))
# print(vms[1].get_cmd_output('iperf3 -c 10.0.0.4 -t 60'))

# run iperf client
def iperf_c(vm, t=60, ip_s='10.0.0.4'):
    print('running iperf client')
    #print(vm.run_cmd('iperf3 -c ' + ip_s + ' -t ' + str(t)))
    #print(vm.run('iperf3 -c ' + ip_s + ' -t ' + str(t)))
    vm.run_command('iperf3 -c ' + ip_s + ' -t ' + str(t))
    print('finishing iperf client')
    return None


# run iperf server

def iperf_s(vm):
    print('running iperf server')
    #print(vm.run_cmd('iperf3 -s -1'))
    #print(vm.run('iperf3 -s -1'))
    vm.run_command('iperf3 -s -1')
    print('finishing iperf server')
    return None


'''
print('\n====\nconnected to :\n ====\n virtual machines\n' )
for i, val in enumerate(vms.keys()):
    print(vms[val].get_cmd_output('hostname'))
    vms[val].close()

print('\n====\nconnected to :\n ====\ngateways\n' )
for i, val in enumerate(gws.keys()):
    print(gws[val].get_cmd_output('hostname'))
    gws[val].close()
'''

'''
===========================================
Section 2: HTTP requests to the OFCTL_REST.py app of the Ryu controller 
on 10.0.200.2 (controller1 server)
===========================================
'''


# this method will help to create the payload required to add a flow.

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
    flow1_payload = ofctl_flow_payload(action='ADD', dpid=DPID_BR0, in_port=1, out_port=5, ip_src='10.0.0.1',
                                       ip_dst='10.0.0.4', priority=10)
    flow2_payload = ofctl_flow_payload(action='ADD', dpid=DPID_BR0, in_port=5, out_port=1, ip_src='10.0.0.4',
                                       ip_dst='10.0.0.1', priority=10)
    # Trunk2:
    flow3_payload = ofctl_flow_payload(action='ADD', dpid=DPID_BR0, in_port=1, out_port=7, ip_src='10.0.0.1',
                                       ip_dst='10.0.0.4', priority=5)
    flow4_payload = ofctl_flow_payload(action='ADD', dpid=DPID_BR0, in_port=7, out_port=1, ip_src='10.0.0.4',
                                       ip_dst='10.0.0.1', priority=5)

    # Add flows for bridge 1:
    # Trunk1:
    flow5_payload = ofctl_flow_payload(action='ADD', dpid=DPID_BR1, in_port=6, out_port=4, ip_src='10.0.0.1',
                                       ip_dst='10.0.0.4', priority=10)
    flow6_payload = ofctl_flow_payload(action='ADD', dpid=DPID_BR1, in_port=4, out_port=6, ip_src='10.0.0.4',
                                       ip_dst='10.0.0.1', priority=10)
    # Trunk2:
    flow7_payload = ofctl_flow_payload(action='ADD', dpid=DPID_BR1, in_port=8, out_port=4, ip_src='10.0.0.1',
                                       ip_dst='10.0.0.4', priority=5)
    flow8_payload = ofctl_flow_payload(action='ADD', dpid=DPID_BR1, in_port=4, out_port=8, ip_src='10.0.0.4',
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


# delete flows that match certain conditions.

# clear flows per bridge
def del_all_flows(dpid):
    r = requests.delete(url=OFCTL_REST_IP + CLEAR_FLOWS_URI + str(dpid))
    return None


# TEMPORARY METHOD TO DELETE THE FLOWS FOR VM1 TO VM4 BETWEEN TRUNK1
# must use delete_strict URI to consider deleting flows matching priority.
def del_flows_trunk1():
    flow1_payload = ofctl_flow_payload(dpid=DPID_BR0, in_port=1, out_port=5, ip_src='10.0.0.1', ip_dst='10.0.0.4',
                                       action='DELETE')
    flow2_payload = ofctl_flow_payload(dpid=DPID_BR0, in_port=5, out_port=1, ip_src='10.0.0.4', ip_dst='10.0.0.1',
                                       action='DELETE')
    flow3_payload = ofctl_flow_payload(dpid=DPID_BR1, in_port=6, out_port=4, ip_src='10.0.0.1', ip_dst='10.0.0.4',
                                       action='DELETE')
    flow4_payload = ofctl_flow_payload(dpid=DPID_BR1, in_port=4, out_port=6, ip_src='10.0.0.4', ip_dst='10.0.0.1',
                                       action='DELETE')

    r = requests.post(url=OFCTL_REST_IP + DELETE_FLOWS_URI, data=flow1_payload)
    r = requests.post(url=OFCTL_REST_IP + DELETE_FLOWS_URI, data=flow2_payload)
    r = requests.post(url=OFCTL_REST_IP + DELETE_FLOWS_URI, data=flow3_payload)
    r = requests.post(url=OFCTL_REST_IP + DELETE_FLOWS_URI, data=flow4_payload)
    print('removing flows trunk1')
    return None


# add_flows_vm1_vm4()

# del_flows_trunk1()

# Connect to gateways and virtual machines
gws, vms = connect_to_vms_pssh()
#gws, vms = connect_to_vms_fabric()
#print(vms.keys())
'''
Threading section
'''


# Initialize flows
add_flows_vm1_vm4()

thread_instance = []
# Reconfigure from trunk1 to trunk2
reconfigure = threading.Timer(20, del_flows_trunk1)
reconfigure.start()
thread_instance.append(reconfigure)

# Return traffic to trunk1
return_traffic = threading.Timer(50, add_flows_vm1_vm4)
return_traffic.start()
thread_instance.append(return_traffic)

#run iperf
iperf_s(vms['4'])
iperf_c(vms['1'])
#iperf_server = threading.Timer(0,iperf_s(vms['4']))
#iperf_server.start()
#iperf_client = threading.Timer(0,iperf_c(vms['1']))
#iperf_client.start()

#iperf_server = multiprocessing.Process(target=iperf_s(vms['4']))
#iperf_server.start()
#iperf_client=multiprocessing.Process(target=iperf_c(vms['1']))
#iperf_client.start()

#iperf_server.join()
#iperf_client.join()

# close all sessions
#close_ssh = threading.Timer(61, close_all_ssh(vms, gws))
#close_ssh.start()

for thread in thread_instance:
    thread.join()
