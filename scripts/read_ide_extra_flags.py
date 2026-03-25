#!/usr/bin/env python3
"""Read ide_sync.mk and output extra CFLAGS for paths not already in makefile_appli.
Also adds source directories so #include "file.c" wrappers resolve."""
import re
import sys
import os

def main():
    mk_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'gcc', 'ide_sync.mk')
    if not os.path.exists(mk_path):
        sys.exit(0)

    content = open(mk_path).read()

    # Extract paths that are absolute (C:/ or similar) — these are the BSP/ISP paths
    # not already in the TouchGFX makefile
    paths = re.findall(r'-I((?:[A-Za-z]:/)[^\s\\]+)', content)

    # Also add source directories (Src counterparts of Inc paths) for #include "file.c"
    extra_src_paths = set()
    for p in paths:
        # Inc -> Src
        if '/Inc' in p:
            src = p.replace('/Inc', '/Src')
            if os.path.isdir(src):
                extra_src_paths.add(src)
        # Component directories (contain both .h and .c)
        if os.path.isdir(p):
            extra_src_paths.add(p)

    # Also add local HAL Src directory for #include "hal_*.c" wrappers
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, '..', '..', '..'))
    hal_src = os.path.join(project_root, 'Drivers', 'STM32N6xx_HAL_Driver', 'Src')
    if os.path.isdir(hal_src):
        extra_src_paths.add(hal_src.replace('\\', '/'))

    all_paths = paths + sorted(extra_src_paths - set(paths))

    if all_paths:
        print(' '.join(['-I' + p for p in all_paths]))


if __name__ == '__main__':
    main()
