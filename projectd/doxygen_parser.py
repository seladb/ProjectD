import os
import re
from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property
from typing import Any, Callable

from cxxheaderparser.simple import ClassScope, NamespaceScope
from cxxheaderparser.types import AnonymousName, EnumDecl, Enumerator, Field, Method, Parameter


def remove_comment_chars_from_line(line: str) -> str:
    line = line.strip()
    if line.startswith("//!<") or line.startswith("///<"):
        line = line[4:]
    elif line.startswith("///"):
        line = line[3:]
    else:
        line = line.replace("/**", "").replace("/*!", "").replace("/*", "").replace("*/", "")

    return line.strip("*")


def preprocess_lines(lines: list[str]) -> list[str]:
    result = []
    cur_line = None
    block_type = None

    chars_from_original_line = 0

    for line in lines:
        original_line = line

        if block_type == "verbatim":
            if "\\endverbatim" in line or "@endverbatim" in line:
                block_type = None
                line_without_end_verbatim = line.replace("\\endverbatim", "").replace("@endverbatim", "")[
                    chars_from_original_line:
                ]
                result.append("\n".join([cur_line, line_without_end_verbatim]))
                cur_line = None
            else:
                verbatim_line = line[chars_from_original_line:]
                cur_line = "\n".join([cur_line, verbatim_line]) if cur_line else verbatim_line

            continue

        if block_type == "code":
            if "\\endcode" in line or "@endcode" in line:
                block_type = None
                result.append(cur_line)
                cur_line = None
            else:
                code_line = line[chars_from_original_line:]
                cur_line = "\n".join([cur_line, code_line]) if cur_line else code_line

            continue

        stripped_line = remove_comment_chars_from_line(line)
        fully_stripped_line = stripped_line.lstrip()

        if block_type == "other":
            if not fully_stripped_line or fully_stripped_line.startswith(("\\", "@", "-", "+", "*")):
                block_type = None
                result.append(cur_line)
                cur_line = None
            else:
                cur_line = " ".join([cur_line, fully_stripped_line]) if cur_line else fully_stripped_line
                continue

        if block_type == "list":
            if not fully_stripped_line or fully_stripped_line.startswith(("\\", "@", "-", "+", "*")):
                block_type = None
                result.append(cur_line)
                cur_line = None
            else:
                cur_line = " ".join([cur_line, stripped_line]) if cur_line else stripped_line
                continue

        if not fully_stripped_line:
            if result:
                result.append("@blank")
            continue

        if fully_stripped_line.startswith(("\\verbatim", "@verbatim")):
            block_type = "verbatim"
            chars_from_original_line = max(original_line.find("@verbatim"), original_line.find("\\verbatim"))
            cur_line = fully_stripped_line
        elif fully_stripped_line.startswith(("\\code", "@code")):
            block_type = "code"
            chars_from_original_line = max(original_line.find("@code"), original_line.find("\\code"))
            cur_line = fully_stripped_line
        elif fully_stripped_line.startswith(("-", "+", "*")):
            block_type = "list"
            cur_line = f"@li {stripped_line}"
        # elif fully_stripped_line.startswith(("\\", "@")):
        else:
            block_type = "other"
            cur_line = fully_stripped_line

    if cur_line:
        result.append(cur_line)

    return result


def get_keyword_and_rest_of_line(line: str) -> tuple[str, str]:
    if line.startswith(("\\", "@")):
        keyword_and_rest_of_line = re.split(" |\n", line, 1)
        rest_of_line = keyword_and_rest_of_line[1] if len(keyword_and_rest_of_line) > 1 else ""
        return keyword_and_rest_of_line[0][1:], rest_of_line

    return "", line


@dataclass
class TextBlock:
    text: str


class CodeBlock(TextBlock):
    pass


class VerbatimBlock(TextBlock):
    pass


DocBlock = list[TextBlock] | list[str]


@dataclass
class CommandDoc:
    name: str
    doc: DocBlock = field(default_factory=list)


def process_lines(lines: list[str]) -> list[CommandDoc]:
    lines = preprocess_lines(lines)

    result = []
    empty_command = CommandDoc(name="")
    cur_command = empty_command

    for line in lines:
        keyword, rest_of_line = get_keyword_and_rest_of_line(line)

        if not keyword:
            empty_command.doc.append(TextBlock(text=rest_of_line))
            continue

        match keyword:
            case "blank":
                if cur_command not in result:
                    result.append(cur_command)
                cur_command = empty_command
            case "verbatim":
                cur_command.doc.append(VerbatimBlock(text=rest_of_line))
            case "code":
                cur_command.doc.append(CodeBlock(text=rest_of_line))
            case "li":
                cur_command.doc.append(TextBlock(text=rest_of_line))
            case _:
                if cur_command not in result:
                    result.append(cur_command)
                cur_command = CommandDoc(name=keyword)
                if rest_of_line:
                    cur_command.doc.append(TextBlock(text=rest_of_line))

    if cur_command not in result:
        result.append(cur_command)

    return result


class Direction(str, Enum):
    IN = "in"
    OUT = "out"
    INOUT = "in,out"


@dataclass
class Param:
    name: str
    desc: DocBlock
    param_type: str
    direction: Direction


@dataclass
class EntityDoc:
    desc: DocBlock | None
    brief: DocBlock | None
    deprecated: DocBlock | None
    todo: DocBlock | None

    @classmethod
    def _from_comment(cls, doxygen: str | None) -> tuple[dict[str, Any], list[CommandDoc]]:
        commands_and_data: list[CommandDoc] = []
        if doxygen:
            commands_and_data = process_lines(doxygen.splitlines())

        kwargs = {
            "brief": next((cmd.doc for cmd in commands_and_data if cmd.name == "brief"), None),
            "desc": next((cmd.doc for cmd in commands_and_data if cmd.name == ""), None),
            "deprecated": next((cmd.doc for cmd in commands_and_data if cmd.name == "deprecated"), None),
            "todo": next((cmd.doc for cmd in commands_and_data if cmd.name == "todo"), None),
        }
        return kwargs, commands_and_data

    @classmethod
    def _is_public_attribute_or_method(cls, class_doc: "ClassDoc", attr_or_method_name: str) -> bool:
        return any(attr_or_method_name == public_method.name for public_method in class_doc.public_methods) or any(
            attr_or_method_name == public_attr.name for public_attr in class_doc.public_attributes
        )

    @classmethod
    def _update_text_block(
        cls,
        text_block: str,
        namespace_docs: dict[str, "NamespaceDoc"],
        cur_namespace: str,
        class_link: Callable[[str, str, str | None], str],
    ) -> str:
        text_block_str = str(text_block)
        index_of_first_non_whitespace = len(text_block_str) - len(text_block_str.lstrip())
        prefix = text_block_str[:index_of_first_non_whitespace]
        words = []
        for word in text_block_str.split():
            if word in ["@ref", "\\ref"]:
                continue

            namespace = None
            klass = None
            method = None

            stripped_word = re.sub(r"^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$", "", word)
            split_word = re.split(r"::|#", stripped_word)
            if len(split_word) == 1:
                if split_word[0] in namespace_docs:
                    namespace = split_word[0]
                elif split_word[0] in namespace_docs[cur_namespace].classes:
                    namespace = cur_namespace
                    klass = split_word[0]
            elif len(split_word) == 2:
                split_word[1] = split_word[1].replace("()", "")
                if split_word[0] in namespace_docs and split_word[1] in namespace_docs[split_word[0]].classes:
                    namespace = split_word[0]
                    klass = split_word[1]
                elif split_word[0] in namespace_docs[cur_namespace].classes and cls._is_public_attribute_or_method(
                    namespace_docs[cur_namespace].classes[split_word[0]], split_word[1]
                ):
                    namespace = cur_namespace
                    klass = split_word[0]
                    method = split_word[1]
            elif len(split_word) == 3 and (
                split_word[0] in namespace_docs
                and split_word[1] in namespace_docs[split_word[0]].classes
                and cls._is_public_attribute_or_method(
                    namespace_docs[split_word[0]].classes[split_word[1]], split_word[2]
                )
            ):
                namespace = split_word[0]
                klass = split_word[1]
                method = split_word[2]

            if namespace is not None or klass is not None or method is not None:
                word_with_link = word.replace(stripped_word, class_link(namespace, klass, method))
                words.append(word_with_link)
            else:
                words.append(word)

        return prefix + " ".join(words)

    def _update_doc_block(
        self,
        block: DocBlock,
        namespace_docs: dict[str, "NamespaceDoc"],
        cur_namespace: str,
        code_template: Callable[[str], str],
        class_link: Callable[[str, str, str | None], str],
    ) -> list[str]:
        result = []
        for line in block:
            if isinstance(line, (CodeBlock, VerbatimBlock)):
                result.append(code_template(line.text))
            elif isinstance(line, TextBlock):
                result.append(self._update_text_block(line.text, namespace_docs, cur_namespace, class_link))

        return result

    def post_process(
        self,
        namespace_docs: dict[str, "NamespaceDoc"],
        cur_namespace: str,
        code_template: Callable[[str], str],
        class_link: Callable[[str, str, str | None], str],
    ):
        if self.brief:
            self.brief = self._update_doc_block(self.brief, namespace_docs, cur_namespace, code_template, class_link)
        if self.desc:
            self.desc = self._update_doc_block(self.desc, namespace_docs, cur_namespace, code_template, class_link)


@dataclass
class NamedEntityDoc(EntityDoc):
    name: str

    def __repr__(self):
        return self.name


@dataclass
class MethodDoc(NamedEntityDoc):
    params: list[Param]
    static: bool
    inline: bool
    const: bool
    volatile: bool
    constructor: bool
    explicit: bool
    default: bool
    deleted: bool
    destructor: bool
    pure_virtual: bool
    virtual: bool
    final: bool
    override: bool
    returns: DocBlock | None = None
    return_type: str | None = None

    @classmethod
    def parse_param(cls, param_doc: CommandDoc, params: list[Parameter]) -> Param | None:
        param_pattern = r"^param(?:\[(in|out|inout)\])?$"

        if not param_doc.doc:
            return None

        match = re.match(param_pattern, param_doc.name)

        if not match:
            return None

        direction_from_regex = match.group(1)
        if direction_from_regex == "inout":
            direction_from_regex = "in,out"

        direction = Direction(direction_from_regex) if direction_from_regex else Direction.IN

        try:
            param_name, param_desc = param_doc.doc[0].text.split(" ", 1)
        except ValueError:
            return None

        if param := next((param for param in params if param.name == param_name), None):
            param_desc = [TextBlock(text=param_desc)] + param_doc.doc[1:]
            return Param(name=param_name, desc=param_desc, direction=direction, param_type=param.type.format())

        return None

    @classmethod
    def parse(cls, method: Method) -> "MethodDoc | None":
        kwargs, commands_and_data = super()._from_comment(method.doxygen)
        kwargs["name"] = method.name.format()
        params = []

        kwargs["returns"] = next((cmd.doc for cmd in commands_and_data if cmd.name in ["return", "returns"]), None)

        param_docs = [cmd for cmd in commands_and_data if cmd.name.startswith("param")]
        for param_doc in param_docs:
            if param := cls.parse_param(param_doc, method.parameters):
                params.append(param)

        kwargs["params"] = params
        if method.return_type:
            kwargs["return_type"] = method.return_type.format()

        for attr in [
            "static",
            "inline",
            "const",
            "volatile",
            "constructor",
            "explicit",
            "default",
            "deleted",
            "destructor",
            "pure_virtual",
            "virtual",
            "final",
            "override",
        ]:
            kwargs[attr] = getattr(method, attr)

        return cls(**kwargs)

    def post_process(
        self,
        namespace_docs: dict[str, "NamespaceDoc"],
        cur_namespace: str,
        code_template: Callable[[str], str],
        class_link: Callable[[str, str, str | None], str],
    ):
        super().post_process(namespace_docs, cur_namespace, code_template, class_link)

        for param in self.params:
            param.desc = self._update_doc_block(param.desc, namespace_docs, cur_namespace, code_template, class_link)

        if self.returns:
            self.returns = self._update_doc_block(
                self.returns, namespace_docs, cur_namespace, code_template, class_link
            )


@dataclass
class AttributeDoc(NamedEntityDoc):
    attribute_type: str

    @classmethod
    def parse(cls, field_scope: Field) -> "AttributeDoc":
        kwargs, _ = cls._from_comment(field_scope.doxygen)

        return cls(name=field_scope.name, attribute_type=field_scope.type.format(), **kwargs)


@dataclass
class EnumeratorDoc(NamedEntityDoc):
    value: str | None

    @classmethod
    def parse(cls, enumerator: Enumerator) -> "EnumeratorDoc":
        kwargs, _ = super()._from_comment(enumerator.doxygen)
        kwargs["value"] = enumerator.value.format() if enumerator.value else None
        kwargs["name"] = enumerator.name
        return cls(**kwargs)


@dataclass
class EnumDoc(NamedEntityDoc):
    values: list[EnumeratorDoc]

    @classmethod
    def parse(cls, enum_decl: EnumDecl) -> "EnumDoc | None":
        kwargs, commands_and_data = super()._from_comment(enum_decl.doxygen)

        enum_name = enum_decl.typename.segments[-1].format()
        for cmd in commands_and_data:
            if cmd.name == "enum" and cmd.doc:
                enum_name_and_desc = cmd.doc[0].text.split(" ", 1)
                if enum_name_and_desc[0] != enum_name:
                    return None
                if len(enum_name_and_desc) > 1:
                    kwargs["desc"] = cmd.doc + kwargs["desc"]

        kwargs["name"] = enum_name
        kwargs["values"] = [EnumeratorDoc.parse(val) for val in enum_decl.values]
        return cls(**kwargs)

    def post_process(
        self,
        namespace_docs: dict[str, "NamespaceDoc"],
        cur_namespace: str,
        code_template: Callable[[str], str],
        class_link: Callable[[str, str, str | None], str],
    ):
        super().post_process(namespace_docs, cur_namespace, code_template, class_link)

        for val in self.values:
            val.post_process(namespace_docs, cur_namespace, code_template, class_link)


@dataclass
class ClassDoc(NamedEntityDoc):
    class_key: str
    full_name: str
    public_methods: list[MethodDoc]
    public_attributes: list[AttributeDoc]
    public_enums: dict[str, EnumDoc]
    base_classes: list[str]
    namespace: "NamespaceDoc"

    @classmethod
    def parse(cls, class_scope: ClassScope, namespace: "NamespaceDoc") -> "ClassDoc | None":
        kwargs, commands_and_data = super()._from_comment(class_scope.class_decl.doxygen)

        name_segment = class_scope.class_decl.typename.segments[-1]
        if isinstance(name_segment, AnonymousName):
            return None

        class_name = name_segment.format()
        kwargs["name"] = class_name
        kwargs["full_name"] = "::".join(seg.format() for seg in class_scope.class_decl.typename.segments)

        for cmd in commands_and_data:
            if cmd.name == "class" and cmd.doc:
                class_name_and_desc = cmd.doc[0].text.split(" ", 1)
                if class_name_and_desc[0] != class_name:
                    return None
                if len(class_name_and_desc) > 1:
                    kwargs["desc"] = [TextBlock(text=class_name_and_desc[1])] + cmd.doc[1:] + kwargs["desc"]

        public_methods = []
        for method in class_scope.methods:
            if not method.doxygen or method.access != "public":
                continue
            if method_doc := MethodDoc.parse(method):
                public_methods.append(method_doc)

        public_attributes = []
        for fld in class_scope.fields:
            if fld.access == "public":
                public_attributes.append(AttributeDoc.parse(fld))

        public_enums = {}
        for enum in class_scope.enums:
            if enum.access == "public":
                enum_doc = EnumDoc.parse(enum)
                public_enums[enum_doc.name] = enum_doc

        kwargs["public_methods"] = public_methods
        kwargs["public_attributes"] = public_attributes
        kwargs["public_enums"] = public_enums
        kwargs["class_key"] = class_scope.class_decl.typename.classkey
        kwargs["base_classes"] = [
            base_class.typename.segments[-1].format() for base_class in class_scope.class_decl.bases
        ]
        kwargs["namespace"] = namespace

        return cls(**kwargs)

    def post_process(
        self,
        namespace_docs: dict[str, "NamespaceDoc"],
        cur_namespace: str,
        code_template: Callable[[str], str],
        class_link: Callable[[str, str, str | None], str],
    ):
        super().post_process(namespace_docs, cur_namespace, code_template, class_link)

        for public_method in self.public_methods:
            public_method.post_process(namespace_docs, cur_namespace, code_template, class_link)

        for public_attr in self.public_attributes:
            public_attr.post_process(namespace_docs, cur_namespace, code_template, class_link)

        for public_enum in self.public_enums.values():
            public_enum.post_process(namespace_docs, cur_namespace, code_template, class_link)

    @cached_property
    def inheritance_tree(self) -> list["ClassDoc"]:
        result = [self]
        for base_class in self.base_classes:
            if base_class not in self.namespace.classes:
                continue

            base_inheritance_tree = self.namespace.classes[base_class].inheritance_tree
            for cls in base_inheritance_tree:
                if cls not in result:
                    result.append(cls)

        return result


@dataclass
class NamespaceDoc(NamedEntityDoc):
    classes: dict[str, ClassDoc] = field(default_factory=dict)
    enums: dict[str, EnumDoc] = field(default_factory=dict)

    @classmethod
    def parse(cls, namespace_scope: NamespaceScope) -> "NamespaceDoc | None":
        kwargs, commands_and_data = super()._from_comment(namespace_scope.doxygen)

        if any(
            cmd.name == "namespace" and cmd.doc[0].text.split()[0] != namespace_scope.name for cmd in commands_and_data
        ):
            return None

        kwargs["name"] = namespace_scope.name
        return cls(**kwargs)

    def post_process(
        self,
        namespace_docs: dict[str, "NamespaceDoc"],
        cur_namespace: str,
        code_template: Callable[[str], str],
        class_link: Callable[[str, str, str | None], str],
    ):
        super().post_process(namespace_docs, cur_namespace, code_template, class_link)

        for enum in self.enums.values():
            enum.post_process(namespace_docs, cur_namespace, code_template, class_link)


@dataclass
class FileDoc(NamedEntityDoc):
    namespaces: dict[str, NamespaceDoc] = field(default_factory=dict)
    classes: dict[str, ClassDoc] = field(default_factory=dict)
    enums: dict[str, EnumDoc] = field(default_factory=dict)

    @classmethod
    def parse(cls, file_path: str) -> "FileDoc":
        file_name = os.path.basename(file_path)
        return cls(name=file_name, desc=[], brief=None, deprecated=None, todo=None)
