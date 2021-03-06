#!/usr/bin/env python3

# Copyright 2020 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import copy
import unittest
import json

from unittest import mock

from ops import framework
from ops.charm import CharmBase
from ops.testing import Harness

from charmhelpers.contrib.storage.linux.ceph import CephBrokerRq

from interface_ceph_client import CephClientRequires, BrokerAvailableEvent


class TestCephClientRequires(unittest.TestCase):

    TEST_CASE_0 = {
        'ceph-mon/0': {
            'remote_unit_data': {
                'ingress-address': '192.0.2.1',
                'ceph-public-address': '192.0.2.1'}},
        'ceph-mon/1': {
            'remote_unit_data': {
                'ingress-address': '192.0.2.2',
                'ceph-public-address': '192.0.2.2'}},
        'ceph-mon/2': {
            'remote_unit_data': {
                'ingress-address': '192.0.2.3',
                'ceph-public-address': '192.0.2.3'}},
        'client/0': {
            'remote_unit_data': {
                'ingress-address': '192.0.2.4'}}}

    TEST_CASE_1 = {
        'ceph-mon/0': {
            'remote_unit_data': {
                'auth': 'cephx',
                'key': 'AQBUfpVeNl7CHxAA8/f6WTcYFxW2dJ5VyvWmJg==',
                'ingress-address': '192.0.2.1',
                'ceph-public-address': '192.0.2.1'}},
        'ceph-mon/1': {
            'remote_unit_data': {
                'auth': 'cephx',
                'key': 'AQBUfpVeNl7CHxAA8/f6WTcYFxW2dJ5VyvWmJg==',
                'ingress-address': '192.0.2.2',
                'ceph-public-address': '192.0.2.2',
                'broker-rsp-client-0': (
                    '{"exit-code": 0, '
                    '"request-id": "a3ad24dd-7e2f-11ea-8ba2-e5a5b68b415f"}'),
                'broker-rsp-client-1': (
                    '{"exit-code": 0, '
                    '"request-id": "c729e333-7e2f-11ea-8b3c-09dfcfc90070"}'),
                'broker_rsp': (
                    '{"exit-code": 0, '
                    '"request-id": "c729e333-7e2f-11ea-8b3c-09dfcfc90070')}},
        'ceph-mon/2': {
            'remote_unit_data': {
                'auth': 'cephx',
                'key': 'AQBUfpVeNl7CHxAA8/f6WTcYFxW2dJ5VyvWmJg==',
                'ingress-address': '192.0.2.3',
                'ceph-public-address': '192.0.2.3'}},
        'client/0': {
            'remote_unit_data': {
                'ingress-address': '192.0.2.4',
                'broker_req': (
                    '{"api-version": 1, '
                    '"ops": [{"op": "create-pool", "name": "tmbtil", '
                    '"replicas": 3, "pg_num": null, "weight": null, '
                    '"group": null, "group-namespace": null, '
                    '"app-name": null, '
                    '"max-bytes": null, "max-objects": null}, '
                    '{"op": "set-key-permissions", '
                    '"permissions": ["osd", "allow *", "mon", "allow *", '
                    '"mgr", '
                    '"allow r"], "client": "ceph-iscsi"}], '
                    '"request-id": "a3ad24dd-7e2f-11ea-8ba2-e5a5b68b415f"}')}}}

    def setUp(self):
        self.harness = Harness(CharmBase, meta='''
            name: client
            provides:
              ceph-client:
                interface: ceph-client
        ''')
        self.client_req = CephBrokerRq()
        self.client_req.add_op_create_replicated_pool(
            name='tmbtil',
            replica_count=3)
        self.client_req.add_op({
            'op': 'set-key-permissions',
            'permissions': [
                'osd', 'allow *',
                'mon', 'allow *',
                'mgr', 'allow r'],
            'client': 'ceph-iscsi'})
        self.client_req.request_id = 'a3ad24dd-7e2f-11ea-8ba2-e5a5b68b415f'
        self.random_request = CephBrokerRq()
        self.random_request.add_op_create_replicated_pool(
            name='another-pool',
            replica_count=3)

    def apply_unit_data(self, test_case, rel_id):
        for unit_name, data in test_case.items():
            self.harness.add_relation_unit(
                rel_id,
                unit_name,
                remote_unit_data=test_case[unit_name]['remote_unit_data'])

    def harness_setup(self, test_case, load_requst_from_client=False):
        rel_id = self.harness.add_relation('ceph-client', 'ceph-mon')
        self.apply_unit_data(test_case, rel_id)
        self.harness.begin()
        ceph_client = CephClientRequires(self.harness.charm, 'ceph-client')
        if load_requst_from_client:
            raw_rq = test_case['client/0']['remote_unit_data']['broker_req']
            ceph_client.state.broker_req = raw_rq
        return ceph_client

    def test_request_osd_settings(self):
        self.harness.begin()
        self.ceph_client = CephClientRequires(self.harness.charm,
                                              'ceph-client')
        relation_id = self.harness.add_relation('ceph-client', 'ceph-mon')
        self.harness.add_relation_unit(
            relation_id,
            'ceph-mon/0',
            {'ingress-address': '192.0.2.2'}
        )
        settings = {
            'osd heartbeat grace': 20,
            'osd heartbeat interval': 5
        }
        self.ceph_client.request_osd_settings(settings)

        rel = self.harness.charm.model.get_relation('ceph-client')
        rel_data = rel.data[self.harness.charm.model.unit]
        self.assertEqual(json.loads(rel_data['osd-settings']), settings)

    def test_mon_hosts(self):
        self.harness.begin()
        self.ceph_client = CephClientRequires(self.harness.charm,
                                              'ceph-client')
        mon_ips = ['192.0.2.1', '192.0.2.2', '2001:DB8::1']
        mon_hosts = self.ceph_client.mon_hosts(mon_ips)
        self.assertEqual(mon_hosts, ['192.0.2.1', '192.0.2.2',
                                     '[2001:DB8::1]'])

    def test_mon_hosts_ceph_proxy(self):
        self.harness.begin()
        self.ceph_client = CephClientRequires(self.harness.charm,
                                              'ceph-client')
        proxy_mon_ips = ['192.0.2.1 192.0.2.2 2001:DB8::1']
        mon_hosts = self.ceph_client.mon_hosts(proxy_mon_ips)
        self.assertEqual(mon_hosts, ['192.0.2.1', '192.0.2.2',
                                     '[2001:DB8::1]'])

    def test_get_relation_data(self):
        relation_id_a = self.harness.add_relation('ceph-client', 'ceph-monA')
        relation_id_b = self.harness.add_relation('ceph-client', 'ceph-monB')
        self.harness.begin()
        self.harness.add_relation_unit(
            relation_id_a,
            'ceph-monA/0',
            {'ingress-address': '192.0.2.2',
             'ceph-public-address': '192.0.2.2',
             'key': 'foo',
             'auth': 'bar'},
        )
        self.harness.add_relation_unit(
            relation_id_a,
            'ceph-monA/1',
            {'ingress-address': '192.0.2.3'},
        )
        self.harness.add_relation_unit(
            relation_id_b,
            'ceph-monB/0',
            {'ingress-address': '2001:DB8::1',
             'ceph-public-address': '2001:DB8::1',
             'key': 'foo',
             'auth': 'bar'},
        )
        self.harness.add_relation_unit(
            relation_id_b,
            'ceph-monB/1',
            {'ingress-address': '2001:DB8::2',
             'ceph-public-address': '2001:DB8::2'},
        )

        self.ceph_client = CephClientRequires(self.harness.charm,
                                              'ceph-client')
        rel_data = self.ceph_client.get_relation_data()
        self.assertEqual(
            rel_data,
            {
                'mon_hosts': ['192.0.2.2', '[2001:DB8::1]', '[2001:DB8::2]'],
                'key': 'foo',
                'auth': 'bar',
            }
        )

    def test_existing_request_complete(self):
        ceph_client = self.harness_setup(
            self.TEST_CASE_1,
            load_requst_from_client=True)
        self.assertTrue(ceph_client.existing_request_complete())

    def test_existing_request_false(self):
        test_case = copy.deepcopy(self.TEST_CASE_1)
        test_case['ceph-mon/1']['remote_unit_data'] = {}
        ceph_client = self.harness_setup(
            test_case,
            load_requst_from_client=True)
        self.assertFalse(ceph_client.existing_request_complete())

    def test_on_changed(self):
        class TestReceiver(framework.Object):

            def __init__(self, parent, key):
                super().__init__(parent, key)
                self.observed_events = []

            def on_broker_available(self, event):
                self.observed_events.append(event)
        self.harness.begin()
        self.ceph_client = CephClientRequires(self.harness.charm,
                                              'ceph-client')
        receiver = TestReceiver(self.harness.framework, 'receiver')
        self.harness.framework.observe(self.ceph_client.on.broker_available,
                                       receiver)
        # No data yet.
        relation_id = self.harness.add_relation('ceph-client', 'ceph-mon')
        self.harness.add_relation_unit(
            relation_id,
            'ceph-mon/0',
            {'ingress-address': '192.0.2.2',
             'ceph-public-address': '192.0.2.2'},
        )
        self.assertEqual(len(receiver.observed_events), 0)

        # Got the necessary data - should get a BrokerAvailable event.
        self.apply_unit_data(self.TEST_CASE_1, relation_id)
        # 1 broker_available event per mon and 1 completed request: 4 events
        self.assertEqual(len(receiver.observed_events), 4)
        self.assertIsInstance(receiver.observed_events[0],
                              BrokerAvailableEvent)

    @mock.patch.object(CephClientRequires, 'send_request_if_needed')
    # Expected failure, need https://github.com/canonical/operator/pull/196
    @unittest.expectedFailure
    def test_create_replicated_pool(self, _send_request_if_needed):
        # TODO: Replace mocking with real calls. Otherwise this test is not
        # very useful.
        self.harness.begin()
        self.ceph_client = CephClientRequires(self.harness.charm,
                                              'ceph-client')

        self.ceph_client.create_replicated_pool('ceph-client')
        _send_request_if_needed.assert_not_called()

        self.harness.add_relation('ceph-client', 'ceph-mon')
        self.ceph_client.create_replicated_pool('ceph-client')
        _send_request_if_needed.assert_called()

    @mock.patch.object(CephClientRequires, 'send_request_if_needed')
    # Expected failure, need https://github.com/canonical/operator/pull/196
    @unittest.expectedFailure
    def test_create_request_ceph_permissions(self, _send_request_if_needed):
        # TODO: Replace mocking with real calls. Otherwise this test is not
        # very useful.
        self.harness.begin()
        self.ceph_client = CephClientRequires(self.harness.charm,
                                              'ceph-client')
        CEPH_CAPABILITIES = [
            "osd", "allow *",
            "mon", "allow *",
            "mgr", "allow r"
        ]
        self.ceph_client.request_ceph_permissions('ceph-iscsi',
                                                  CEPH_CAPABILITIES)
        _send_request_if_needed.assert_not_called()

        self.harness.add_relation('ceph-client', 'ceph-mon')
        self.ceph_client.create_replicated_pool('ceph-client')
        _send_request_if_needed.assert_called()

    def test_get_previous_request(self):
        ceph_client = self.harness_setup(
            self.TEST_CASE_1,
            load_requst_from_client=False)
        rel = self.harness.charm.model.get_relation('ceph-client')
        self.assertEqual(
            ceph_client.get_previous_request(rel).request_id,
            'a3ad24dd-7e2f-11ea-8ba2-e5a5b68b415f')

    def test_get_previous_request_no_request(self):
        ceph_client = self.harness_setup(
            self.TEST_CASE_0,
            load_requst_from_client=False)
        rel = self.harness.charm.model.get_relation('ceph-client')
        self.assertEqual(
            ceph_client.get_previous_request(rel),
            None)

    def test_get_request_states(self):
        ceph_client = self.harness_setup(
            self.TEST_CASE_1,
            load_requst_from_client=False)
        relations = [self.harness.charm.model.get_relation('ceph-client')]
        self.assertEqual(
            ceph_client.get_request_states(self.client_req, relations),
            {'ceph-client:0': {'complete': True, 'sent': True}})

    def test_get_request_states_new_request(self):
        ceph_client = self.harness_setup(
            self.TEST_CASE_1,
            load_requst_from_client=False)
        relations = [self.harness.charm.model.get_relation('ceph-client')]
        self.assertEqual(
            ceph_client.get_request_states(self.random_request, relations),
            {'ceph-client:0': {'complete': False, 'sent': False}})

    def test_is_request_complete_for_relation(self):
        ceph_client = self.harness_setup(
            self.TEST_CASE_1,
            load_requst_from_client=False)
        relation = self.harness.charm.model.get_relation('ceph-client')
        self.assertTrue(
            ceph_client.is_request_complete_for_relation(
                self.client_req,
                relation))

    def test_is_request_complete(self):
        ceph_client = self.harness_setup(
            self.TEST_CASE_1,
            load_requst_from_client=False)
        relations = [self.harness.charm.model.get_relation('ceph-client')]
        self.assertTrue(
            ceph_client.is_request_complete(
                self.client_req,
                relations))

    def test_is_request_complete_similar_req(self):
        ceph_client = self.harness_setup(
            self.TEST_CASE_1,
            load_requst_from_client=False)
        relations = [self.harness.charm.model.get_relation('ceph-client')]
        similar_req = copy.deepcopy(self.client_req)
        similar_req.request_id = '2234234234'
        self.assertTrue(
            ceph_client.is_request_complete(
                similar_req,
                relations))

    def test_is_request_complete_new_req(self):
        ceph_client = self.harness_setup(
            self.TEST_CASE_1,
            load_requst_from_client=False)
        relations = [self.harness.charm.model.get_relation('ceph-client')]
        self.assertFalse(
            ceph_client.is_request_complete(
                self.random_request,
                relations))

    def test_is_request_sent(self):
        ceph_client = self.harness_setup(
            self.TEST_CASE_1,
            load_requst_from_client=False)
        relations = [self.harness.charm.model.get_relation('ceph-client')]
        self.assertTrue(
            ceph_client.is_request_sent(
                self.client_req,
                relations))

    def test_is_request_sent_similar_req(self):
        ceph_client = self.harness_setup(
            self.TEST_CASE_1,
            load_requst_from_client=False)
        relations = [self.harness.charm.model.get_relation('ceph-client')]
        similar_req = copy.deepcopy(self.client_req)
        similar_req.request_id = '2234234234'
        self.assertTrue(
            ceph_client.is_request_sent(
                similar_req,
                relations))

    def test_is_request_sent_new_req(self):
        ceph_client = self.harness_setup(
            self.TEST_CASE_1,
            load_requst_from_client=False)
        relations = [self.harness.charm.model.get_relation('ceph-client')]
        self.assertFalse(
            ceph_client.is_request_sent(
                self.random_request,
                relations))

    def test_send_request_if_needed(self):
        ceph_client = self.harness_setup(
            self.TEST_CASE_0,
            load_requst_from_client=False)
        relations = [self.harness.charm.model.get_relation('ceph-client')]
        self.assertIsNone(
            relations[0].data[self.harness.charm.model.unit].get('broker_req'))
        ceph_client.send_request_if_needed(
            self.random_request,
            relations)
        self.assertIsNotNone(
            relations[0].data[self.harness.charm.model.unit]['broker_req'])

    def test_send_request_if_needed_duplicate(self):
        ceph_client = self.harness_setup(
            self.TEST_CASE_1,
            load_requst_from_client=False)
        relations = [self.harness.charm.model.get_relation('ceph-client')]
        similar_req = copy.deepcopy(self.client_req)
        similar_req.request_id = '2234234234'
        orig_req_data = relations[0].data[self.harness.charm.model.unit].get(
            'broker_req')
        ceph_client.send_request_if_needed(
            similar_req,
            relations)
        self.assertEqual(
            relations[0].data[self.harness.charm.model.unit]['broker_req'],
            orig_req_data)


if __name__ == '__main__':
    unittest.main()
