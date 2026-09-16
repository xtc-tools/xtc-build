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

Install the latest release from [PyPI](https://pypi.org/project/xtc-build/):

```sh
python -m pip install xtc-build
```

Development versions built from `main` are available from
[TestPyPI](https://test.pypi.org/project/xtc-build/) for testing:

```sh
python -m pip install --pre --upgrade \
  --index-url https://test.pypi.org/simple/ xtc-build
```

## Development installation

Development requires `cc`, `ar`, and `make`. On macOS, the system-provided
Apple Clang toolchain is sufficient; Homebrew is not required. Missing tools
are reported as test errors rather than skipped tests. Install `uv` from the
[official installation page](https://docs.astral.sh/uv/getting-started/installation/),
or directly with:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then clone the repository and set up the development environment:

```sh
git clone git@github.com:xtc-tools/xtc-build.git
cd xtc-build
uv sync
source .venv/bin/activate
make check
```

`uv sync` creates the virtual environment, installs the project in editable
mode, installs the default `dev` dependency group, and synchronizes everything
with the committed `uv.lock`. Alternatively, run checks without activating the
environment:

```sh
uv run make check
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
    Object,
    SharedLibrary,
)

ctx = BuildContext(
    build_dir="build",
    compile_flags="-O2 -Wall",
    defines=["PROJECT_BUILD=1"],
)

helper = Object(
    "helper",
    source="src/helper.c",
    inputs=["include/helper.h"],
    includes=["include"],
    compile_flags=["-Wconversion"],
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

Flag fields such as `compile_flags`, `archive_flags`, and `link_flags` accept
either a sequence of arguments or a shell-like string. Strings are parsed with
`shlex.split()`, including quote handling, but commands are still executed
without a shell.

`BuildContext` provides default `compile_flags`, `link_flags`, and `defines`.
Artifact-specific values are appended after these defaults. Set
`override_flags=True` on an `Object` or `SharedLibrary` to ignore the matching
context flags, or `override_defines=True` on an `Object` to ignore context
definitions.

The default `GnuToolchain` uses the system `cc` and `ar` commands. On macOS,
`cc` selects Apple Clang and shared libraries use the native `.dylib` format.
A specific compatible compiler can still be selected explicitly:

```python
from xtc_build import GnuToolchain

ctx = BuildContext(toolchain=GnuToolchain(cc="gcc"))
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

The immediate executor compares input and output timestamps and stores each
command's deterministic JSON state, including its ordered input and output
paths, beside the output. The stored JSON is compared directly and can be
diffed when diagnosing a rebuild. Changing compiler flags or declared inputs
therefore causes a rebuild even when source timestamps did not change.

## Prebuilt inputs

Object files and static archives produced outside the graph can be declared as
input-only artifacts:

```python
from xtc_build import (
    Archive,
    ExternalArchive,
    ExternalObject,
    ExternalSharedLibrary,
    SharedLibrary,
)

prebuilt_object = ExternalObject("generated/helper.o", pic=True)
archive = Archive("core", objects=[prebuilt_object])

prebuilt_archive = ExternalArchive("vendor/libsupport.a", pic=True)
prebuilt_shared = ExternalSharedLibrary("vendor/libdependency.so")
library = SharedLibrary(
    "example",
    objects=[api],
    archives=[prebuilt_archive],
    libraries=[prebuilt_shared],
)
```

`ExternalObject`, `ExternalArchive`, and `ExternalSharedLibrary` have no build
command and are not graph nodes. Their exact paths, including extensions, are
explicit command inputs and Make prerequisites. They must exist before
immediate execution or be produced independently before Make needs them. Set
`pic=True` when an object or archive is suitable for linking into a shared
library. On Linux and macOS, each external shared library's resolved parent
directory is added to the linked library's runtime search path. Windows does
not support embedded rpaths, so its DLL search path must be configured at
runtime.

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
must use the `xtc-build-vX.Y.Z` form. Create an annotated tag for each release:

```sh
git tag -a xtc-build-v1.2.3 -m "xtc-build 1.2.3"
```

A build at that tag has version `1.2.3`; later commits receive a development
version derived from the tag and Git revision. Builds without Git metadata use
`0.0.0` as a fallback.

After all checks pass, pushes to `main` publish development distributions to
[TestPyPI](https://test.pypi.org/project/xtc-build/), while
`xtc-build-vX.Y.Z` tags publish releases to
[PyPI](https://pypi.org/project/xtc-build/). Both publication jobs in
`.github/workflows/ci.yml` use trusted publishing through the `testpypi` and
`pypi` GitHub environments; those trusted publishers must be configured on the
corresponding package indexes before the jobs can authenticate.

Published versions can be inspected through the package-index JSON APIs:

```sh
curl -fsSL https://pypi.org/pypi/xtc-build/json \
  | jq -r '.releases | keys[]'
curl -fsSL https://test.pypi.org/pypi/xtc-build/json \
  | jq -r '.releases | keys[]'
```

## License

BSD 3-Clause. See [LICENSE](LICENSE).
