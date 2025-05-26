from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.interfaces.datasource import DatasourceProvider


class NotionDatasourceProvider(DatasourceProvider):
    def _oauth_get_authorization_url(self, system_credentials: Mapping[str, Any]) -> str:
        return super()._oauth_get_authorization_url(system_credentials)

    def _oauth_get_credentials(self, system_credentials: Mapping[str, Any], request: Request) -> Mapping[str, Any]:
        return super()._oauth_get_credentials(system_credentials, request)

    def _validate_credentials(self, credentials: Mapping[str, Any]):
        """
        Validate the credentials for the Notion datasource provider.
        """
        pass
