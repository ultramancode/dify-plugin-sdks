import codecs
import json
import logging
import uuid
from collections.abc import Generator
from decimal import Decimal
from typing import Any, Optional, Union, cast
from urllib.parse import urljoin

import requests
from pydantic import TypeAdapter, ValidationError

from dify_plugin.entities import I18nObject
from dify_plugin.entities.model import (
    AIModelEntity,
    DefaultParameterName,
    FetchFrom,
    ModelFeature,
    ModelPropertyKey,
    ModelType,
    ParameterRule,
    ParameterType,
    PriceConfig,
)
from dify_plugin.entities.model.llm import (
    LLMMode,
    LLMResult,
    LLMResultChunk,
    LLMResultChunkDelta,
)
from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    ImagePromptMessageContent,
    PromptMessage,
    PromptMessageContent,
    PromptMessageContentType,
    PromptMessageFunction,
    PromptMessageTool,
    SystemPromptMessage,
    ToolPromptMessage,
    UserPromptMessage,
)
from dify_plugin.errors.model import CredentialsValidateFailedError, InvokeError
from dify_plugin.interfaces.model.large_language_model import LargeLanguageModel
from dify_plugin.interfaces.model.openai_compatible.common import _CommonOaiApiCompat

logger = logging.getLogger(__name__)


def _gen_tool_call_id() -> str:
    return f"chatcmpl-tool-{uuid.uuid4().hex!s}"


def _increase_tool_call(
    new_tool_calls: list[AssistantPromptMessage.ToolCall], existing_tools_calls: list[AssistantPromptMessage.ToolCall]
):
    """
    Merge incremental tool call updates into existing tool calls.

    :param new_tool_calls: List of new tool call deltas to be merged.
    :param existing_tools_calls: List of existing tool calls to be modified IN-PLACE.
    """

    def get_tool_call(tool_call_id: str):
        """
        Get or create a tool call by ID

        :param tool_call_id: tool call ID
        :return: existing or new tool call
        """
        if not tool_call_id:
            return existing_tools_calls[-1]

        _tool_call = next((_tool_call for _tool_call in existing_tools_calls if _tool_call.id == tool_call_id), None)
        if _tool_call is None:
            _tool_call = AssistantPromptMessage.ToolCall(
                id=tool_call_id,
                type="function",
                function=AssistantPromptMessage.ToolCall.ToolCallFunction(name="", arguments=""),
            )
            existing_tools_calls.append(_tool_call)

        return _tool_call

    for new_tool_call in new_tool_calls:
        # generate ID for tool calls with function name but no ID to track them
        if new_tool_call.function.name and not new_tool_call.id:
            new_tool_call.id = _gen_tool_call_id()
        # get tool call
        tool_call = get_tool_call(new_tool_call.id)
        # update tool call
        if new_tool_call.id:
            tool_call.id = new_tool_call.id
        if new_tool_call.type:
            tool_call.type = new_tool_call.type
        if new_tool_call.function.name:
            tool_call.function.name = new_tool_call.function.name
        if new_tool_call.function.arguments:
            tool_call.function.arguments += new_tool_call.function.arguments


class OAICompatLargeLanguageModel(_CommonOaiApiCompat, LargeLanguageModel):
    """
    Model class for OpenAI large language model.
    """

    def _invoke(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        model_parameters: dict,
        tools: Optional[list[PromptMessageTool]] = None,
        stop: Optional[list[str]] = None,
        stream: bool = True,
        user: Optional[str] = None,
    ) -> Union[LLMResult, Generator]:
        """
        Invoke large language model

        :param model: model name
        :param credentials: model credentials
        :param prompt_messages: prompt messages
        :param model_parameters: model parameters
        :param tools: tools for tool calling
        :param stop: stop words
        :param stream: is stream response
        :param user: unique user id
        :return: full response or stream response chunk generator result
        """

        # text completion model
        return self._generate(
            model=model,
            credentials=credentials,
            prompt_messages=prompt_messages,
            model_parameters=model_parameters,
            tools=tools,
            stop=stop,
            stream=stream,
            user=user,
        )

    def get_num_tokens(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        tools: Optional[list[PromptMessageTool]] = None,
    ) -> int:
        """
        Get number of tokens for given prompt messages

        :param model:
        :param credentials:
        :param prompt_messages:
        :param tools: tools for tool calling
        :return:
        """
        return self._num_tokens_from_messages(prompt_messages, tools, credentials)

    def validate_credentials(self, model: str, credentials: dict) -> None:
        """
        Validate model credentials using requests to ensure compatibility with all providers following
         OpenAI's API standard.

        :param model: model name
        :param credentials: model credentials
        :return:
        """
        try:
            headers = {"Content-Type": "application/json"}

            api_key = credentials.get("api_key")
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            endpoint_url = credentials["endpoint_url"]
            if not endpoint_url.endswith("/"):
                endpoint_url += "/"

            # prepare the payload for a simple ping to the model
            data = {"model": credentials.get("endpoint_model_name", model), "max_tokens": 5}

            completion_type = LLMMode.value_of(credentials["mode"])

            if completion_type is LLMMode.CHAT:
                data["messages"] = [
                    {"role": "user", "content": "ping"},
                ]
                endpoint_url = urljoin(endpoint_url, "chat/completions")
            elif completion_type is LLMMode.COMPLETION:
                data["prompt"] = "ping"
                endpoint_url = urljoin(endpoint_url, "completions")
            else:
                raise ValueError("Unsupported completion type for model configuration.")

            # ADD stream validate_credentials
            stream_mode_auth = credentials.get("stream_mode_auth", "not_use")
            if stream_mode_auth == "use":
                data["stream"] = True
                data["max_tokens"] = 10
                response = requests.post(endpoint_url, headers=headers, json=data, timeout=(10, 300), stream=True)
                if response.status_code != 200:
                    raise CredentialsValidateFailedError(
                        f"Credentials validation failed with status code {response.status_code} "
                        f"and response body {response.text}"
                    )
                return

            # send a post request to validate the credentials
            response = requests.post(endpoint_url, headers=headers, json=data, timeout=(10, 300))

            if response.status_code != 200:
                raise CredentialsValidateFailedError(
                    f"Credentials validation failed with status code {response.status_code} "
                    f"and response body {response.text}"
                )

            try:
                json_result = response.json()
            except json.JSONDecodeError:
                raise CredentialsValidateFailedError(
                    f"Credentials validation failed: JSON decode error, response body {response.text}"
                ) from None

            if completion_type is LLMMode.CHAT and json_result.get("object", "") == "":
                json_result["object"] = "chat.completion"
            elif completion_type is LLMMode.COMPLETION and json_result.get("object", "") == "":
                json_result["object"] = "text_completion"

            if completion_type is LLMMode.CHAT and (
                "object" not in json_result or json_result["object"] != "chat.completion"
            ):
                raise CredentialsValidateFailedError(
                    f"Credentials validation failed: invalid response object, "
                    f"must be 'chat.completion', response body {response.text}"
                )
            elif completion_type is LLMMode.COMPLETION and (
                "object" not in json_result or json_result["object"] != "text_completion"
            ):
                raise CredentialsValidateFailedError(
                    f"Credentials validation failed: invalid response object, "
                    f"must be 'text_completion', response body {response.text}"
                )
        except CredentialsValidateFailedError:
            raise
        except Exception as ex:
            raise CredentialsValidateFailedError(
                f"An error occurred during credentials validation: {ex!s}, response body {response.text}"
            ) from ex

    def get_customizable_model_schema(self, model: str, credentials: dict) -> AIModelEntity:
        """
        generate custom model entities from credentials
        """
        features = []

        function_calling_type = credentials.get("function_calling_type", "no_call")
        if function_calling_type == "function_call":
            features.append(ModelFeature.TOOL_CALL)
        elif function_calling_type == "tool_call":
            features.append(ModelFeature.MULTI_TOOL_CALL)

        stream_function_calling = credentials.get("stream_function_calling", "supported")
        if stream_function_calling == "supported":
            features.append(ModelFeature.STREAM_TOOL_CALL)

        vision_support = credentials.get("vision_support", "not_support")
        if vision_support == "support":
            features.append(ModelFeature.VISION)

        entity = AIModelEntity(
            model=model,
            label=I18nObject(en_US=model),
            model_type=ModelType.LLM,
            fetch_from=FetchFrom.CUSTOMIZABLE_MODEL,
            features=features,
            model_properties={
                ModelPropertyKey.CONTEXT_SIZE: int(credentials.get("context_size", "4096")),
                ModelPropertyKey.MODE: credentials.get("mode"),
            },
            parameter_rules=[
                ParameterRule(
                    name=DefaultParameterName.TEMPERATURE.value,
                    label=I18nObject(en_US="Temperature", zh_Hans="温度"),
                    help=I18nObject(
                        en_US="Kernel sampling threshold. Used to determine the randomness of the results."
                        "The higher the value, the stronger the randomness."
                        "The higher the possibility of getting different answers to the same question.",
                        zh_Hans="核采样阈值。用于决定结果随机性，取值越高随机性越强即相同的问题得到的不同答案的可能性越高。",
                    ),
                    type=ParameterType.FLOAT,
                    default=float(credentials.get("temperature", 0.7)),
                    min=0,
                    max=2,
                    precision=2,
                ),
                ParameterRule(
                    name=DefaultParameterName.TOP_P.value,
                    label=I18nObject(en_US="Top P", zh_Hans="Top P"),
                    help=I18nObject(
                        en_US="The probability threshold of the nucleus sampling method during the generation process."
                        "The larger the value is, the higher the randomness of generation will be."
                        "The smaller the value is, the higher the certainty of generation will be.",
                        zh_Hans="生成过程中核采样方法概率阈值。取值越大，生成的随机性越高；取值越小，生成的确定性越高。",
                    ),
                    type=ParameterType.FLOAT,
                    default=float(credentials.get("top_p", 1)),
                    min=0,
                    max=1,
                    precision=2,
                ),
                ParameterRule(
                    name=DefaultParameterName.FREQUENCY_PENALTY.value,
                    label=I18nObject(en_US="Frequency Penalty", zh_Hans="频率惩罚"),
                    help=I18nObject(
                        en_US="For controlling the repetition rate of words used by the model."
                        "Increasing this can reduce the repetition of the same words in the model's output.",
                        zh_Hans="用于控制模型已使用字词的重复率。 提高此项可以降低模型在输出中重复相同字词的重复度。",
                    ),
                    type=ParameterType.FLOAT,
                    default=float(credentials.get("frequency_penalty", 0)),
                    min=-2,
                    max=2,
                ),
                ParameterRule(
                    name=DefaultParameterName.PRESENCE_PENALTY.value,
                    label=I18nObject(en_US="Presence Penalty", zh_Hans="存在惩罚"),
                    help=I18nObject(
                        en_US="Used to control the repetition rate when generating models."
                        "Increasing this can reduce the repetition rate of model generation.",
                        zh_Hans="用于控制模型生成时的重复度。提高此项可以降低模型生成的重复度。",
                    ),
                    type=ParameterType.FLOAT,
                    default=float(credentials.get("presence_penalty", 0)),
                    min=-2,
                    max=2,
                ),
                ParameterRule(
                    name=DefaultParameterName.MAX_TOKENS.value,
                    label=I18nObject(en_US="Max Tokens", zh_Hans="最大标记"),
                    help=I18nObject(
                        en_US="Maximum length of tokens for the model response.",
                        zh_Hans="模型回答的tokens的最大长度。",
                    ),
                    type=ParameterType.INT,
                    default=512,
                    min=1,
                    max=int(credentials.get("max_tokens_to_sample", 4096)),
                ),
            ],
            pricing=PriceConfig(
                input=Decimal(credentials.get("input_price", 0)),
                output=Decimal(credentials.get("output_price", 0)),
                unit=Decimal(credentials.get("unit", 0)),
                currency=credentials.get("currency", "USD"),
            ),
        )

        if credentials["mode"] == "chat":
            entity.model_properties[ModelPropertyKey.MODE] = LLMMode.CHAT.value
        elif credentials["mode"] == "completion":
            entity.model_properties[ModelPropertyKey.MODE] = LLMMode.COMPLETION.value
        else:
            raise ValueError(f"Unknown completion type {credentials['completion_type']}")

        return entity

    # validate_credentials method has been rewritten to use the requests library for compatibility with all providers
    # following OpenAI's API standard.
    def _generate(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        model_parameters: dict,
        tools: Optional[list[PromptMessageTool]] = None,
        stop: Optional[list[str]] = None,
        stream: bool = True,
        user: Optional[str] = None,
    ) -> Union[LLMResult, Generator]:
        """
        Invoke llm completion model

        :param model: model name
        :param credentials: credentials
        :param prompt_messages: prompt messages
        :param model_parameters: model parameters
        :param stop: stop words
        :param stream: is stream response
        :param user: unique user id
        :return: full response or stream response chunk generator result
        """
        headers = {
            "Content-Type": "application/json",
            "Accept-Charset": "utf-8",
        }
        extra_headers = credentials.get("extra_headers")
        if extra_headers is not None:
            headers = {
                **headers,
                **extra_headers,
            }

        api_key = credentials.get("api_key")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        endpoint_url = credentials["endpoint_url"]
        if not endpoint_url.endswith("/"):
            endpoint_url += "/"

        response_format = model_parameters.get("response_format")
        if response_format:
            if response_format == "json_schema":
                json_schema = model_parameters.get("json_schema")
                if not json_schema:
                    raise ValueError("Must define JSON Schema when the response format is json_schema")
                try:
                    schema = TypeAdapter(dict[str, Any]).validate_json(json_schema)
                except Exception as exc:
                    raise ValueError(f"not correct json_schema format: {json_schema}") from exc
                model_parameters.pop("json_schema")
                model_parameters["response_format"] = {"type": "json_schema", "json_schema": schema}
            else:
                model_parameters["response_format"] = {"type": response_format}
        elif "json_schema" in model_parameters:
            del model_parameters["json_schema"]

        data = {"model": credentials.get("endpoint_model_name", model), "stream": stream, **model_parameters}

        completion_type = LLMMode.value_of(credentials["mode"])

        if completion_type is LLMMode.CHAT:
            endpoint_url = urljoin(endpoint_url, "chat/completions")
            data["messages"] = [self._convert_prompt_message_to_dict(m, credentials) for m in prompt_messages]
        elif completion_type is LLMMode.COMPLETION:
            endpoint_url = urljoin(endpoint_url, "completions")
            data["prompt"] = prompt_messages[0].content
        else:
            raise ValueError("Unsupported completion type for model configuration.")

        # annotate tools with names, descriptions, etc.
        function_calling_type = credentials.get("function_calling_type", "no_call")
        formatted_tools = []
        if tools:
            if function_calling_type == "function_call":
                data["functions"] = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    }
                    for tool in tools
                ]
            elif function_calling_type == "tool_call":
                data["tool_choice"] = "auto"

                for tool in tools:
                    formatted_tools.append(PromptMessageFunction(function=tool).model_dump())

                data["tools"] = formatted_tools

        if stop:
            data["stop"] = stop

        if user:
            data["user"] = user

        response = requests.post(endpoint_url, headers=headers, json=data, timeout=(10, 300), stream=stream)

        if response.encoding is None or response.encoding == "ISO-8859-1":
            response.encoding = "utf-8"

        if response.status_code != 200:
            raise InvokeError(f"API request failed with status code {response.status_code}: {response.text}")

        if stream:
            return self._handle_generate_stream_response(model, credentials, response, prompt_messages)

        return self._handle_generate_response(model, credentials, response, prompt_messages)

    def _create_final_llm_result_chunk(
        self,
        index: int,
        message: AssistantPromptMessage,
        finish_reason: str,
        usage: dict,
        model: str,
        prompt_messages: list[PromptMessage],
        credentials: dict,
        full_content: str,
    ) -> LLMResultChunk:
        # calculate num tokens
        prompt_tokens = usage and usage.get("prompt_tokens")
        if prompt_tokens is None:
            prompt_tokens = self._num_tokens_from_string(text=prompt_messages[0].content)
        completion_tokens = usage and usage.get("completion_tokens")
        if completion_tokens is None:
            completion_tokens = self._num_tokens_from_string(text=full_content)

        # transform usage
        usage = self._calc_response_usage(model, credentials, prompt_tokens, completion_tokens)

        return LLMResultChunk(
            model=model,
            delta=LLMResultChunkDelta(index=index, message=message, finish_reason=finish_reason, usage=usage),
        )

    def _handle_generate_stream_response(
        self, model: str, credentials: dict, response: requests.Response, prompt_messages: list[PromptMessage]
    ) -> Generator:
        """
        Handle llm stream response

        :param model: model name
        :param credentials: model credentials
        :param response: streamed response
        :param prompt_messages: prompt messages
        :return: llm response chunk generator
        """
        chunk_index = 0
        full_assistant_content = ""
        full_reasoning_content = ""
        tools_calls: list[AssistantPromptMessage.ToolCall] = []
        finish_reason = None
        usage = None
        # delimiter for stream response, need unicode_escape
        delimiter = credentials.get("stream_mode_delimiter", "\n\n")
        delimiter = codecs.decode(delimiter, "unicode_escape")
        for chunk in response.iter_lines(decode_unicode=True, delimiter=delimiter):
            chunk = chunk.strip()
            if chunk:
                # ignore sse comments
                if chunk.startswith(":"):
                    continue
                decoded_chunk = chunk.strip().removeprefix("data:").lstrip()
                if decoded_chunk == "[DONE]":  # Some provider returns "data: [DONE]"
                    continue

                try:
                    chunk_json: dict = TypeAdapter(dict[str, Any]).validate_json(decoded_chunk)
                # stream ended
                except ValidationError:
                    yield self._create_final_llm_result_chunk(
                        index=chunk_index + 1,
                        message=AssistantPromptMessage(content=""),
                        finish_reason="Non-JSON encountered.",
                        usage=usage,
                        model=model,
                        credentials=credentials,
                        prompt_messages=prompt_messages,
                        full_content=full_assistant_content,
                    )
                    break
                # handle the error here. for issue #11629
                if chunk_json.get("error") and chunk_json.get("choices") is None:
                    raise ValueError(chunk_json.get("error"))

                if chunk_json:  # noqa: SIM102
                    if u := chunk_json.get("usage"):
                        usage = u
                if not chunk_json or len(chunk_json["choices"]) == 0:
                    continue

                choice = chunk_json["choices"][0]
                finish_reason = chunk_json["choices"][0].get("finish_reason")
                chunk_index += 1

                if "delta" in choice:
                    delta = choice["delta"]
                    
                    # Simple field separation approach - let backend handle reasoning_format
                    delta_content = delta.get("content", "")
                    reasoning_content_for_message = delta.get("reasoning_content")

                    assistant_message_tool_calls = None

                    if "tool_calls" in delta and credentials.get("function_calling_type", "no_call") == "tool_call":
                        assistant_message_tool_calls = delta.get("tool_calls", None)
                    elif (
                        "function_call" in delta
                        and credentials.get("function_calling_type", "no_call") == "function_call"
                    ):
                        assistant_message_tool_calls = [
                            {"id": "tool_call_id", "type": "function", "function": delta.get("function_call", {})}
                        ]

                    # extract tool calls from response
                    if assistant_message_tool_calls:
                        tool_calls = self._extract_response_tool_calls(assistant_message_tool_calls)
                        _increase_tool_call(tool_calls, tools_calls)

                    # Skip if both content and reasoning_content are empty
                    if not delta_content and not reasoning_content_for_message:
                        continue

                    # Create assistant message (compatible with both approaches)
                    assistant_prompt_message = AssistantPromptMessage(
                        content=delta_content,
                        reasoning_content=reasoning_content_for_message
                    )

                    full_assistant_content += delta_content if delta_content else ""
                    full_reasoning_content += reasoning_content_for_message if reasoning_content_for_message else ""

                elif "text" in choice:
                    choice_text = choice.get("text", "")
                    if choice_text == "":
                        continue

                    # transform assistant message to prompt message
                    assistant_prompt_message = AssistantPromptMessage(content=choice_text)
                    full_assistant_content += choice_text
                else:
                    continue

                yield LLMResultChunk(
                    model=model,
                    delta=LLMResultChunkDelta(
                        index=chunk_index,
                        message=assistant_prompt_message,
                    ),
                )

            chunk_index += 1

        if tools_calls:
            yield LLMResultChunk(
                model=model,
                delta=LLMResultChunkDelta(
                    index=chunk_index,
                    message=AssistantPromptMessage(tool_calls=tools_calls, content=""),
                ),
            )

        # For token calculation, include reasoning content if present
        full_content_for_tokens = full_assistant_content
        if full_reasoning_content:
            full_content_for_tokens = f"<think>{full_reasoning_content}</think>{full_assistant_content}"
            
        yield self._create_final_llm_result_chunk(
            index=chunk_index,
            message=AssistantPromptMessage(content=""),
            finish_reason=finish_reason,
            usage=usage,
            model=model,
            credentials=credentials,
            prompt_messages=prompt_messages,
            full_content=full_content_for_tokens,
        )

    def _handle_generate_response(
        self,
        model: str,
        credentials: dict,
        response: requests.Response,
        prompt_messages: list[PromptMessage],
    ) -> LLMResult:
        response_json: dict = response.json()

        completion_type = LLMMode.value_of(credentials["mode"])

        output = response_json["choices"][0]
        message_id = response_json.get("id")

        response_content = ""
        tool_calls = None
        function_calling_type = credentials.get("function_calling_type", "no_call")
        if completion_type is LLMMode.CHAT:
            response_content = output.get("message", {})["content"]
            if function_calling_type == "tool_call":
                tool_calls = output.get("message", {}).get("tool_calls")
            elif function_calling_type == "function_call":
                tool_calls = output.get("message", {}).get("function_call")

        elif completion_type is LLMMode.COMPLETION:
            response_content = output["text"]

        assistant_message = AssistantPromptMessage(content=response_content, tool_calls=[])

        if tool_calls:
            if function_calling_type == "tool_call":
                assistant_message.tool_calls = self._extract_response_tool_calls(tool_calls)
            elif function_calling_type == "function_call":
                assistant_message.tool_calls = [self._extract_response_function_call(tool_calls)]

        usage = response_json.get("usage")
        if usage:
            # transform usage
            prompt_tokens = usage["prompt_tokens"]
            completion_tokens = usage["completion_tokens"]
        else:
            # calculate num tokens
            assert prompt_messages[0].content is not None
            prompt_tokens = self._num_tokens_from_string(model, prompt_messages[0].content)
            assert assistant_message.content is not None
            completion_tokens = self._num_tokens_from_string(model, assistant_message.content)

        # transform usage
        usage = self._calc_response_usage(model, credentials, prompt_tokens, completion_tokens)

        # transform response
        result = LLMResult(
            id=message_id,
            model=response_json["model"],
            message=assistant_message,
            usage=usage,
        )

        return result

    def _convert_prompt_message_to_dict(self, message: PromptMessage, credentials: Optional[dict] = None) -> dict:
        """
        Convert PromptMessage to dict for OpenAI API format
        """
        message_dict = {}
        if isinstance(message, UserPromptMessage):
            message = cast(UserPromptMessage, message)
            if isinstance(message.content, str):
                message_dict = {"role": "user", "content": message.content}
            else:
                sub_messages = []
                for message_content in message.content or []:
                    if message_content.type == PromptMessageContentType.TEXT:
                        message_content = cast(PromptMessageContent, message_content)
                        sub_message_dict = {
                            "type": "text",
                            "text": message_content.data,
                        }
                        sub_messages.append(sub_message_dict)
                    elif message_content.type == PromptMessageContentType.IMAGE:
                        message_content = cast(ImagePromptMessageContent, message_content)
                        sub_message_dict = {
                            "type": "image_url",
                            "image_url": {
                                "url": message_content.data,
                                "detail": message_content.detail.value,
                            },
                        }
                        sub_messages.append(sub_message_dict)

                message_dict = {"role": "user", "content": sub_messages}
        elif isinstance(message, AssistantPromptMessage):
            message = cast(AssistantPromptMessage, message)
            message_dict = {"role": "assistant", "content": message.content}
            if message.tool_calls:
                function_calling_type = credentials.get("function_calling_type", "no_call")
                if function_calling_type == "tool_call":
                    message_dict["tool_calls"] = [tool_call.dict() for tool_call in message.tool_calls]
                elif function_calling_type == "function_call":
                    function_call = message.tool_calls[0]
                    message_dict["function_call"] = {
                        "name": function_call.function.name,
                        "arguments": function_call.function.arguments,
                    }
        elif isinstance(message, SystemPromptMessage):
            message = cast(SystemPromptMessage, message)
            message_dict = {"role": "system", "content": message.content}
        elif isinstance(message, ToolPromptMessage):
            message = cast(ToolPromptMessage, message)
            function_calling_type = credentials.get("function_calling_type", "no_call")
            if function_calling_type == "tool_call":
                message_dict = {
                    "role": "tool",
                    "content": message.content,
                    "tool_call_id": message.tool_call_id,
                }
            elif function_calling_type == "function_call":
                message_dict = {
                    "role": "function",
                    "content": message.content,
                    "name": message.tool_call_id,
                }
        else:
            raise ValueError(f"Got unknown type {message}")

        if message.name and message_dict.get("role", "") != "tool":
            message_dict["name"] = message.name

        return message_dict

    def _num_tokens_from_string(
        self,
        text: Union[str, list[PromptMessageContent]],
        tools: Optional[list[PromptMessageTool]] = None,
    ) -> int:
        """
        Approximate num tokens for model with gpt2 tokenizer.

        :param text: prompt text
        :param tools: tools for tool calling
        :return: number of tokens
        """
        if isinstance(text, str):
            full_text = text
        else:
            full_text = ""
            for message_content in text:
                if message_content.type == PromptMessageContentType.TEXT:
                    message_content = cast(PromptMessageContent, message_content)
                    full_text += message_content.data

        num_tokens = self._get_num_tokens_by_gpt2(full_text)

        if tools:
            num_tokens += self._num_tokens_for_tools(tools)

        return num_tokens

    def _num_tokens_from_messages(
        self,
        messages: list[PromptMessage],
        tools: Optional[list[PromptMessageTool]] = None,
        credentials: Optional[dict] = None,
    ) -> int:
        """
        Approximate num tokens with GPT2 tokenizer.
        """

        tokens_per_message = 3
        tokens_per_name = 1

        num_tokens = 0
        messages_dict = [self._convert_prompt_message_to_dict(m, credentials) for m in messages]
        for message in messages_dict:
            num_tokens += tokens_per_message
            for key, value in message.items():
                # Cast str(value) in case the message value is not a string
                # This occurs with function messages
                # TODO: The current token calculation method for the image type is not implemented,
                #  which need to download the image and then get the resolution for calculation,
                #  and will increase the request delay
                if isinstance(value, list):
                    text = ""
                    for item in value:
                        if isinstance(item, dict) and item["type"] == "text":
                            text += item["text"]

                    value = text

                if key == "tool_calls":
                    for tool_call in value or []:
                        for t_key, t_value in tool_call.items():
                            num_tokens += self._get_num_tokens_by_gpt2(t_key)
                            if t_key == "function":
                                for f_key, f_value in t_value.items():
                                    num_tokens += self._get_num_tokens_by_gpt2(f_key)
                                    num_tokens += self._get_num_tokens_by_gpt2(f_value)
                            else:
                                num_tokens += self._get_num_tokens_by_gpt2(t_key)
                                num_tokens += self._get_num_tokens_by_gpt2(t_value)
                else:
                    num_tokens += self._get_num_tokens_by_gpt2(str(value))

                if key == "name":
                    num_tokens += tokens_per_name

        # every reply is primed with <im_start>assistant
        num_tokens += 3

        if tools:
            num_tokens += self._num_tokens_for_tools(tools)

        return num_tokens

    def _num_tokens_for_tools(self, tools: list[PromptMessageTool]) -> int:
        """
        Calculate num tokens for tool calling with tiktoken package.

        :param tools: tools for tool calling
        :return: number of tokens
        """
        num_tokens = 0
        for tool in tools:
            num_tokens += self._get_num_tokens_by_gpt2("type")
            num_tokens += self._get_num_tokens_by_gpt2("function")
            num_tokens += self._get_num_tokens_by_gpt2("function")

            # calculate num tokens for function object
            num_tokens += self._get_num_tokens_by_gpt2("name")
            if hasattr(tool, "name"):
                num_tokens += self._get_num_tokens_by_gpt2(tool.name)
            num_tokens += self._get_num_tokens_by_gpt2("description")
            if hasattr(tool, "description"):
                num_tokens += self._get_num_tokens_by_gpt2(tool.description)
            if hasattr(tool, "parameters"):
                parameters = tool.parameters
                num_tokens += self._get_num_tokens_by_gpt2("parameters")
                if "title" in parameters:
                    num_tokens += self._get_num_tokens_by_gpt2("title")
                    num_tokens += self._get_num_tokens_by_gpt2(parameters.get("title"))
                num_tokens += self._get_num_tokens_by_gpt2("type")
                num_tokens += self._get_num_tokens_by_gpt2(parameters.get("type"))
                if "properties" in parameters:
                    num_tokens += self._get_num_tokens_by_gpt2("properties")
                    for key, value in parameters.get("properties", {}).items():
                        num_tokens += self._get_num_tokens_by_gpt2(key)
                        for field_key, field_value in value.items():
                            num_tokens += self._get_num_tokens_by_gpt2(field_key)
                            if field_key == "enum":
                                for enum_field in field_value:
                                    num_tokens += 3
                                    num_tokens += self._get_num_tokens_by_gpt2(enum_field)
                            else:
                                num_tokens += self._get_num_tokens_by_gpt2(field_key)
                                num_tokens += self._get_num_tokens_by_gpt2(str(field_value))
                if "required" in parameters:
                    num_tokens += self._get_num_tokens_by_gpt2("required")
                    for required_field in parameters["required"]:
                        num_tokens += 3
                        num_tokens += self._get_num_tokens_by_gpt2(required_field)

        return num_tokens

    def _extract_response_tool_calls(self, response_tool_calls: list[dict]) -> list[AssistantPromptMessage.ToolCall]:
        """
        Extract tool calls from response

        :param response_tool_calls: response tool calls
        :return: list of tool calls
        """
        tool_calls = []
        if response_tool_calls:
            for response_tool_call in response_tool_calls:
                if not response_tool_call.get("function"):
                    continue
                function = AssistantPromptMessage.ToolCall.ToolCallFunction(
                    name=response_tool_call.get("function", {}).get("name", ""),
                    arguments=response_tool_call.get("function", {}).get("arguments", ""),
                )

                tool_call = AssistantPromptMessage.ToolCall(
                    id=response_tool_call.get("id", ""),
                    type=response_tool_call.get("type", ""),
                    function=function,
                )
                tool_calls.append(tool_call)

        return tool_calls

    def _extract_response_function_call(self, response_function_call) -> AssistantPromptMessage.ToolCall | None:
        """
        Extract function call from response

        :param response_function_call: response function call
        :return: tool call
        """
        tool_call = None
        if response_function_call:
            function = AssistantPromptMessage.ToolCall.ToolCallFunction(
                name=response_function_call.get("name", ""),
                arguments=response_function_call.get("arguments", ""),
            )

            tool_call = AssistantPromptMessage.ToolCall(
                id=response_function_call.get("id", ""),
                type="function",
                function=function,
            )

        return tool_call
