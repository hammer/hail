import os
import json
import logging
from aiohttp import web

log = logging.getLogger('gear')


class DeployConfig:
    def __init__(self, _config=None):
        if _config:
            config = _config
        else:
            config_file = os.environ.get(
                'HAIL_DEPLOY_CONFIG_FILE', os.path.expanduser('~/.hail/deploy-config.json'))
            if os.path.isfile(config_file):
                with open(config_file, 'r') as f:
                    config = json.loads(f.read())
            else:
                log.info(f'deploy config file not found: {config_file}')
                config = {
                    'location': 'external',
                    'default_namespace': 'default',
                    'service_namespace': {}
                }
        self._location = config['location']
        assert self._location in ('external', 'k8s', 'gce')
        self._default_ns = config['default_namespace']
        self._service_namespace = config['service_namespace']

    def location(self):
        return self._location

    def service_ns(self, service):
        return self._service_namespace.get(service, self._default_ns)

    def scheme(self):
        return 'https' if self._location == 'external' else 'http'

    def domain(self, service):
        ns = self.service_ns(service)
        if self._location == 'k8s':
            return f'{service}.{ns}'
        if self._location == 'gce':
            return 'hail.internal'
        assert self._location == 'external'
        if ns == 'default':
            return f'{service}.hail.is'
        return 'internal.hail.is'

    def base_path(self, service):
        ns = self.service_ns(service)
        if ns == 'default':
            return ''
        return f'/{ns}/{service}'

    def base_url(self, service):
        return self.scheme() + '://' + self.domain(service) + self.base_path(service)

    def url(self, service, path):
        return f'{self.base_url(service)}{path}'

    def auth_session_cookie_name(self):
        auth_ns = self.service_ns('auth')
        if auth_ns == 'default':
            return 'session'
        return 'sesh'

    def external_url(self, service, path):
        ns = self.service_ns(service)
        if ns == 'default':
            return f'https://{service}.hail.is{path}'
        return f'https://internal.hail.is/{ns}/{service}{path}'

    def prefix_application(self, app, service):
        base_path = self.base_path(service)
        if not base_path:
            return app

        root_routes = web.RouteTableDef()

        @root_routes.get('/healthcheck')
        async def get_healthcheck(request):  # pylint: disable=unused-argument,unused-variable
            return web.Response()

        root_app = web.Application()
        root_app.add_routes(root_routes)
        root_app.add_subapp(base_path, app)

        return root_app


deploy_config = None


def get_deploy_config():
    global deploy_config

    if not deploy_config:
        deploy_config = DeployConfig()
    return deploy_config
