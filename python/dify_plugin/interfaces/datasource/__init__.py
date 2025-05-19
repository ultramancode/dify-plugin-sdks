from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, final

from werkzeug import Request

from dify_plugin.core.runtime import Session
from dify_plugin.entities.datasource import DatasourceRuntime


class Datasource(ABC):
    """
    Datasource abstract class
    """

    runtime: DatasourceRuntime
    session: Session

    @final
    def __init__(
        self,
        runtime: DatasourceRuntime,
        session: Session,
    ):
        """
        Initialize the datasource

        NOTE:
        - This method has been marked as final, DO NOT OVERRIDE IT.
        """
        self.runtime = runtime
        self.session = session

    def invoke_first_step(self, datasource_parameters: Mapping[str, Any]) -> Mapping[str, Any]:
        """
        Invoke the first step of the datasource, waiting for a better abstraction
        """
        return self._invoke_first_step(datasource_parameters)

    @abstractmethod
    def _invoke_first_step(self, datasource_parameters: Mapping[str, Any]) -> Mapping[str, Any]:
        """
        Invoke the first step of the datasource, waiting for a better abstraction
        """
        raise NotImplementedError("This method should be implemented by a subclass")

    def invoke_second_step(self, datasource_parameters: Mapping[str, Any]) -> Mapping[str, Any]:
        """
        Invoke the second step of the datasource, waiting for a better abstraction
        """
        return self._invoke_second_step(datasource_parameters)

    @abstractmethod
    def _invoke_second_step(self, datasource_parameters: Mapping[str, Any]) -> Mapping[str, Any]:
        """
        Invoke the second step of the datasource, waiting for a better abstraction
        """
        raise NotImplementedError("This method should be implemented by a subclass")


class DatasourceProvider:
    """
    A provider for a datasource
    """

    def validate_credentials(self, credentials: dict):
        return self._validate_credentials(credentials)

    def _validate_credentials(self, credentials: dict):
        raise NotImplementedError("This method should be implemented by a subclass")

    def oauth_get_authorization_url(self, system_credentials: Mapping[str, Any]) -> str:
        return self._oauth_get_authorization_url(system_credentials)

    def _oauth_get_authorization_url(self, system_credentials: Mapping[str, Any]) -> str:
        raise NotImplementedError("This method should be implemented by a subclass")

    def oauth_get_credentials(self, system_credentials: Mapping[str, Any], request: Request) -> Mapping[str, Any]:
        return self._oauth_get_credentials(system_credentials, request)

    def _oauth_get_credentials(self, system_credentials: Mapping[str, Any], request: Request) -> Mapping[str, Any]:
        raise NotImplementedError("This method should be implemented by a subclass")
