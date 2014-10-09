#!/usr/bin/env python
# coding=utf-8
# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

"""
Will test the OS occiosapi against a local running instance.
"""

#pylint: disable=W0102,C0103,R0904

import base64
import json
import sys
import time
import httplib
import logging
import unittest
import random


HEADS = {'Content-Type': 'text/occi',
         'Accept': 'text/occi'}

KEYSTONE_HOST = '127.0.0.1:5000'
OCCI_HOST = '127.0.0.1:8787'

OS_TPL_TITLE = '"Image: cirros-0.3.1-x86_64-uec"'
OS_TPL_SCHEMA = 'scheme="http://schemas.openstack.org/template/os#"'
RES_TPL_SCHEMA = 'scheme="http://schemas.openstack.org/template/resource#"'
RES_TPL_NANO = ' '.join(['m1-nano;', RES_TPL_SCHEMA])
RES_TPL_MICRO = ' '.join(['m1-micro;', RES_TPL_SCHEMA])

# Init a simple logger...
logging.basicConfig(level=logging.DEBUG)
CONSOLE = logging.StreamHandler()
CONSOLE.setLevel(logging.DEBUG)
LOG = logging.getLogger()
LOG.addHandler(CONSOLE)


def do_request(verb, url, headers):
    """
    Do an HTTP request defined by a HTTP verb, an URN and a dict of headers.
    """
    try:
        conn = httplib.HTTPConnection(OCCI_HOST, timeout=100)
        conn.request(verb, url, None, headers)
        response = conn.getresponse()
        if response.status not in [200, 201]:
            LOG.error(response.reason)
            LOG.debug("Request: %s\n%s\n%s\n" % (verb, url, headers))
            LOG.warn(response.read())
            sys.exit(1)

        heads = response.getheaders()
        result = {}
        for item in heads:
            if item[0] in ['category', 'link', 'x-occi-attribute',
                           'x-occi-location', 'location']:
                tmp = []
                for val in item[1].split(','):
                    tmp.append(val.strip())
                result[item[0]] = tmp

        conn.close()
        return result
    except httplib.HTTPException as e:
        LOG.error(e)
        LOG.debug("Request: %s\n%s\n%s\n" % (verb, url, headers))
        sys.exit(1)


def get_os_token(username, password):
    """
    Get a security token from Keystone.
    """
    # TODO: switch dot demo account
    body = '{"auth": {"tenantName": "' + 'demo' + '", ' \
           '"passwordCredentials":{"username": "' + username + '", ' \
           '"password": "' + password + '"}}}'

    heads = {'Content-Type': 'application/json'}
    conn = httplib.HTTPConnection(KEYSTONE_HOST)
    conn.request("POST", "/v2.0/tokens", body, heads)
    response = conn.getresponse()
    data = response.read()
    tokens = json.loads(data)
    token = tokens['access']['token']['id']
    return token


def get_qi_listing(token):
    """
    Retrieve categories from QI.
    """
    heads = HEADS.copy()
    heads['X-Auth-Token'] = token
    result = do_request('GET', '/-/', heads)
    return result


def get_os_tpl(token):
    """
    Get the os_template to use for creating VMs
    """
    qis = get_qi_listing(token)
    for qi in [q.split(';') for q in qis['category']]:
        if qi[1].strip() == OS_TPL_SCHEMA:
            if qi[3].split('=')[-1] == OS_TPL_TITLE:
                return ";".join((qi[0], qi[1]))
    return None


def create_node(token, category_list, attributes=[]):
    """
    Create a VM.
    """
    heads = HEADS.copy()
    heads['X-Auth-Token'] = token

    for cat in category_list:
        if 'Category' in heads:
            heads['Category'] += ', ' + cat
        else:
            heads['Category'] = cat

    for attr in attributes:
        if 'X-OCCI-Attribute' in heads:
            heads['X-OCCI-Attribute'] += ', ' + attr
        else:
            heads['X-OCCI-Attribute'] = attr

    heads = do_request('POST', '/compute/', heads)
    loc = heads['location'][0]
    loc = loc[len('http://' + OCCI_HOST):]
    LOG.debug('Location is: ' + loc)
    return loc


def list_nodes(token, url):
    """
    List a bunch of resource.
    """
    heads = HEADS.copy()
    heads['X-Auth-Token'] = token
    heads = do_request('GET', url, heads)
    return heads['x-occi-location']


def get_node(token, location):
    """
    Retrieve a single resource.
    """
    heads = HEADS.copy()
    heads['X-Auth-Token'] = token
    heads = do_request('GET', location, heads)
    return heads


def destroy_node(token, location):
    """
    Destroy a single node.
    """
    heads = HEADS.copy()
    heads['X-Auth-Token'] = token
    heads = do_request('DELETE', location, heads)
    return heads


def trigger_action(token, url, action_cat, action_param=None):
    """
    Trigger an OCCI action.
    """
    heads = HEADS.copy()
    heads['X-Auth-Token'] = token
    heads['Category'] = action_cat
    if action_param is not None:
        heads['X-OCCI-Attribute'] = action_param

    do_request('POST', url, heads)


class SystemTest(unittest.TestCase):
    """
    Do a simple set of test.
    """

    def setUp(self):
        """
        Setup the test.
        """
        # Get a security token:
        self.token = get_os_token('admin', 'os4all')
        #LOG.info('security token is: ' + self.token)
        # get the VM category to use
        self.os_tpl = get_os_tpl(self.token)
        #LOG.info('OS tpl is: ' + self.os_tpl)

    def test_compute_node(self):
        """
        Test ops on a compute node!
        """
        # QI listing
        LOG.debug(get_qi_listing(self.token)['category'])

        # create VM
        cats = [RES_TPL_NANO,
                self.os_tpl,
                'compute; scheme="http://schemas.ogf'
                '.org/occi/infrastructure#"']
        vm_location = create_node(self.token, cats)
        # list computes
        if 'http://' + OCCI_HOST + vm_location not \
                in list_nodes(self.token, '/compute/'):
            LOG.error('VM should be listed!')

        # wait
        cont = False
        while not cont:
            if 'occi.compute.state="active"' in \
                    get_node(self.token, vm_location)['x-occi-attribute']:
                cont = True
            else:
                time.sleep(5)

        # trigger stop
        trigger_action(self.token, vm_location + '?action=stop',
                       'stop; scheme="http://schemas.ogf.org/occi/'
                       'infrastructure/compute/action#"')

        # wait
        cont = False
        while not cont:
            if 'occi.compute.state="inactive"' in \
                    get_node(self.token, vm_location)['x-occi-attribute']:
                cont = True
            else:
                time.sleep(5)

        # trigger start
        trigger_action(self.token, vm_location + '?action=start',
                       'start; scheme="http://schemas.ogf.org/occi/'
                       'infrastructure/compute/action#"')

        # wait
        cont = False
        while not cont:
            if 'occi.compute.state="active"' in \
                    get_node(self.token, vm_location)['x-occi-attribute']:
                cont = True
            else:
                time.sleep(5)

        # trigger suspend
        trigger_action(self.token, vm_location + '?action=suspend',
                       'suspend; scheme="http://schemas.ogf.org/occi/'
                       'infrastructure/compute/action#"')

        # wait
        cont = False
        while not cont:
            if 'occi.compute.state="inactive"' in \
                    get_node(self.token, vm_location)['x-occi-attribute']:
                cont = True
            else:
                time.sleep(5)

        # trigger start
        trigger_action(self.token, vm_location + '?action=start',
                       'start; scheme="http://schemas.ogf.org/occi/'
                       'infrastructure/compute/action#"')

        # wait
        cont = False
        while not cont:
            if 'occi.compute.state="active"' in \
                    get_node(self.token, vm_location)['x-occi-attribute']:
                cont = True
            else:
                time.sleep(5)

        # delete
        destroy_node(self.token, vm_location)

    def test_security_grouping(self):
        """
        Test some security and accessibility stuff!
        """
        # create sec group
        heads = HEADS.copy()
        heads['X-Auth-Token'] = self.token
        name = 'my_grp' + str(random.randint(1, 999999))
        heads['Category'] = name + '; scheme="http://www.mystuff.org/sec#"; ' \
                                   'rel="http://schemas.ogf.org/occi/' \
                                   'infrastructure/security#group"; ' \
                                   'location="/mygroups/"'
        do_request('POST', '/-/', heads)

        # create sec rule
        cats = [name + '; scheme="http://www.mystuff.org/sec#";',
                'rule; scheme="http://schemas.openstack'
                '.org/occi/infrastructure/network/security#";']
        attrs = ['occi.network.security.protocol="tcp"',
                 'occi.network.security.to="22"',
                 'occi.network.security.from="22"',
                 'occi.network.security.range="0.0.0.0/0"']
        sec_rule_loc = create_node(self.token, cats, attrs)

        # list
        LOG.error(list_nodes(self.token, '/mygroups/'))
        LOG.debug(do_request('GET', sec_rule_loc, heads))

        # FIXME: add VM to sec group - see #22
        #heads['X-OCCI-Location'] = vm_location
        #print do_request('POST', '/mygroups/', heads)

        # create new VM
        cats = [RES_TPL_NANO,
                self.os_tpl,
                name + '; scheme="http://www.mystuff.org/sec#"',
                'compute; scheme="http://schemas.ogf'
                '.org/occi/infrastructure#"']
        vm_location = create_node(self.token, cats)

        # wait
        cont = False
        while not cont:
            if 'occi.compute.state="active"' in \
                    get_node(self.token, vm_location)['x-occi-attribute']:
                cont = True
            else:
                time.sleep(5)

        # allocate floating IP
        cats = ['networkinterface; scheme="http://schemas.ogf'
                '.org/occi/infrastructure#"', 'ipnetworkinterface; '
                                              'scheme="http://schemas.ogf'
                '.org/occi/infrastructure/networkinterface#"']
        attrs = ['occi.core.source=http://"' + OCCI_HOST + vm_location + '"',
                 'occi.core.target=http://"' + OCCI_HOST +
                 '/network/public"']
        float_ip_location = create_node(self.token, cats, attrs)

        time.sleep(15)

        # Deallocate Floating IP to VM
        destroy_node(self.token, float_ip_location)

        # change pw
        # XXX: currently not working as OS libvirt driver does not support it.
        #LOG.debug(trigger_action(self.token, vm_location + '?action=chg_pwd',
        #                         'chg_pwd; scheme="http://schemas.'
        #                         'openstack.org/instance/action#"',
        #                         'org.openstack.credentials.admin_pwd'
        #                         '="new_pass"'))

        # clean VM
        destroy_node(self.token, vm_location)

        # delete rule
        destroy_node(self.token, sec_rule_loc)

        time.sleep(5)

        # FIXME: delete sec group - see #18
        heads = HEADS.copy()
        heads['X-Auth-Token'] = self.token
        heads['Category'] = name + '; scheme="http://www.mystuff.org/sec#"'
        do_request('DELETE', '/-/', heads)

    def test_storage_stuff(self):
        """
        Test attaching and detaching storage volumes + snapshotting etc.
        """

        # create new VM
        cats = [RES_TPL_NANO,
                self.os_tpl,
                'compute; scheme="http://schemas.ogf.org/occi/'
                'infrastructure#"']
        vm_location = create_node(self.token, cats)

        # create volume
        cats = ['storage; scheme="http://schemas.ogf'
                '.org/occi/infrastructure#"']
        attrs = ['occi.storage.size = 1.0', 'occi.core.title = foobar']
        vol_location = create_node(self.token, cats, attrs)

        time.sleep(25)

        # get individual node.
        LOG.debug(get_node(self.token, vol_location)['x-occi-attribute'])

        # snapshot volume
        # snapshot will work - but than deletion of volume is impossible :-/
        #trigger_action(self.token, vol_location +
        #                           '?action=snapshot',
        #    'snapshot; scheme="http://schemas.ogf'
        #    '.org/occi/infrastructure/storage/action#"')

        # link volume and compute
        cats = ['storagelink; scheme="http://schemas.ogf'
                '.org/occi/infrastructure#"']
        attrs = ['occi.core.source=http://"' + OCCI_HOST + vm_location + '"',
                 'occi.core.target=http://"' + OCCI_HOST + vol_location + '"',
                 'occi.storagelink.deviceid="/dev/vdc"']
        link_location = create_node(self.token, cats, attrs)

        # retrieve link
        LOG.debug(get_node(self.token, link_location)['x-occi-attribute'])

        time.sleep(30)

        # deassociate storage vol - see #15
        destroy_node(self.token, link_location)

        time.sleep(15)
        destroy_node(self.token, vol_location)

        # wait
        cont = False
        while not cont:
            if 'occi.compute.state="active"' in \
                    get_node(self.token, vm_location)['x-occi-attribute']:
                cont = True
            else:
                time.sleep(5)

        # Create a Image from an Active VM
        LOG.debug(trigger_action(self.token, vm_location + '?action='
                                                           'create_image',
                                 'create_image; scheme="http://schemas.'
                                 'openstack.org/instance/action#"',
                                 'org.openstack.snapshot.image_name='
                                 '"awesome_ware"'))

        destroy_node(self.token, vm_location)

    def test_scaling(self):
        """
        Test the scaling operations
        """
        # create new VM
        cats = [RES_TPL_NANO,
                self.os_tpl,
                'compute; scheme="http://schemas.ogf.org/occi/'
                'infrastructure#"']
        vm_location = create_node(self.token, cats)

        # wait
        cont = False
        while not cont:
            if 'occi.compute.state="active"' in \
                    get_node(self.token, vm_location)['x-occi-attribute']:
                cont = True
            else:
                time.sleep(5)

        # scale up VM - see #17
        heads = HEADS.copy()
        heads['X-Auth-Token'] = self.token
        heads['Category'] = RES_TPL_MICRO
        do_request('POST', vm_location, heads)

        # wait
        cont = False
        while not cont:
            if 'occi.compute.state="active"' in \
                    get_node(self.token, vm_location)['x-occi-attribute']:
                cont = True
            else:
                time.sleep(5)

        destroy_node(self.token, vm_location)

    def test_userdata(self):
        """
        Test passing userdata to the VM
        """
        user_data = base64.b64encode("1, 2, 3 this is a test")
        # create new VM
        cats = [RES_TPL_NANO,
                self.os_tpl,
                'user_data; '
                'scheme="http://schemas.openstack.org/compute/instance#"; ',
                'compute; scheme="http://schemas.ogf.org/occi/'
                'infrastructure#"']
        attrs = ['org.openstack.compute.user_data="%s"' % user_data]
        vm_location = create_node(self.token, cats, attrs)

        # XXX
        # is there any way to test that the data is there
        # without logging in into the machine?
        cont = False
        while not cont:
            if 'occi.compute.state="active"' in \
                    get_node(self.token, vm_location)['x-occi-attribute']:
                cont = True
            else:
                time.sleep(5)

        destroy_node(self.token, vm_location)
