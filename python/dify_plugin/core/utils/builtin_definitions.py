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
            "general_structure_chunk": {
                "type": "object",
                "properties": {
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
