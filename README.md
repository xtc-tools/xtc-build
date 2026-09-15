# xtc-build

`xtc-build` is a small Python library for describing C object files, static
archives, and shared libraries as an explicit dependency graph. The same graph
can be inspected, built immediately from Python, or written as a GNU Makefile.

It deliberately has no mandatory project object. Artifacts describe what must
be built; a lightweight `BuildContext` supplies the toolchain and output
directory.

> **Status:** early alpha. The initial backend targets GCC/Clang-compatible C
> toolchains and GNU Make on Unix-like systems.

## Installation

```sh
python -m pip install .
```

Development requires `gcc`, `ar`, and GNU Make. Missing tools are reported as
test errors rather than skipped tests.

```sh
python -m pip install -e '.[dev]'
make check
```

The full check requires 100% line and branch coverage and writes an HTML report
to `htmlcov/`. Use `make check-pytest` to run pytest without collecting
coverage.

## Example

```python
import ctypes

from xtc_build import (
    Archive,
    BuildContext,
    ExternalLibrary,
    GnuToolchain,
    Object,
    SharedLibrary,
)

ctx = BuildContext(
    build_dir="build",
    toolchain=GnuToolchain(cc="gcc", ar="ar"),
)

helper = Object(
    "helper",
    source="src/helper.c",
    inputs=["include/helper.h"],
    includes=["include"],
    compile_flags=["-O2", "-Wall"],
    pic=True,
)
api = Object("api", source="src/api.c", includes=["include"], pic=True)
core = Archive("core", objects=[helper])
math = ExternalLibrary("math", link_flags=["-lm"])
library = SharedLibrary(
    "example",
    objects=[api],
    archives=[core],
    libraries=[math],
    link_flags=["-Wl,--no-undefined"],
)
```

Every artifact is independently buildable. Building a composite artifact also
builds its stale transitive dependencies:

```python
helper.build(ctx)       # build/example.o-style object output
core.build(ctx)         # builds its object dependencies first
path = library.build(ctx)

loaded = ctypes.CDLL(str(path))
```

`Artifact.build()` returns its output path. `BuildContext.build()` instead
returns the tuple of artifacts rebuilt by that invocation:

```python
rebuilt = ctx.build(library)
```

The immediate executor compares input and output timestamps and stores a
command fingerprint beside each output. Changing compiler flags therefore
causes a rebuild even when source timestamps did not change.

## Inspecting the graph

```python
graph = ctx.graph(library)

for node in graph.topological_order():
    command = graph.command(node)
    print(node.name)
    print("dependencies:", graph.dependencies(node))
    print("argv:", command.argv)
    print("inputs:", command.inputs)
    print("outputs:", command.outputs)
```

Commands are structured argument vectors, not shell strings. This allows the
immediate executor to invoke them without `shell=True` and lets output backends
perform their own quoting.

## Generating a Makefile

```python
ctx.write_makefile("build/Makefile", targets=[core, library])
```

Run it from the directory against which source paths were declared:

```sh
make -f build/Makefile
make -f build/Makefile clean
```

Object rules emit GCC-compatible dependency files (`-MMD -MP`). Declare
non-discoverable inputs such as generated headers and linker scripts explicitly
with `Object(inputs=[...])`.

## Design notes

- Dependencies between built artifacts are explicit and cycle checked.
- Output collisions are rejected while constructing a graph.
- Link order follows declaration order.
- Objects linked into a shared library must declare `pic=True` by default. Set
  `require_pic=False` on `SharedLibrary` only when the target platform permits
  it.
- `ExternalLibrary` is not a build node; it is an explicit collection of link
  flags for a library built outside the graph.
- A project/grouping abstraction may be added later as an optional convenience,
  but is not required by the core model.

## Versioning

Package versions are derived from Git tags by `setuptools-scm`. Release tags
must use the `xtc-build-vX.Y.Z` form, for example:

Create an annotated tag for each release:

```sh
git tag -a xtc-build-v1.2.3 -m "xtc-build 1.2.3"
```

A build at that tag has version `1.2.3`; later commits receive a development
version derived from the tag and Git revision. Builds without Git metadata use
`0.0.0` as a fallback.

## License

BSD 3-Clause. See [LICENSE](LICENSE).
