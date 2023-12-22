import re

from projectd.doxygen_parser.dataclasses import CommandDoc, DocElement


def _remove_comment_chars_from_line(line: str) -> str:
    line = line.strip()
    if line.startswith("//!<") or line.startswith("///<"):
        line = line[4:]
    elif line.startswith("///"):
        line = line[3:]
    else:
        line = line.replace("/**", "").replace("/*!", "").replace("/*", "").replace("*/", "")

    return line.strip("*")


def _preprocess_lines(lines: list[str]) -> list[str]:
    # ruff: noqa: C901
    result: list[str] = []
    cur_line = ""
    block_type = None

    chars_from_original_line = 0

    for line in lines:
        original_line = line

        if block_type == "verbatim":
            if "\\endverbatim" in line or "@endverbatim" in line:
                block_type = None
                if line_without_end_verbatim := line.replace("\\endverbatim", "").replace("@endverbatim", "")[
                    chars_from_original_line:
                ]:
                    cur_line = "\n".join([cur_line, line_without_end_verbatim])

                result.append(cur_line)
                cur_line = ""
            else:
                verbatim_line = line[chars_from_original_line:]
                cur_line = "\n".join([cur_line, verbatim_line]) if cur_line else verbatim_line

            continue

        if block_type == "code":
            if "\\endcode" in line or "@endcode" in line:
                block_type = None
                result.append(cur_line)
                cur_line = ""
            else:
                code_line = line[chars_from_original_line:]
                cur_line = "\n".join([cur_line, code_line]) if cur_line else code_line

            continue

        stripped_line = _remove_comment_chars_from_line(line)
        fully_stripped_line = stripped_line.lstrip()

        if block_type == "other":
            if not fully_stripped_line or fully_stripped_line.startswith(("\\", "@", "-", "+", "*")):
                block_type = None
                result.append(cur_line)
                cur_line = ""
            else:
                cur_line = " ".join([cur_line, fully_stripped_line]) if cur_line else fully_stripped_line
                continue

        if block_type == "list":
            if not fully_stripped_line or fully_stripped_line.startswith(("\\", "@", "-", "+", "*")):
                block_type = None
                result.append(cur_line)
                cur_line = ""
            else:
                cur_line = " ".join([cur_line, fully_stripped_line]) if cur_line else fully_stripped_line
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
        else:
            block_type = "other"
            cur_line = fully_stripped_line

    if cur_line:
        result.append(cur_line)

    return result


def _get_keyword_and_rest_of_line(line: str) -> tuple[str, str]:
    if line.startswith(("\\", "@")):
        keyword_and_rest_of_line = re.split(" |\n", line, maxsplit=1)
        rest_of_line = keyword_and_rest_of_line[1] if len(keyword_and_rest_of_line) > 1 else ""
        return keyword_and_rest_of_line[0][1:], rest_of_line

    return "", line


def process_lines(lines: list[str]) -> list[CommandDoc]:
    lines = _preprocess_lines(lines)

    commands = []
    anonymous_command = CommandDoc(name="")
    cur_command = anonymous_command

    for line in lines:
        if cur_command not in commands:
            commands.append(cur_command)

        keyword, rest_of_line = _get_keyword_and_rest_of_line(line)

        match keyword:
            case "blank":
                cur_command = anonymous_command
            case "":
                cur_command = anonymous_command
                cur_command.doc.elements.append(DocElement(text=rest_of_line, element_type="text"))
            case "verbatim":
                cur_command.doc.elements.append(DocElement(text=rest_of_line, element_type="verbatim"))
            case "code":
                cur_command.doc.elements.append(DocElement(text=rest_of_line, element_type="code"))
            case "li":
                cur_command.doc.elements.append(DocElement(text=rest_of_line, element_type="text"))
            case _:
                cur_command = CommandDoc(name=keyword)
                if rest_of_line:
                    cur_command.doc.elements.append(DocElement(text=rest_of_line, element_type="text"))

    if cur_command not in commands:
        commands.append(cur_command)

    return [command for command in commands if command.name or command.doc.elements]
