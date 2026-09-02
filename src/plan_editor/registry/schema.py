from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class PortSpec:
    name: str
    port_type: str  # plan / motor / detector / number / string / bool / any


@dataclass
class NodeSchema:
    node_id: str
    title: str
    category: str
    inputs: list[PortSpec] = field(default_factory=list)
    outputs: list[PortSpec] = field(default_factory=list)
    params: dict = field(default_factory=dict)
    desc: str = ""
    param_pairs: tuple = ()       # e.g. ("motor","pos") → N expandable pair rows
    expandable_ports: bool = False # True → user can add/remove input ports
    expand_port_type: str = "plan" # type of ports created by the + button
    min_ports: int = 1             # minimum number of input ports (protects fixed ports)
    value_inputs: tuple = ()       # param names that get an optional wireable value port
    param_choices: dict = field(default_factory=dict)  # param_name → list[str] → renders QComboBox
    supports_csv:        bool = False  # show CSV import button (populates param_pairs from file)
    expand_output_ports: bool = False  # True → one output port per param_pair row
    hidden:              bool = False  # True → not shown in palette (auto-created nodes)
    title_param:         str  = ""    # if set, use params[title_param] as the header title
    inline_pairs:        bool = False  # True → render each param_pair as one row (two side-by-side fields)
    expand_port_name:    str  = ""    # if set, expanded ports use this label instead of "arg N"
