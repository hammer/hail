import aiohttp
from hailtop.config import get_deploy_config
from hailtop.utils import async_to_blocking

from .tokens import get_tokens


async def async_get_userinfo(deploy_config=None):
    if not deploy_config:
        deploy_config = get_deploy_config()
    headers = service_auth_headers(deploy_config, 'auth')
    async with aiohttp.ClientSession(
            raise_for_status=True, timeout=aiohttp.ClientTimeout(total=60)) as session:
        async with session.get(
                deploy_config.url('auth', '/api/v1alpha/userinfo'), headers=headers) as resp:
            return await resp.json()


def get_userinfo(deploy_config=None):
    return async_to_blocking(async_get_userinfo(deploy_config))


def namespace_auth_headers(deploy_config, ns, authorize_target=True):
    tokens = get_tokens()
    headers = {}
    if authorize_target:
        headers['Authorization'] = f'Bearer {tokens.namespace_token_or_error(ns)}'
    if deploy_config.location() == 'external' and ns != 'default':
        headers['X-Hail-Internal-Authorization'] = f'Bearer {tokens.namespace_token_or_error("default")}'
    return headers


def service_auth_headers(deploy_config, service, authorize_target=True):
    ns = deploy_config.service_ns(service)
    return namespace_auth_headers(deploy_config, ns, authorize_target)
