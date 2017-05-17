# -*-  coding: utf-8 -*-
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from zengine.lib.test_utils import BaseTestCase


class TestCase(BaseTestCase):
    def test_check_user_task_rerun(self):

        for i in range(3):
            # If pre-task is user task and there is no wf_meta, engine should rerun this user task.
            self.prepare_client('/check_user_task_rerun', username='super_user')
            resp = self.client.post(cmd=i)
            token = resp.token
            assert resp.json['task_name'] == 'user_task_a'
            self.prepare_client('/check_user_task_rerun', username='super_user', token=token)
            resp = self.client.post(wf_meta=False)
            assert resp.json['task_name'] == 'user_task_a'

        for i in range(3, 5):
            self.prepare_client('/check_user_task_rerun', username='super_user')
            resp = self.client.post(cmd=i)
            token = resp.token
            assert resp.json['task_name'] == 'user_task_b'
            resp = self.client.post()
            assert resp.json['task_name'] == 'user_task_a'
            self.prepare_client('/check_user_task_rerun', username='super_user', token=token)
            if i == 3:
                # User Task which is before than EndEvent test.
                # If user task is before than EndEvent, engine should ignore rerun and finish wf.
                self.client.post()
                assert self.client.current.wf_cache.wf_state['finished'] == True
            else:
                # First lane ends with user task test.
                # Generally this user task is message box and doesn't have buttons. If there is
                # lane change and lane ends with user task, engine should ignore rerun and
                # continue to wf execution.
                resp = self.client.post()
                assert resp.json['task_name'] == 'user_task_b'
