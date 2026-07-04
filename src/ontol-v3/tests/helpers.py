from __future__ import annotations

from uml_dsl.tdl_build import build_diagram
from uml_dsl.tdl_lexer import lex
from uml_dsl.tdl_parser import parse_tdl


CLASS = "\u041a\u041b\u0410\u0421\u0421"
INTERFACE = "\u0418\u041d\u0422\u0415\u0420\u0424\u0415\u0419\u0421"
DATA_TYPE = "\u0422\u0418\u041f_\u0414\u0410\u041d\u041d\u042b\u0425"
ENUM = "\u041f\u0415\u0420\u0415\u0427\u0418\u0421\u041b\u0415\u041d\u0418\u0415"
END = "\u041a\u041e\u041d\u0415\u0426"
ABSTRACT = "\u0410\u0411\u0421\u0422\u0420\u0410\u041a\u0422\u041d\u042b\u0419"
ATTRS = "\u0410\u0422\u0420\u0418\u0411\u0423\u0422\u042b"
OPS = "\u041e\u041f\u0415\u0420\u0410\u0426\u0418\u0418"
GENERALIZATION = "\u041e\u0411\u041e\u0411\u0429\u0415\u041d\u0418\u0415"
ASSOCIATION = "\u0410\u0421\u0421\u041e\u0426\u0418\u0410\u0426\u0418\u042f"
COMPOSITION = "\u041a\u041e\u041c\u041f\u041e\u0417\u0418\u0426\u0418\u042f"
AGGREGATION = "\u0410\u0413\u0420\u0415\u0413\u0410\u0426\u0418\u042f"
DEPENDENCY = "\u0417\u0410\u0412\u0418\u0421\u0418\u041c\u041e\u0421\u0422\u042c"
REALIZATION = "\u0420\u0415\u0410\u041b\u0418\u0417\u0410\u0426\u0418\u042f"
NAME = "\u0418\u041c\u042f"


def class_block(name: str, body: str = "", *, abstract: bool = False) -> str:
    suffix = f" {ABSTRACT}" if abstract else ""
    body_text = f"\n{body.rstrip()}" if body.strip() else ""
    return f"{CLASS} {name}{suffix}{body_text}\n{END} {CLASS}\n"


def interface_block(name: str, body: str = "") -> str:
    body_text = f"\n{body.rstrip()}" if body.strip() else ""
    return f"{INTERFACE} {name}{body_text}\n{END} {INTERFACE}\n"


def data_type_block(name: str, body: str = "") -> str:
    body_text = f"\n{body.rstrip()}" if body.strip() else ""
    return f"{DATA_TYPE} {name}{body_text}\n{END} {DATA_TYPE}\n"


def enum_block(name: str, values: list[str]) -> str:
    return f"{ENUM} {name}\n" + "\n".join(values) + f"\n{END} {ENUM}\n"


def parse_document(tdl: str):
    return parse_tdl(lex(tdl))


def build(tdl: str):
    return build_diagram(parse_document(tdl))


def complete_graph_tdl(names: str) -> str:
    import itertools

    body = "".join(class_block(name) for name in names)
    edges = "".join(
        f"{ASSOCIATION} {left} -- {right}\n"
        for left, right in itertools.combinations(names, 2)
    )
    return body + edges
