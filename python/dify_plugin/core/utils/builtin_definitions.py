from typing import Any


class BuiltinDefinitions:
    """
    Builtin schema definitions for datasource and tool manifests
    """

    @classmethod
    def get_definitions(cls) -> dict[str, Any]:
        """
        Get all builtin schema definitions

        Returns:
            Dictionary containing all builtin schema definitions
        """
        return {
            "file": {
                "type": "object",
                "properties": {
                    "dify_builtin_type": {
                        "type": "string",
                        "enum": ["File"],
                        "description": "Business type identifier for frontend",
                    },
                    "name": {"type": "string", "description": "file name"},
                    "size": {"type": "number", "description": "file size"},
                    "file_type": {"type": "string", "description": "file type"},
                    "extension": {"type": "string", "description": "file extension"},
                    "mime_type": {"type": "string", "description": "file mime type"},
                    "transfer_method": {"type": "string", "description": "file transfer method"},
                    "url": {"type": "string", "description": "file url"},
                    "related_id": {"type": "string", "description": "file related id"},
                },
                "required": ["name"],
            },
            "website_crawl": {
                "type": "object",
                "properties": {
                    "dify_builtin_type": {
                        "type": "string",
                        "enum": ["WebsiteCrawl"],
                        "description": "Business type identifier for frontend",
                    },
                    "source_url": {"type": "string", "description": "The URL of the crawled website"},
                    "content": {"type": "string", "description": "The content of the crawled website"},
                    "title": {"type": "string", "description": "The title of the crawled website"},
                    "description": {"type": "string", "description": "The description of the crawled website"},
                },
                "required": ["source_url", "content"],
            },
            "online_document": {
                "type": "object",
                "properties": {
                    "dify_builtin_type": {
                        "type": "string",
                        "enum": ["OnlineDocument"],
                        "description": "Business type identifier for frontend",
                    },
                    "workspace_id": {
                        "type": "string",
                        "description": "The ID of the workspace where the document is stored",
                    },
                    "page_id": {"type": "string", "description": "The ID of the page in the document"},
                    "content": {"type": "string", "description": "The content of the online document"},
                },
                "required": ["content"],
            },
            "general_structure_chunk": {
                "type": "object",
                "properties": {
                    "dify_builtin_type": {
                        "type": "string",
                        "enum": ["GeneralStructureChunk"],
                        "description": "Business type identifier for frontend",
                    },
                    "general_chunks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of general content chunks",
                    },
                },
                "required": ["general_chunks"],
            },
            "parent_child_structure_chunk": {
                "type": "object",
                "properties": {
                    "dify_builtin_type": {
                        "type": "string",
                        "enum": ["ParentChildStructureChunk"],
                        "description": "Business type identifier for frontend",
                    },
                    "parent_mode": {"type": "string", "description": "The mode of parent-child relationship"},
                    "parent_child_chunks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "parent_content": {"type": "string", "description": "The parent content"},
                                "child_contents": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of child contents",
                                },
                            },
                            "required": ["parent_content", "child_contents"],
                        },
                        "description": "List of parent-child chunk pairs",
                    },
                },
                "required": ["parent_mode", "parent_child_chunks"],
            },
            "qa_structure_chunk": {
                "type": "object",
                "properties": {
                    "dify_builtin_type": {
                        "type": "string",
                        "enum": ["QAStructureChunk"],
                        "description": "Business type identifier for frontend",
                    },
                    "qa_chunks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question": {"type": "string", "description": "The question"},
                                "answer": {"type": "string", "description": "The answer"},
                            },
                            "required": ["question", "answer"],
                        },
                        "description": "List of question-answer pairs",
                    },
                },
                "required": ["qa_chunks"],
            },
        }
