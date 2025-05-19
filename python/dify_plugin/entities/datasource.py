from collections.abc import Mapping
from typing import Any, Optional
from pydantic import BaseModel


class DatasourceRuntime(BaseModel):
    credentials: Mapping[str, Any]
    user_id: Optional[str]
    session_id: Optional[str]
