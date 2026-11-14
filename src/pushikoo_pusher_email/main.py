from loguru import logger
from pushikoo_interface import Pusher, Struct

from pushikoo_pusher_email.api import EmailClient
from pushikoo_pusher_email.config import AdapterConfig, InstanceConfig


class EmailPusher(Pusher[AdapterConfig, InstanceConfig]):
    def __init__(self) -> None:
        logger.debug(f"{self.adapter_name}.{self.identifier} initialized")

    def push(self, content: Struct) -> None:
        account = self.config.accounts[self.instance_config.account]
        client = EmailClient(account, proxies=self.ctx.get_proxies())
        client.send(content, self.instance_config)
