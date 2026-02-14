#!/usr/bin/env python3
"""
Cross-platform script to create symbolic links for calibration files.
Works on Windows, macOS, and Linux.

Configuration is read from 'calibration_links.toml' in the same directory.
The script auto-detects all .py files and subfolders in the specified source folders.

Usage:
    python create_calibration_links.py

Note: On Windows, run as Administrator. On Mac/Linux, may need sudo.
"""

import os
import sys
import ctypes
from pathlib import Path

# Handle TOML parsing for different Python versions
try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # pip install tomli for Python < 3.11
    except ImportError:
        tomllib = None


def load_config(config_path: Path) -> dict:
    """Load configuration from TOML file."""
    if not config_path.exists():
        print(f"ERROR: Config file not found: {config_path}")
        print("Please create 'calibration_links.toml' with your link definitions.")
        sys.exit(1)

    if tomllib is None:
        print("ERROR: TOML parser not available.")
        print("For Python < 3.11, install tomli: pip install tomli")
        sys.exit(1)

    with open(config_path, "rb") as f:
        return tomllib.load(f)


def is_admin():
    """Check if script is running with administrator/root privileges."""
    if sys.platform == "win32":
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    else:
        return os.geteuid() == 0


def create_symlink(link_path: Path, target_path: Path, is_directory: bool = False):
    """Create a symbolic link, removing existing one if present."""
    # Check if target exists
    if not target_path.exists():
        print(f"   ERROR: Target does not exist: {target_path}")
        return False

    # Remove existing link/file/directory
    if link_path.exists() or link_path.is_symlink():
        print("   Removing existing link...")
        try:
            if link_path.is_dir() and not link_path.is_symlink():
                link_path.rmdir()
            else:
                link_path.unlink()
        except Exception as e:
            print(f"   ERROR removing existing link: {e}")
            return False

    # Create the symlink
    try:
        link_path.symlink_to(target_path, target_is_directory=is_directory)
        print(f"   SUCCESS: {link_path.name}")
        print(f"      -> {target_path}")
        return True
    except OSError as e:
        print(f"   FAILED: {e}")
        if sys.platform == "win32" and "privilege" in str(e).lower():
            print("   (Try running as Administrator)")
        return False


def get_py_files(folder: Path) -> list[Path]:
    """Get all .py files in a folder (non-recursive)."""
    if not folder.exists():
        return []
    return sorted([f for f in folder.iterdir() if f.is_file() and f.suffix == ".py"])


def get_subfolders(folder: Path) -> list[Path]:
    """Get all subfolders in a folder (non-recursive)."""
    if not folder.exists():
        return []
    return sorted([d for d in folder.iterdir() if d.is_dir() and not d.name.startswith("__")])


# Markers for auto-generated section in .gitignore
GITIGNORE_START_MARKER = "# >>> AUTO-GENERATED SYMLINKS (do not edit manually) >>>"
GITIGNORE_END_MARKER = "# <<< AUTO-GENERATED SYMLINKS <<<"


def update_gitignore(script_dir: Path, symlink_paths: list[str]):
    """
    Update .gitignore with the created symlinks.
    Preserves existing entries and replaces only the auto-generated section.
    """
    gitignore_path = script_dir / ".gitignore"
    
    # Read existing content
    existing_content = ""
    if gitignore_path.exists():
        existing_content = gitignore_path.read_text(encoding="utf-8")
    
    # Remove old auto-generated section if it exists
    lines = existing_content.splitlines()
    new_lines = []
    in_auto_section = False
    
    for line in lines:
        if line.strip() == GITIGNORE_START_MARKER:
            in_auto_section = True
            continue
        elif line.strip() == GITIGNORE_END_MARKER:
            in_auto_section = False
            continue
        
        if not in_auto_section:
            new_lines.append(line)
    
    # Remove trailing empty lines from existing content
    while new_lines and new_lines[-1].strip() == "":
        new_lines.pop()
    
    # Build new content
    final_content = "\n".join(new_lines)
    
    # Add auto-generated section if there are symlinks
    if symlink_paths:
        if final_content:
            final_content += "\n\n"
        final_content += GITIGNORE_START_MARKER + "\n"
        for path in sorted(symlink_paths):
            final_content += path + "\n"
        final_content += GITIGNORE_END_MARKER + "\n"
    elif final_content:
        final_content += "\n"
    
    # Write back to .gitignore
    gitignore_path.write_text(final_content, encoding="utf-8")
    print(f"Updated .gitignore with {len(symlink_paths)} symlink entries.")


def main():
    # Get script directory and load config
    script_dir = Path(__file__).parent.resolve()
    config_path = script_dir / "calibration_links.toml"
    
    config = load_config(config_path)
    
    # Parse config
    source_base = Path(config.get("source_base", ""))
    
    # Handle both single string and list formats for backward compatibility
    calibrations_source = config.get("calibrations_source", [])
    if isinstance(calibrations_source, str):
        calibrations_source = [calibrations_source] if calibrations_source else []
    
    calibration_utils_source = config.get("calibration_utils_source", [])
    if isinstance(calibration_utils_source, str):
        calibration_utils_source = [calibration_utils_source] if calibration_utils_source else []

    if not source_base:
        print("ERROR: 'source_base' not defined in config file.")
        sys.exit(1)

    print()
    print("=" * 60)
    print("Creating symbolic links for calibration files")
    print(f"Config: {config_path}")
    print(f"Source base: {source_base}")
    print("=" * 60)

    # Check admin privileges on Windows
    if sys.platform == "win32" and not is_admin():
        print()
        print("WARNING: Not running as Administrator.")
        print("Symbolic links may fail on Windows without admin privileges.")
        print("Right-click and 'Run as administrator' if needed.")
        print()

    success_count = 0
    fail_count = 0
    created_symlinks = []  # Track successfully created symlinks for .gitignore

    # === Process calibrations folder (files) ===
    if calibrations_source:
        print()
        print("=== CALIBRATIONS FOLDER (files) ===")
        file_index = 0
        for source_rel in calibrations_source:
            calibrations_source_path = source_base / source_rel
            print()
            print(f"Source: {calibrations_source_path}")
            
            if not calibrations_source_path.exists():
                print(f"   ERROR: Source folder does not exist!")
                continue
            
            py_files = get_py_files(calibrations_source_path)
            if not py_files:
                print("   No .py files found in source folder.")
                continue
            
            print(f"   Found {len(py_files)} .py file(s)")
            for target_path in py_files:
                file_index += 1
                link_name = target_path.name
                link_path = script_dir / "calibrations" / link_name

                print()
                print(f"[{file_index}] {link_name}")

                if create_symlink(link_path, target_path, is_directory=False):
                    success_count += 1
                    # Use forward slash for .gitignore compatibility
                    created_symlinks.append(f"calibrations/{link_name}")
                else:
                    fail_count += 1

    # === Process calibration_utils folder (directories) ===
    if calibration_utils_source:
        print()
        print("=== CALIBRATION_UTILS FOLDER (directories) ===")
        folder_index = 0
        for source_rel in calibration_utils_source:
            utils_source_path = source_base / source_rel
            print()
            print(f"Source: {utils_source_path}")
            
            if not utils_source_path.exists():
                print(f"   ERROR: Source folder does not exist!")
                continue
            
            subfolders = get_subfolders(utils_source_path)
            if not subfolders:
                print("   No subfolders found in source folder.")
                continue
            
            print(f"   Found {len(subfolders)} subfolder(s)")
            for target_path in subfolders:
                folder_index += 1
                link_name = target_path.name
                link_path = script_dir / "calibration_utils" / link_name

                print()
                print(f"[{folder_index}] {link_name}")

                if create_symlink(link_path, target_path, is_directory=True):
                    success_count += 1
                    # Use forward slash and trailing slash for directories
                    created_symlinks.append(f"calibration_utils/{link_name}/")
                else:
                    fail_count += 1

    # Update .gitignore with created symlinks
    print()
    print("=== UPDATING .gitignore ===")
    update_gitignore(script_dir, created_symlinks)

    print()
    print("=" * 60)
    print(f"Done. Success: {success_count}, Failed: {fail_count}")
    print("=" * 60)

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
