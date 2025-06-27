from abc import abstractmethod
from collections.abc import Generator
from typing import final

from dify_plugin.core.runtime import Session
from dify_plugin.entities.datasource import (
    DataSourceMessage,
    DatasourceRuntime,
    OnlineDriverBrowseFilesRequest,
    OnlineDriverBrowseFilesResponse,
    OnlineDriverDownloadFileRequest,
    OnlineDriverFileBucket,
)
from dify_plugin.interfaces.tool import ToolLike


class OnlineDriverDatasource(ToolLike[DataSourceMessage]):
    """
    Online Driver Datasource abstract class
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
        self.response_type = DataSourceMessage

    def browse_files(self, request: OnlineDriverBrowseFilesRequest) -> OnlineDriverBrowseFilesResponse:
        """
        Get the file list
        """
        return OnlineDriverBrowseFilesResponse(result=self._browse_files(request))

    @abstractmethod
    def _browse_files(self, request: OnlineDriverBrowseFilesRequest) -> list[OnlineDriverFileBucket]:
        """
        Browse the files
        """
        raise NotImplementedError("This method should be implemented by a subclass")

    def download_file(self, request: OnlineDriverDownloadFileRequest) -> Generator[DataSourceMessage, None, None]:
        """
        Get the file content
        """
        return self._download_file(request)

    @abstractmethod
    def _download_file(self, request: OnlineDriverDownloadFileRequest) -> Generator[DataSourceMessage, None, None]:
        """
        Download the file content
        """
        raise NotImplementedError("This method should be implemented by a subclass")
