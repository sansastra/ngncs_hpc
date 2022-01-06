'''
Script to connect to the virtual machines through the gateways node1 and node2
https://pypi.org/project/jumpssh/

William Orozco
worozco@ucdavis.edu
December 2021
'''

'''
====================================
import libraries
====================================
'''
from jumpssh import SSHSession
import requests
import json

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


def connect_to_vms(gw_cred=gateway_credentials, vm_cred=vm_credentials):
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

    # 2. Create the ssh connection to the virtual machines (guest servers)
    for i, val in enumerate(vm_credentials.keys()):
        try:
            # vm_credentials[val][3] has the host server ID, the key in the gateway sessions dict.
            vm_session[val] = gateway_session[vm_credentials[val][3]].get_remote_session(
                host=vm_credentials[val][0],
                username=vm_credentials[val][1],
                password=vm_credentials[val][2])
        except:
            print('Could not connect to guest vm: ' + vm_credentials[val][0])

    return gateway_session, vm_session


# gws, vms = connect_to_vms()

# print(vms[4].get_cmd_output('iperf3 -s'))
# print(vms[1].get_cmd_output('iperf3 -c 10.0.0.4 -t 60'))


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
    return None


# import time
# start = time.time()

add_flows_vm1_vm4()

# end = time.time()
# print(end - start)

# del_flows_trunk1()
