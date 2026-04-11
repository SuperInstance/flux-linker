"""
FLUX Linker — combine multiple bytecode modules into one program.

Supports:
- Module imports with symbol resolution
- Cross-module label resolution
- Relocation tables for jump fixups
- Library linking (pre-compiled bytecode libraries)
"""
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum


class SymbolType(Enum):
    LABEL = "label"
    FUNCTION = "function"
    VARIABLE = "variable"
    EXTERNAL = "external"


@dataclass
class Symbol:
    name: str
    symbol_type: SymbolType
    offset: int  # offset within module
    module: str
    size: int = 0
    resolved: bool = False


@dataclass
class Relocation:
    """A reference that needs to be fixed up after linking."""
    offset: int  # where in the bytecode to patch
    symbol_name: str
    module: str
    reloc_type: str = "absolute"  # absolute or relative


@dataclass
class Module:
    """A FLUX bytecode module."""
    name: str
    bytecode: List[int]
    symbols: Dict[str, Symbol] = field(default_factory=dict)
    relocations: List[Relocation] = field(default_factory=dict)
    exports: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    
    def add_symbol(self, name: str, symbol_type: SymbolType, offset: int):
        self.symbols[name] = Symbol(
            name=name, symbol_type=symbol_type,
            offset=offset, module=self.name
        )
    
    def add_export(self, name: str):
        self.exports.append(name)
    
    def add_import(self, name: str):
        self.imports.append(name)
    
    def size(self) -> int:
        return len(self.bytecode)


@dataclass
class LinkResult:
    """Result of a link operation."""
    bytecode: List[int]
    symbols: Dict[str, Symbol]
    modules_linked: int
    relocations_resolved: int
    errors: List[str] = field(default_factory=list)


class FluxLinker:
    """Links multiple FLUX bytecode modules."""
    
    def __init__(self):
        self.modules: Dict[str, Module] = {}
        self.libraries: Dict[str, List[int]] = {}
    
    def add_module(self, module: Module):
        self.modules[module.name] = module
    
    def add_library(self, name: str, bytecode: List[int]):
        self.libraries[name] = bytecode
    
    def link(self) -> LinkResult:
        """Link all modules into a single bytecode program."""
        result = LinkResult(bytecode=[], symbols={}, modules_linked=0, relocations_resolved=0)
        
        # Phase 1: Concatenate bytecodes, adjusting offsets
        offset = 0
        all_symbols: Dict[str, Symbol] = {}
        
        for name, module in self.modules.items():
            result.bytecode.extend(module.bytecode)
            
            # Adjust symbol offsets
            for sym_name, sym in module.symbols.items():
                adjusted = Symbol(
                    name=sym.name, symbol_type=sym.symbol_type,
                    offset=sym.offset + offset, module=sym.module,
                    size=sym.size, resolved=sym.resolved
                )
                all_symbols[sym_name] = adjusted
            
            offset += len(module.bytecode)
            result.modules_linked += 1
        
        # Phase 2: Resolve relocations
        for name, module in self.modules.items():
            module_offset = sum(len(m.bytecode) for n, m in self.modules.items() if list(self.modules.keys()).index(n) < list(self.modules.keys()).index(name))
            
            for reloc in module.relocations:
                target = all_symbols.get(reloc.symbol_name)
                if target:
                    patch_offset = reloc.offset + module_offset
                    if 0 <= patch_offset < len(result.bytecode):
                        # Patch with resolved offset (simplified: 16-bit little-endian)
                        result.bytecode[patch_offset] = target.offset & 0xFF
                        if patch_offset + 1 < len(result.bytecode):
                            result.bytecode[patch_offset + 1] = (target.offset >> 8) & 0xFF
                        result.relocations_resolved += 1
                else:
                    result.errors.append(f"Unresolved symbol: {reloc.symbol_name}")
        
        # Phase 3: Resolve imports from libraries
        for name, module in self.modules.items():
            for imp in module.imports:
                if imp in self.libraries:
                    # Append library bytecode
                    lib_start = len(result.bytecode)
                    result.bytecode.extend(self.libraries[imp])
                    
                    lib_sym = Symbol(name=imp, symbol_type=SymbolType.LABEL,
                                    offset=lib_start, module="library")
                    all_symbols[imp] = lib_sym
        
        result.symbols = all_symbols
        return result
    
    def link_two(self, mod_a: Module, mod_b: Module) -> LinkResult:
        """Link exactly two modules."""
        self.add_module(mod_a)
        self.add_module(mod_b)
        return self.link()


# ── Tests ──────────────────────────────────────────────

import unittest


class TestModule(unittest.TestCase):
    def test_create(self):
        m = Module(name="test", bytecode=[0x18, 0, 42, 0x00])
        self.assertEqual(m.size(), 4)
    
    def test_add_symbol(self):
        m = Module(name="test", bytecode=[0x00])
        m.add_symbol("main", SymbolType.LABEL, 0)
        self.assertIn("main", m.symbols)
    
    def test_export(self):
        m = Module(name="test", bytecode=[0x00])
        m.add_export("main")
        self.assertIn("main", m.exports)
    
    def test_import(self):
        m = Module(name="test", bytecode=[0x00])
        m.add_import("math_lib")
        self.assertIn("math_lib", m.imports)


class TestLinker(unittest.TestCase):
    def test_link_empty(self):
        linker = FluxLinker()
        result = linker.link()
        self.assertEqual(result.modules_linked, 0)
        self.assertEqual(len(result.bytecode), 0)
    
    def test_link_single(self):
        linker = FluxLinker()
        linker.add_module(Module(name="main", bytecode=[0x18, 0, 42, 0x00]))
        result = linker.link()
        self.assertEqual(result.modules_linked, 1)
        self.assertEqual(result.bytecode, [0x18, 0, 42, 0x00])
    
    def test_link_two_modules(self):
        linker = FluxLinker()
        linker.add_module(Module(name="a", bytecode=[0x18, 0, 10, 0x18, 1, 20]))
        linker.add_module(Module(name="b", bytecode=[0x20, 2, 0, 1, 0x00]))
        result = linker.link()
        self.assertEqual(result.modules_linked, 2)
        self.assertEqual(len(result.bytecode), 11)
    
    def test_symbol_offset_adjustment(self):
        linker = FluxLinker()
        mod_a = Module(name="a", bytecode=[0x18, 0, 42, 0x00])
        mod_a.add_symbol("main", SymbolType.LABEL, 0)
        mod_b = Module(name="b", bytecode=[0x18, 1, 7, 0x00])
        mod_b.add_symbol("helper", SymbolType.LABEL, 0)
        linker.add_module(mod_a)
        linker.add_module(mod_b)
        result = linker.link()
        # "helper" should be at offset 4 (after mod_a's 4 bytes)
        self.assertEqual(result.symbols["helper"].offset, 4)
    
    def test_library_linking(self):
        linker = FluxLinker()
        linker.add_library("math", [0x22, 1, 1, 0, 0x00])  # MUL R1, R1, R0; HALT
        mod = Module(name="main", bytecode=[0x18, 0, 5, 0x18, 1, 1])
        mod.add_import("math")
        linker.add_module(mod)
        result = linker.link()
        # Main (6 bytes) + math library (5 bytes)
        self.assertEqual(len(result.bytecode), 11)
    
    def test_link_result_no_errors(self):
        linker = FluxLinker()
        linker.add_module(Module(name="test", bytecode=[0x00]))
        result = linker.link()
        self.assertEqual(len(result.errors), 0)


class TestSymbol(unittest.TestCase):
    def test_create(self):
        s = Symbol(name="main", symbol_type=SymbolType.LABEL, offset=0, module="test")
        self.assertEqual(s.name, "main")
        self.assertFalse(s.resolved)
    
    def test_types(self):
        for t in SymbolType:
            s = Symbol(name="x", symbol_type=t, offset=0, module="test")
            self.assertEqual(s.symbol_type, t)


if __name__ == "__main__":
    unittest.main(verbosity=2)
