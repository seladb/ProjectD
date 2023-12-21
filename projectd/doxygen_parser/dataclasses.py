from dataclasses import dataclass, field
from typing import Iterator, Literal


@dataclass
class DocElement:
    text: str
    element_type: Literal["text", "code", "verbatim"]

    def __str__(self) -> str:
        return self.text


@dataclass
class DocBlock:
    elements: list[DocElement] = field(default_factory=list)

    def __iter__(self) -> Iterator:
        return iter(self.elements)


@dataclass
class CommandDoc:
    name: str
    doc: DocBlock = field(default_factory=DocBlock)
