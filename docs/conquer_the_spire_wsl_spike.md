# conquer-the-spire WSL Build Spike

This spike must stay outside the repository working tree. It should clone and
build external simulator code under `~/stsrl-spikes` inside WSL.

## Current Preflight Result

From this Codex session on 2026-06-03:

```text
wsl.exe -l -v
```

is only visible from Codex when run outside the filesystem sandbox. It reports:

```text
Ubuntu  Stopped  2
```

Toolchain probe inside Ubuntu:

```text
PRETTY_NAME="Ubuntu 26.04 LTS"
git=present
cmake=present
make=present
gcc=present
g++=missing
python3=present
pip3=missing
ninja=missing
```

`sudo -n true` reports that interactive authentication is required, so Codex
cannot install missing WSL packages without user action.

## Preflight Commands

After WSL is initialized, verify the toolchain:

```bash
cat /etc/os-release
uname -a
command -v git
command -v cmake
command -v make
command -v g++
command -v python3
```

For Ubuntu/Debian, install missing build tools with:

```bash
sudo apt update
sudo apt install -y git cmake build-essential python3 python3-pip
```

## Isolated Clone And Build

Use a shallow recursive clone only for the spike:

```bash
mkdir -p ~/stsrl-spikes
cd ~/stsrl-spikes
git clone --depth 1 --recursive https://github.com/utilForever/conquer-the-spire.git
cd conquer-the-spire
mkdir -p build
cd build
cmake ..
cmake --build . --parallel
```

If `--depth 1 --recursive` fails because a submodule needs history, retry with:

```bash
rm -rf ~/stsrl-spikes/conquer-the-spire
git clone --recursive https://github.com/utilForever/conquer-the-spire.git ~/stsrl-spikes/conquer-the-spire
```

## Spike Finding

`conquer-the-spire` was cloned at commit `483abc9`. The repository README claims
C++ and Python APIs, but the checked source is only a skeleton:

```text
Includes/conquer-the-spire/Test.hpp
Includes/conquer-the-spire/conquer-the-spire.hpp
Sources/conquer-the-spire/Test.cpp
Tests/UnitTests/SimpleTest.cpp
```

The C++ code is an `Add(int, int)` example and the whole first-party
Sources/Includes/Tests tree is roughly 139 lines. No pybind, Python binding,
game state, reset, step, card, or monster implementation was found.

Conclusion: do not use `conquer-the-spire` as the simulator path unless a
different branch/fork is identified.

## Success Criteria

The spike is useful only if it answers:

- Build succeeds in WSL.
- A Python-facing API exists or can be imported without wiring it into this repo.
- The simulator can reset, expose state, accept an action, and advance a step.
- Action concepts can map roughly to play card, target, end turn, choose, and
  proceed.
- No external simulator source, build artifacts, or game assets are copied into
  this repository.
