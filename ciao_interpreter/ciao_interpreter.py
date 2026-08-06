"""
CIAO Interpreter — полная реализация на основе правил именования
"""

import sys
import os
from typing import Dict, List, Optional, Any, Tuple
from collections import deque
from dataclasses import dataclass, field
import re
import random

# Добавляем путь к ontol-v3
_ontol_v3_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "src", "ontol-v3",
)
if _ontol_v3_path not in sys.path:
    sys.path.insert(0, _ontol_v3_path)

from uml_dsl.tdl_run import tdl_to_diagram


# ─── Вспомогательные типы данных ──────────────────────────────────────────

@dataclass
class Variable:
    name: str
    value: Any = None
    type_: str = ""
    initialized: bool = False


@dataclass
class Interface:
    name: str
    kind: str
    sort: str
    link: Optional[Tuple[str, str]] = None


@dataclass
class AutoObject:
    name: str
    class_name: str
    current_state: str
    variables: Dict[str, Variable] = field(default_factory=dict)
    interfaces: Dict[str, Interface] = field(default_factory=dict)
    states: Dict[str, List[Dict]] = field(default_factory=dict)


@dataclass
class Event:
    name: str
    target_object: str
    arguments: List[Any] = field(default_factory=list)


# ─── Парсер диаграммы CIAO ──────────────────────────────────────────────────

class CIAODiagramParser:
    """Парсер диаграммы CIAO на основе правил именования."""

    def __init__(self, diagram, debug: bool = False):
        self.diagram = diagram
        self.debug = debug

        self.auto_objects: Dict[str, Any] = {}
        self.variables: Dict[str, Any] = {}
        self.interfaces: Dict[str, Any] = {}
        self.states: Dict[str, Any] = {}
        self.transitions: Dict[str, Any] = {}
        self.triggers: Dict[str, Any] = {}
        self.effects: Dict[str, Any] = {}
        self.actions: Dict[str, Any] = {}
        self.calls: Dict[str, Any] = {}
        self.choices: Dict[str, Any] = {}
        self.directs: Dict[str, Any] = {}

        self.objects: Dict[str, AutoObject] = {}
        self.effect_implementations: Dict[str, Dict] = {}

    def parse(self) -> Dict[str, AutoObject]:
        self._classify_classes()

        if self.debug:
            print("\n=== Parsed Classifications ===")
            print(f"  Auto objects: {list(self.auto_objects.keys())}")
            print(f"  Interfaces: {list(self.interfaces.keys())}")
            print(f"  States: {list(self.states.keys())}")
            print(f"  Transitions: {list(self.transitions.keys())}")
            print(f"  Triggers: {list(self.triggers.keys())}")
            print(f"  Effects: {list(self.effects.keys())}")

        for name, cls in self.auto_objects.items():
            obj = self._parse_auto_object(name, cls)
            self.objects[name] = obj

        self._collect_effect_implementations()

        if self.debug:
            print("\n=== Parsed Objects ===")
            for name, obj in self.objects.items():
                print(f"  {name} -> {obj.name}")
                print(f"    States: {list(obj.states.keys())}")
                for state, transitions in obj.states.items():
                    for t in transitions:
                        print(
                            f"      {state}: {t.get('trigger')} -> {t.get('target', t.get('target1', '?'))} (type: {t.get('type')})")
                print(f"    Interfaces:")
                for iface in obj.interfaces.values():
                    print(f"      {iface.name} ({iface.kind}) -> {iface.link}")

        return self.objects

    def _classify_classes(self):
        for name, classifier in self.diagram.classifiers.items():
            if name.startswith("Auto_Obj_"):
                self.auto_objects[name] = classifier
            elif name.startswith("Var_"):
                self.variables[name] = classifier
            elif name.startswith("Interface_"):
                self.interfaces[name] = classifier
            elif name.startswith("State_"):
                self.states[name] = classifier
            elif name.startswith("Transition_"):
                self.transitions[name] = classifier
            elif name.startswith("Trigger_"):
                self.triggers[name] = classifier
            elif name.startswith("Effect_"):
                self.effects[name] = classifier
            elif name.startswith("Action_"):
                self.actions[name] = classifier
            elif name.startswith("Call_"):
                self.calls[name] = classifier
            elif name.startswith("Choice_"):
                self.choices[name] = classifier
            elif name.startswith("Direct_"):
                self.directs[name] = classifier

    def _parse_auto_object(self, name: str, cls) -> AutoObject:
        obj_name = name.replace("Auto_Obj_", "")

        current_state = "idle"
        for attr in cls.attributes:
            if attr.name == "s":
                if attr.initial_value is not None:
                    current_state = str(attr.initial_value).lower()
                break

        variables = {}
        for attr in cls.attributes:
            if attr.name == "V":
                if attr.initial_value and isinstance(attr.initial_value, list):
                    for var_ref in attr.initial_value:
                        var_class = self.variables.get(var_ref)
                        if var_class:
                            var = self._parse_variable(var_class)
                            variables[var.name] = var
                break

        interfaces = {}
        for attr in cls.attributes:
            if attr.name == "P":
                if attr.initial_value and isinstance(attr.initial_value, list):
                    for iface_ref in attr.initial_value:
                        iface_class = self.interfaces.get(iface_ref)
                        if iface_class:
                            iface = self._parse_interface(iface_class)
                            interfaces[iface.name] = iface
                break

        states = {}
        for attr in cls.attributes:
            if attr.name == "S":
                if attr.initial_value and isinstance(attr.initial_value, list):
                    for state_ref in attr.initial_value:
                        state_class = self.states.get(state_ref)
                        if state_class:
                            state_name, transitions = self._parse_state(state_class)
                            states[state_name] = transitions
                break

        return AutoObject(
            name=obj_name,
            class_name=cls.name,
            current_state=current_state,
            variables=variables,
            interfaces=interfaces,
            states=states
        )

    def _parse_variable(self, cls) -> Variable:
        name = cls.name.replace("Var_", "")
        var = Variable(name=name)

        for attr in cls.attributes:
            if attr.name == "v":
                var.value = attr.initial_value
            elif attr.name == "t":
                var.type_ = str(attr.initial_value) if attr.initial_value else "Any"
            elif attr.name == "r":
                var.initialized = bool(attr.initial_value) if attr.initial_value is not None else False

        return var

    def _parse_interface(self, cls) -> Interface:
        """Парсит интерфейс."""
        parts = cls.name.replace("Interface_", "").split("_")
        iface_name = parts[0] if parts else cls.name

        kind = "event"
        sort = "public"
        link = None

        for attr in cls.attributes:
            if attr.name == "kind":
                kind = str(attr.initial_value) if attr.initial_value else "event"
            elif attr.name == "sort":
                sort = str(attr.initial_value) if attr.initial_value else "public"
            elif attr.name == "link":
                if attr.initial_value and isinstance(attr.initial_value, dict):
                    if "a" in attr.initial_value and "p" in attr.initial_value:
                        link = (attr.initial_value["a"], attr.initial_value["p"])

        return Interface(name=iface_name, kind=kind, sort=sort, link=link)

    def _parse_state(self, cls) -> Tuple[str, List[Dict]]:
        parts = cls.name.replace("State_", "").split("_")
        state_name = parts[0] if parts else cls.name
        state_name = state_name.lower()

        transitions = []

        for attr in cls.attributes:
            if attr.name in ["исходящие", "transitions"]:
                if attr.initial_value and isinstance(attr.initial_value, list):
                    for trans_ref in attr.initial_value:
                        trans_class = self.transitions.get(trans_ref)
                        if trans_class:
                            trans = self._parse_transition(trans_class)
                            if trans:
                                transitions.append(trans)
                break

        return state_name, transitions

    def _parse_transition(self, cls) -> Optional[Dict]:
        transition = {}

        for attr in cls.attributes:
            if attr.name == "t":
                if attr.initial_value:
                    trigger_name = attr.initial_value
                    trigger_class = self.triggers.get(trigger_name)
                    if trigger_class:
                        trigger_info = self._parse_trigger(trigger_class)
                        transition.update(trigger_info)
            elif attr.name == "m":
                if attr.initial_value:
                    if isinstance(attr.initial_value, str):
                        choice_class = self.choices.get(attr.initial_value)
                        if choice_class:
                            self._parse_choice(choice_class, transition)
                        else:
                            direct_class = self.directs.get(attr.initial_value)
                            if direct_class:
                                self._parse_direct(direct_class, transition)

        return transition if transition else None

    def _parse_choice(self, cls, transition: Dict):
        for attr in cls.attributes:
            if attr.name == "c":
                transition["guard"] = str(attr.initial_value) if attr.initial_value else None
                if transition.get("guard"):
                    transition["type"] = "choice"
            elif attr.name == "f1":
                transition["effect1"] = attr.initial_value
            elif attr.name == "s1":
                transition["target1"] = str(attr.initial_value).lower() if attr.initial_value else None
            elif attr.name == "f0":
                transition["effect0"] = attr.initial_value
            elif attr.name == "s0":
                transition["target0"] = str(attr.initial_value).lower() if attr.initial_value else None

    def _parse_direct(self, cls, transition: Dict):
        for attr in cls.attributes:
            if attr.name == "f":
                transition["effect"] = attr.initial_value
                transition["type"] = "direct"
            elif attr.name == "s":
                transition["target"] = str(attr.initial_value).lower() if attr.initial_value else None

    def _parse_trigger(self, cls) -> Dict:
        trigger = {}

        for attr in cls.attributes:
            if attr.name == "i":
                trigger["trigger"] = str(attr.initial_value) if attr.initial_value else ""
            elif attr.name == "n":
                trigger["arity"] = int(attr.initial_value) if attr.initial_value else 0
            elif attr.name == "X":
                if attr.initial_value and isinstance(attr.initial_value, list):
                    trigger["params"] = [str(p) for p in attr.initial_value]

        return trigger

    def _collect_effect_implementations(self):
        for name, cls in self.effects.items():
            effect_info = {"actions": []}

            for attr in cls.attributes:
                if attr.name == "A":
                    if attr.initial_value and isinstance(attr.initial_value, list):
                        for action_ref in attr.initial_value:
                            action_class = self.actions.get(action_ref)
                            if action_class:
                                action = self._parse_action(action_class)
                                if action:
                                    effect_info["actions"].append(action)
                    break

            self.effect_implementations[name] = effect_info

    def _parse_action(self, cls) -> Optional[Dict]:
        action = {}

        for attr in cls.attributes:
            if attr.name == "d":
                if attr.initial_value:
                    call_class = self.calls.get(attr.initial_value)
                    if call_class:
                        action["kind"] = "call"
                        action["call"] = self._parse_call(call_class)

        return action if action else None

    def _parse_call(self, cls) -> Dict:
        call = {}

        for attr in cls.attributes:
            if attr.name == "i":
                call["interface"] = str(attr.initial_value) if attr.initial_value else ""
            elif attr.name == "n":
                call["arity"] = int(attr.initial_value) if attr.initial_value else 0
            elif attr.name == "X":
                if attr.initial_value and isinstance(attr.initial_value, list):
                    call["arguments"] = [str(p) for p in attr.initial_value]

        return call


# ─── Интерпретатор CIAO ──────────────────────────────────────────────────

class CIAOInterpreter:
    """Полная реализация интерпретатора CIAO."""

    def __init__(self, diagram, debug: bool = False):
        self.diagram = diagram
        self.objects: Dict[str, AutoObject] = {}
        self.objects_by_name: Dict[str, str] = {}
        self.effect_implementations: Dict[str, Dict] = {}
        self.event_queue: deque = deque()
        self.debug = debug
        self.step_limit: int = 100
        self.step_count: int = 0
        self.is_running: bool = False

        parser = CIAODiagramParser(diagram, debug=debug)
        self.objects = parser.parse()
        self.effect_implementations = parser.effect_implementations

        self._build_object_index()

        if self.debug:
            print(f"\nCIAO Interpreter initialized")
            print(f"  Objects: {list(self.objects.keys())}")
            print(f"  Object names: {list(self.objects_by_name.keys())}")
            print(f"  Effects: {list(self.effect_implementations.keys())}")
            print()

    def _build_object_index(self):
        for full_name, obj in self.objects.items():
            self.objects_by_name[full_name] = full_name
            short_name = full_name.replace("Auto_Obj_", "")
            self.objects_by_name[short_name] = full_name
            self.objects_by_name[short_name.lower()] = full_name
            self.objects_by_name[short_name.upper()] = full_name

    def _resolve_object(self, name: str) -> Optional[AutoObject]:
        if not name:
            return None

        full_name = self.objects_by_name.get(name)
        if full_name:
            return self.objects.get(full_name)

        name_lower = name.lower()
        for key, full_name in self.objects_by_name.items():
            if key.lower() == name_lower:
                return self.objects.get(full_name)

        return None

    def start(self, event: Event):
        if self.is_running:
            print("Interpreter is already running!")
            return

        if not self.objects:
            print("No objects loaded!")
            return

        self.is_running = True
        self.step_count = 0
        self.event_queue.clear()

        print(f"=== Starting CIAO Interpreter ===")
        print(f"Start event: {event.name} -> {event.target_object}")
        print(f"Arguments: {event.arguments}")
        print()

        self.event_queue.append(event)

        while self.event_queue and self.step_count < self.step_limit:
            current_event = self.event_queue.popleft()
            self.step_count += 1

            if self.debug:
                print(f"[{self.step_count}] Processing: {current_event.name} -> {current_event.target_object}")

            self._process_event(current_event)

        if self.step_count >= self.step_limit:
            print(f"\n!!! Step limit ({self.step_limit}) reached !!!")

        self.is_running = False
        self._print_final_state()

    def _process_event(self, event: Event):
        obj = self._resolve_object(event.target_object)
        if not obj:
            print(f"  Error: Object '{event.target_object}' not found!")
            return

        if self.debug:
            print(f"  Object: {obj.name}, State: {obj.current_state}")

        for i, arg_value in enumerate(event.arguments):
            var_name = f"arg_{i}"
            self._assign_variable(obj, var_name, arg_value)

        transitions = obj.states.get(obj.current_state, [])
        matching = [t for t in transitions if t.get("trigger", "").lower() == event.name.lower()]

        if not matching:
            if self.debug:
                print(f"  No transition for '{event.name}' in state '{obj.current_state}'")
                if transitions:
                    print(f"  Available triggers: {[t.get('trigger', '?') for t in transitions]}")
            return

        transition = matching[0]
        trans_type = transition.get("type", "direct")

        if trans_type == "direct":
            self._process_direct(transition, obj)
        elif trans_type == "choice":
            self._process_choice(transition, obj)

    def _process_direct(self, transition: Dict, obj: AutoObject):
        target = transition.get("target")
        if self.debug:
            print(f"  Direct transition -> {target}")

        effect_name = transition.get("effect")
        if effect_name:
            self._execute_effect(effect_name)

        if target:
            obj.current_state = target
            if self.debug:
                print(f"  New state: {obj.current_state}")

    def _process_choice(self, transition: Dict, obj: AutoObject):
        guard = transition.get("guard")
        guard_result = self._evaluate_guard(guard, obj)

        if self.debug:
            print(f"  Choice transition [guard: {guard}] = {guard_result}")

        if guard_result:
            effect_name = transition.get("effect1")
            new_state = transition.get("target1")
        else:
            effect_name = transition.get("effect0")
            new_state = transition.get("target0")

        if effect_name:
            self._execute_effect(effect_name)

        if new_state:
            obj.current_state = new_state
            if self.debug:
                print(f"  New state: {obj.current_state}")

    def _execute_effect(self, effect_name: str):
        if self.debug:
            print(f"  Executing effect: {effect_name}")

        effect = self.effect_implementations.get(effect_name)
        if not effect:
            if self.debug:
                print(f"  Warning: Effect '{effect_name}' not found")
            return

        for action in effect.get("actions", []):
            if action.get("kind") == "call":
                self._execute_call(action.get("call", {}))

    def _execute_call(self, call: Dict):
        """
        Выполняет вызов action.
        1. Если action имеет link → используем его
        2. Если action не имеет link → ищем event с таким же именем у другого объекта
        3. Иначе — внутреннее действие
        """
        interface_name = call.get("interface", "")
        arguments = call.get("arguments", [])

        if self.debug:
            print(f"    Call: {interface_name}")

        target_obj = None
        target_interface = None
        interface_name_lower = interface_name.lower()
        caller_obj = None

        # 1. Ищем action-интерфейс с link
        for obj in self.objects.values():
            for iface in obj.interfaces.values():
                if iface.name.lower() == interface_name_lower and iface.kind == "action":
                    caller_obj = obj
                    if iface.link:
                        target_obj, target_interface = iface.link
                        if self.debug:
                            print(
                                f"    Found action '{iface.name}' in {obj.name} with link -> {target_obj}.{target_interface}")
                        break
                    else:
                        if self.debug:
                            print(
                                f"    Action '{iface.name}' in {obj.name} has no link, searching for matching event...")
            if target_obj:
                break

        # 2. Если action с link не найден, ищем event с таким же именем у другого объекта
        if not target_obj:
            for obj in self.objects.values():
                if obj == caller_obj:
                    continue
                for iface in obj.interfaces.values():
                    if iface.name.lower() == interface_name_lower and iface.kind == "event":
                        target_obj = obj.name
                        target_interface = iface.name
                        if self.debug:
                            print(f"    Found matching event '{iface.name}' in {obj.name}")
                        break
                if target_obj:
                    break

        if target_obj and target_interface:
            event = Event(
                name=target_interface,
                target_object=target_obj,
                arguments=arguments
            )
            self.event_queue.append(event)
            if self.debug:
                print(f"    Enqueued: {event.name} -> {event.target_object}")
        else:
            if self.debug:
                print(f"    Action '{interface_name}' is internal (no target found)")

    def _assign_variable(self, obj: AutoObject, var_name: str, value: Any):
        if var_name in obj.variables:
            var = obj.variables[var_name]
            var.value = value
            var.initialized = True
            if self.debug:
                print(f"    Assigned {var_name} = {value}")

    def _evaluate_guard(self, guard: Optional[str], obj: AutoObject) -> bool:
        if guard is None:
            return True
        if guard == "else":
            return False

        match = re.match(r'(\w+)\((\w+)\)', guard)
        if match:
            condition, var_name = match.groups()
            var = obj.variables.get(var_name)
            if var and var.initialized:
                result = random.choice([True, False])
                if self.debug:
                    print(f"    Guard '{condition}({var_name})' = {result}")
                return result
            return False

        return True

    def _print_final_state(self):
        print("\n" + "=" * 50)
        print("FINAL STATE")
        print("=" * 50)

        for full_name, obj in self.objects.items():
            print(f"\n{obj.name}:")
            print(f"  Class: {full_name}")
            print(f"  State: {obj.current_state}")
            print(f"  Variables:")
            for var_name, var in obj.variables.items():
                status = "✓" if var.initialized else "✗"
                print(f"    {status} {var_name}: {var.value} (type: {var.type_})")


# ─── Main ──────────────────────────────────────────────────────────────────

def main():
    with open("consumer_producer.txt", "r", encoding="utf-8") as f:
        diagram = tdl_to_diagram(f.read(), "consumer_producer")

    interpreter = CIAOInterpreter(diagram, debug=False)

    start_event = Event(
        name="need",
        target_object="Consumer",
        arguments=["s"]
    )

    interpreter.start(start_event)

    start_event = Event(
        name="done",
        target_object="Producer",
        arguments=["g"]
    )

    interpreter.start(start_event)


if __name__ == "__main__":
    main()