import json

from collections.abc import Mapping, Sequence
from dataclasses import is_dataclass
from typing import Any

from pydantic import BaseModel, TypeAdapter
from pydantic_core import to_jsonable_python


def serialize_ag_ui_jsonable_python(value: Any, *, exclude_none: bool = False) -> Any:
    """
    以模型别名序列化 AG-UI / Pydantic 对象

    :param value: 待序列化对象
    :param exclude_none: 是否排除空值
    :return:
    """
    if isinstance(value, BaseModel):
        return value.model_dump(mode='json', by_alias=True, exclude_none=exclude_none)
    if is_dataclass(value) and not isinstance(value, type):
        return TypeAdapter(type(value)).dump_python(value, mode='json', by_alias=True, exclude_none=exclude_none)
    if isinstance(value, Mapping):
        return {
            key: serialize_ag_ui_jsonable_python(item, exclude_none=exclude_none)
            for key, item in value.items()
            if not (exclude_none and item is None)
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [serialize_ag_ui_jsonable_python(item, exclude_none=exclude_none) for item in value]
    if isinstance(value, set | frozenset):
        return [serialize_ag_ui_jsonable_python(item, exclude_none=exclude_none) for item in value]
    return to_jsonable_python(value)


def serialize_ag_ui_json(value: Any, *, exclude_none: bool = False) -> str:
    """
    将 AG-UI / Pydantic 对象序列化为 JSON 字符串

    :param value: 待序列化对象
    :param exclude_none: 是否排除空值
    :return:
    """
    return json.dumps(
        serialize_ag_ui_jsonable_python(value, exclude_none=exclude_none),
        ensure_ascii=False,
        separators=(',', ':'),
    )
