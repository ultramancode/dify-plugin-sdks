from collections.abc import Mapping
from typing import Any, Protocol

from pydantic import BaseModel
from werkzeug import Request


class OAuthCredentials(BaseModel):
    metadata: Mapping[str, Any] | None = None
    credentials: Mapping[str, Any]


class OAuthProviderProtocol(Protocol):
    def oauth_get_authorization_url(self, redirect_uri: str, system_credentials: Mapping[str, Any]) -> str:
        """
        Get the authorization url
        :param redirect_uri: redirect uri for the callback
        :param system_credentials: system credentials
        :return: authorization url
        """
        ...

    def oauth_get_credentials(
        self,
        redirect_uri: str,
        system_credentials: Mapping[str, Any],
        request: Request,
    ) -> OAuthCredentials:
        """
        Get the credentials
        :param redirect_uri: redirect uri
        :param request: request
        :param system_credentials: system credentials
        :return: { "metadata": { "avatar_url": str, "name": str }, "credentials": credentials }
        """
        ...
