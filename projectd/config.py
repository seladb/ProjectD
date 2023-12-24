import json
from dataclasses import dataclass
from enum import Enum

from dacite import Config as DaciteConfig
from dacite import from_dict


class TemplateType(Enum):
    FILE = "file"
    CLASS = "class"
    ENUMS = "enums"


@dataclass
class TemplateConfig:
    template_type: TemplateType
    template: str
    output_file: str
    class_link_template: str


@dataclass
class Config:
    input_dirs: list[str]
    output_dir: str
    defines: list[str]
    template_dir: str
    code_template: str
    auto_escape: bool
    templates: list[TemplateConfig]


def get_config() -> Config:
    with open("config.json") as config_file:
        config_json = json.load(config_file)

    return from_dict(data_class=Config, data=config_json, config=DaciteConfig(cast=[TemplateType]))  # type: ignore[no-any-return]
