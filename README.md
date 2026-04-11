# FLUX Linker — Multi-Module Bytecode Linker

Combine multiple FLUX bytecode modules into a single program.

## Features
- **Module system**: Compile separately, link together
- **Symbol resolution**: Labels, functions, variables across modules
- **Relocation**: Fix up cross-module references after concatenation
- **Library linking**: Import pre-compiled bytecode libraries
- **Offset adjustment**: Automatic symbol offset recalculation

## Usage

```python
from linker import FluxLinker, Module, SymbolType

linker = FluxLinker()
main = Module("main", [0x18, 0, 10, 0x18, 1, 20])
main.add_symbol("entry", SymbolType.LABEL, 0)
main.add_export("entry")

helper = Module("helper", [0x20, 2, 0, 1, 0x00])
helper.add_import("math")

linker.add_library("math", [0x22, 1, 1, 0, 0x00])
linker.add_module(main)
linker.add_module(helper)

result = linker.link()
print(f"Linked {result.modules_linked} modules, {len(result.bytecode)} bytes")
```

12 tests passing.
