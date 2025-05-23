from enum import StrEnum
from typing import Optional, Union

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from dify_plugin.entities import I18nObject, ParameterAutoGenerate, ParameterOption, ParameterTemplate
from dify_plugin.entities.oauth import OAuthSchema
from dify_plugin.entities.provider_config import CommonParameterType, ProviderConfig
from dify_plugin.entities.tool import ToolLabelEnum


class DatasourceProviderType(StrEnum):
    """
    Enum class for datasource provider
    """

    ONLINE_DOCUMENT = "online_document"
    WEBSITE_CRAWL = "website_crawl"


class DatasourceParameter(BaseModel):
    """
    Overrides type
    """

    class DatasourceParameterType(StrEnum):
        STRING = CommonParameterType.STRING.value
        NUMBER = CommonParameterType.NUMBER.value
        BOOLEAN = CommonParameterType.BOOLEAN.value
        SELECT = CommonParameterType.SELECT.value
        SECRET_INPUT = CommonParameterType.SECRET_INPUT.value
        FILE = CommonParameterType.FILE.value
        FILES = CommonParameterType.FILES.value

    name: str = Field(..., description="The name of the parameter")
    label: I18nObject = Field(..., description="The label presented to the user")
    placeholder: Optional[I18nObject] = Field(default=None, description="The placeholder presented to the user")
    scope: str | None = None
    auto_generate: Optional[ParameterAutoGenerate] = None
    template: Optional[ParameterTemplate] = None
    required: bool = False
    default: Optional[Union[float, int, str]] = None
    min: Optional[Union[float, int]] = None
    max: Optional[Union[float, int]] = None
    precision: Optional[int] = None
    options: list[ParameterOption] = Field(default_factory=list)
    type: DatasourceParameterType = Field(..., description="The type of the parameter")
    description: I18nObject = Field(..., description="The description of the parameter")


class DatasourceIdentity(BaseModel):
    author: str = Field(..., description="The author of the datasource")
    name: str = Field(..., description="The name of the datasource")
    label: I18nObject = Field(..., description="The label of the datasource")
    provider: str = Field(..., description="The provider of the datasource")
    icon: Optional[str] = None


class DatasourceEntity(BaseModel):
    identity: DatasourceIdentity
    parameters: list[DatasourceParameter] = Field(default_factory=list)
    description: I18nObject = Field(..., description="The label of the datasource")

    @field_validator("parameters", mode="before")
    @classmethod
    def set_parameters(cls, v, validation_info: ValidationInfo) -> list[DatasourceParameter]:
        return v or []


class DatasourceProviderIdentity(BaseModel):
    author: str = Field(..., description="The author of the tool")
    name: str = Field(..., description="The name of the tool")
    description: I18nObject = Field(..., description="The description of the tool")
    icon: str = Field(..., description="The icon of the tool")
    label: I18nObject = Field(..., description="The label of the tool")
    tags: Optional[list[ToolLabelEnum]] = Field(
        default=[],
        description="The tags of the tool",
    )


class DatasourceProviderEntity(BaseModel):
    """
    Datasource provider entity
    """

    identity: DatasourceProviderIdentity
    credentials_schema: list[ProviderConfig] = Field(default_factory=list)
    oauth_schema: Optional[OAuthSchema] = None
    provider_type: DatasourceProviderType


class DatasourceProviderEntityWithPlugin(DatasourceProviderEntity):
    datasources: list[DatasourceEntity] = Field(default_factory=list)
