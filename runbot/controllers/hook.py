# -*- coding: utf-8 -*-

import time
import json
import logging

from odoo import http, tools
from odoo.http import request

_logger = logging.getLogger(__name__)

class RunbotHook(http.Controller):

    @http.route(['/runbot/hook/<int:repo_id>', '/runbot/hook/org'], type='http', auth="public", website=True, csrf=False)
    def hook(self, repo_id=None, **post):
        event = request.httprequest.headers.get("X-Github-Event")
        payload = json.loads(request.params.get('payload', '{}'))
        if repo_id is None:
            repo_data = payload.get('repository')
            if repo_data and event in ['push', 'pull_request']:
                repo_domain = [
                    '|', '|', ('name', '=', repo_data['ssh_url']),
                    ('name', '=', repo_data['clone_url']),
                    ('name', '=', repo_data['clone_url'].rstrip('.git')),
                ]
                repo = request.env['runbot.repo'].sudo().search(
                    repo_domain, limit=1)
                repo_id = repo.id

        repo = request.env['runbot.repo'].sudo().browse([repo_id])

        # force update of dependencies to in case a hook is lost
        if not payload or event == 'push' or (event == 'pull_request' and payload.get('action') in ('synchronize', 'opened', 'reopened')):
            (repo | repo.dependency_ids).set_hook_time(time.time())
        elif event == 'pull_request' and payload and payload.get('action', '') == 'edited' and 'base' in payload.get('changes'):
            # handle PR that have been re-targeted
            pr_number = payload.get('pull_request', {}).get('number', '')
            branch = request.env['runbot.branch'].sudo().search([('repo_id', '=', repo.id), ('name', '=', 'refs/pull/%s' % pr_number)])
            branch._get_branch_infos(payload.get('pull_request', {}))
        else:
            _logger.debug('Ignoring unsupported hook %s %s', event, payload.get('action', ''))
        return ""
