#!/usr/bin/env python3
"""
Sync IDE project config (.cproject) to GCC Makefile include fragment.

Reads the STM32CubeIDE .cproject XML and extracts:
- Include paths (-I)
- Source folders
- Defined symbols (-D)
- Library paths and libraries

Outputs a Makefile fragment (gcc/ide_sync.mk) that can be included
by the main makefile_appli.

Usage:
    python3 sync_ide_config.py [--cproject PATH] [--output PATH] [--dry]

IDE is the source of truth. This script bridges IDE config to GCC build.
"""

import xml.etree.ElementTree as ET
import argparse
import os
import sys
import re
from pathlib import Path


def find_cproject(project_root):
    """Find .cproject file in standard locations."""
    candidates = [
        os.path.join(project_root, "STM32CubeIDE", "Appli", ".cproject"),
        os.path.join(project_root, "STM32CubeIDE", ".cproject"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def resolve_workspace_loc(path_str, workspace_root, project_name="STM32N6570-DK_Appli"):
    """Resolve ${workspace_loc:/${ProjName}/...} to filesystem paths."""
    pattern = r'\$\{workspace_loc:/\$\{ProjName\}/(.+)\}'
    match = re.match(pattern, path_str.strip('"'))
    if match:
        relative = match.group(1)
        # These are linked folders in the IDE project — resolve to actual locations
        # The linked folders point to the firmware repository or project tree
        return relative  # Return as-is, will be mapped below
    return None


def extract_include_paths(root):
    """Extract all include paths from .cproject XML."""
    paths = []
    for opt in root.iter('option'):
        super_class = opt.get('superClass', '')
        if 'includepaths' in super_class.lower() or 'includePath' in super_class:
            for val in opt.findall('listOptionValue'):
                v = val.get('value', '')
                if v and val.get('builtIn') != 'true':
                    paths.append(v)
    return list(dict.fromkeys(paths))  # dedupe, preserve order


def extract_defines(root):
    """Extract all defined symbols from .cproject XML."""
    defines = []
    for opt in root.iter('option'):
        super_class = opt.get('superClass', '')
        if 'definedsymbols' in super_class.lower():
            for val in opt.findall('listOptionValue'):
                v = val.get('value', '')
                if v and val.get('builtIn') != 'true':
                    defines.append(v)
    return list(dict.fromkeys(defines))


def extract_libraries(root):
    """Extract library names and paths from .cproject XML."""
    libs = []
    lib_paths = []
    for opt in root.iter('option'):
        super_class = opt.get('superClass', '')
        if 'libraries.' in super_class.lower() and 'path' not in super_class.lower():
            for val in opt.findall('listOptionValue'):
                v = val.get('value', '')
                if v:
                    libs.append(v)
        elif 'library.paths' in super_class.lower() or 'librarypath' in super_class.lower():
            for val in opt.findall('listOptionValue'):
                v = val.get('value', '')
                if v:
                    lib_paths.append(v)
    return list(dict.fromkeys(libs)), list(dict.fromkeys(lib_paths))


def extract_source_entries(root):
    """Extract source entries (excluding/including folders) from .cproject."""
    entries = []
    for entry in root.iter('entry'):
        kind = entry.get('kind', '')
        name = entry.get('name', '')
        excluding = entry.get('excluding', '')
        flags = entry.get('flags', '')
        if kind == 'sourcePath' and name:
            entries.append({
                'name': name,
                'excluding': excluding,
                'flags': flags
            })
    return entries


def resolve_paths(paths, project_root, cproject_dir):
    """Resolve IDE paths to paths relative to project root (for GCC Makefile)."""
    resolved = []
    for p in paths:
        p_clean = p.strip('"')

        # Handle ${workspace_loc:/${ProjName}/...} — linked folders
        ws_match = re.match(r'\$\{workspace_loc:/\$\{ProjName\}/(.+)\}', p_clean)
        if ws_match:
            relative = ws_match.group(1)
            # Check common locations for linked folders
            candidates = [
                # In-project (already imported/linked)
                os.path.join(project_root, relative),
                # STM32Cube firmware repository
                os.path.join("C:/Users/mp202/STM32Cube/Repository/STM32Cube_FW_N6_V1.3.0/Middlewares/ST", relative),
                os.path.join("C:/Users/mp202/STM32Cube/Repository/STM32Cube_FW_N6_V1.3.0/Drivers", relative),
            ]
            for c in candidates:
                if os.path.exists(c):
                    try:
                        resolved.append(os.path.relpath(c, project_root).replace('\\', '/'))
                    except ValueError:
                        resolved.append(c.replace('\\', '/'))
                    break
            else:
                # Can't resolve — output as comment
                resolved.append(f"# UNRESOLVED: {p_clean}")
            continue

        # Handle relative paths (from .cproject dir)
        if p_clean.startswith('../') or p_clean.startswith('../../'):
            abs_path = os.path.normpath(os.path.join(cproject_dir, p_clean))
            try:
                rel_path = os.path.relpath(abs_path, project_root).replace('\\', '/')
                resolved.append(rel_path)
            except ValueError:
                # Cross-drive (e.g., C: vs D:) — use absolute path
                resolved.append(abs_path.replace('\\', '/'))
        else:
            resolved.append(p_clean)

    return resolved


def generate_makefile_fragment(includes, defines, libs, lib_paths, source_entries, output_path, dry=False):
    """Generate ide_sync.mk Makefile fragment."""
    lines = []
    lines.append("# AUTO-GENERATED by sync_ide_config.py — DO NOT EDIT MANUALLY")
    lines.append("# Source of truth: STM32CubeIDE/Appli/.cproject")
    lines.append("# Re-run: python3 Knowledge/K_STM32_MCP/scripts/sync_ide_config.py")
    lines.append("")

    # Include paths
    lines.append("# Include paths extracted from IDE project")
    lines.append("IDE_C_INCLUDES = \\")
    for i, inc in enumerate(includes):
        if inc.startswith('#'):
            lines.append(f"  {inc}")
        else:
            suffix = " \\" if i < len(includes) - 1 else ""
            lines.append(f"  -I{inc}{suffix}")
    lines.append("")

    # Defines
    lines.append("# Defined symbols extracted from IDE project")
    lines.append("IDE_C_DEFS = \\")
    for i, d in enumerate(defines):
        suffix = " \\" if i < len(defines) - 1 else ""
        lines.append(f"  -D{d}{suffix}")
    lines.append("")

    # Libraries
    if libs:
        lines.append("# Libraries extracted from IDE project")
        lines.append("IDE_LIBS = \\")
        for i, lib in enumerate(libs):
            suffix = " \\" if i < len(libs) - 1 else ""
            lines.append(f"  -l{lib}{suffix}")
        lines.append("")

    if lib_paths:
        lines.append("# Library paths extracted from IDE project")
        lines.append("IDE_LIBDIR = \\")
        for i, lp in enumerate(lib_paths):
            suffix = " \\" if i < len(lib_paths) - 1 else ""
            lines.append(f"  -L{lp}{suffix}")
        lines.append("")

    # Source entries info
    if source_entries:
        lines.append("# Source entries (for reference — source files managed by makefile_appli)")
        for entry in source_entries:
            excl = f" (excluding: {entry['excluding']})" if entry['excluding'] else ""
            lines.append(f"#   {entry['name']}{excl}")
        lines.append("")

    content = "\n".join(lines) + "\n"

    if dry:
        print(content)
        return

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(content)
    print(f"OK: wrote {output_path}")
    print(f"    {len(includes)} include paths, {len(defines)} defines, {len(libs)} libraries")


def main():
    parser = argparse.ArgumentParser(description="Sync IDE config to GCC Makefile fragment")
    parser.add_argument('--cproject', help='Path to .cproject file')
    parser.add_argument('--output', help='Output Makefile fragment path')
    parser.add_argument('--dry', action='store_true', help='Print to stdout instead of writing')
    args = parser.parse_args()

    # Find project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, '..', '..', '..'))

    # Find .cproject
    cproject_path = args.cproject or find_cproject(project_root)
    if not cproject_path or not os.path.exists(cproject_path):
        print("ERROR: .cproject not found", file=sys.stderr)
        sys.exit(1)

    cproject_dir = os.path.dirname(os.path.abspath(cproject_path))

    # Parse
    tree = ET.parse(cproject_path)
    root = tree.getroot()

    # Extract
    raw_includes = extract_include_paths(root)
    defines = extract_defines(root)
    libs, lib_paths = extract_libraries(root)
    source_entries = extract_source_entries(root)

    # Resolve paths
    includes = resolve_paths(raw_includes, project_root, cproject_dir)

    # Resolve library paths too
    lib_paths = resolve_paths(lib_paths, project_root, cproject_dir)

    # Output
    output_path = args.output or os.path.join(project_root, "gcc", "ide_sync.mk")
    generate_makefile_fragment(includes, defines, libs, lib_paths, source_entries, output_path, args.dry)


if __name__ == '__main__':
    main()
