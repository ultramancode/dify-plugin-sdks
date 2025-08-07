from typing import Any

from dify_plugin.core.utils.builtin_definitions import BuiltinDefinitions


def load_builtin_definitions() -> dict[str, Any]:
    """
    Load builtin definitions from BuiltinDefinitions class
    
    Returns:
        Dictionary containing builtin schema definitions
    """
    return BuiltinDefinitions.get_definitions()


def resolve_schema_refs(schema: Any, definitions: dict[str, Any]) -> Any:
    """
    Recursively resolve $ref references in a JSON schema

    Args:
        schema: The schema object that may contain $ref references
        definitions: Available type definitions to resolve references against

    Returns:
        Schema with all $ref references resolved
    """
    if isinstance(schema, dict):
        if "$ref" in schema:
            # Resolve the reference
            ref = schema["$ref"]
            if ref.startswith("#/$defs/"):
                type_name = ref.replace("#/$defs/", "")
                if type_name in definitions:
                    # Return the resolved definition (recursively resolve it too)
                    return resolve_schema_refs(definitions[type_name], definitions)
                else:
                    raise ValueError(f"Reference '{ref}' not found in definitions")
            else:
                raise ValueError(f"Unsupported reference format: {ref}")
        else:
            # Recursively resolve references in nested objects
            resolved = {}
            for key, value in schema.items():
                resolved[key] = resolve_schema_refs(value, definitions)
            return resolved
    elif isinstance(schema, list):
        # Recursively resolve references in arrays
        return [resolve_schema_refs(item, definitions) for item in schema]
    else:
        # Return primitive values as-is
        return schema


def resolve_output_schema(output_schema: Any, user_definitions: dict[str, Any] | None = None) -> Any:
    """
    Resolve output schema with builtin and user definitions
    
    Args:
        output_schema: The output schema to resolve
        user_definitions: Optional user-defined schema definitions
        
    Returns:
        Resolved output schema with all $ref references resolved
    """
    if user_definitions is None:
        user_definitions = {}
    
    # Load builtin definitions and merge with user definitions
    builtin_definitions = load_builtin_definitions()
    all_definitions = {**builtin_definitions, **user_definitions}
    
    return resolve_schema_refs(output_schema, all_definitions)