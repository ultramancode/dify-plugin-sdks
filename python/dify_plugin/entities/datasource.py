from collections.abc import Mapping
from typing import Any, Optional

from pydantic import BaseModel, Field

from dify_plugin.entities.invoke_message import InvokeMessage


class DatasourceRuntime(BaseModel):
    credentials: Mapping[str, Any]
    user_id: Optional[str]
    session_id: Optional[str]

class WebSiteInfoDetail(BaseModel):
    source_url: str = Field(..., description="The url of the website")
    content: str = Field(..., description="The content of the website")
    title: str = Field(..., description="The title of the website")
    description: str = Field(..., description="The description of the website")

class WebSiteInfo(BaseModel):
    """
    Website info
    """
    status: Optional[str] = Field(..., description="crawl job status")
    web_info_list: Optional[list[WebSiteInfoDetail]] = []
    total: Optional[int] = Field(..., description="The total number of websites")
    completed: Optional[int] = Field(..., description="The number of completed websites")

class GetWebsiteCrawlResponse(BaseModel):
    """
    Get website crawl response
    """
    result: WebSiteInfo

class OnlineDocumentPage(BaseModel):
    """
    Online document page
    """

    page_id: str = Field(..., description="The page id")
    page_title: str = Field(..., description="The page title")
    page_icon: Optional[dict] = Field(None, description="The page icon")
    type: str = Field(..., description="The type of the page")
    last_edited_time: str = Field(..., description="The last edited time")


class OnlineDocumentInfo(BaseModel):
    """
    Online document info
    """

    workspace_id: str = Field(..., description="The workspace id")
    workspace_name: str = Field(..., description="The workspace name")
    workspace_icon: str = Field(..., description="The workspace icon")
    total: int = Field(..., description="The total number of documents")
    pages: list[OnlineDocumentPage] = Field(..., description="The pages of the online document")


class GetOnlineDocumentPagesResponse(BaseModel):
    """
    Get online document pages response
    """

    result: list[OnlineDocumentInfo]


class GetOnlineDocumentPageContentRequest(BaseModel):
    """
    Get online document page content request
    """

    workspace_id: str = Field(..., description="The workspace id")
    page_id: str = Field(..., description="The page id")
    type: str = Field(..., description="The type of the page")

class DataSourceMessage(InvokeMessage):
    pass
