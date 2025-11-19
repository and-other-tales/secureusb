#!/usr/bin/env python3
"""
Extract all functions from Python files in src/ directory and generate CSV inventory.
Extracts: module-level functions, class methods, static methods, class methods, private functions.
"""

import ast
import csv
import os
from pathlib import Path
from typing import List, Tuple


class FunctionExtractor(ast.NodeVisitor):
    """AST visitor to extract all function definitions."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.functions: List[Tuple[str, str, int]] = []
        self.current_class = None

    def visit_ClassDef(self, node: ast.ClassDef):
        """Visit class definition and extract methods."""
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Visit function definition."""
        if self.current_class:
            # Method within a class
            function_name = f"{self.current_class}.{node.name}"
        else:
            # Module-level function
            function_name = node.name

        self.functions.append((function_name, self.filepath, node.lineno))

        # Continue visiting nested functions
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Visit async function definition."""
        if self.current_class:
            function_name = f"{self.current_class}.{node.name}"
        else:
            function_name = node.name

        self.functions.append((function_name, self.filepath, node.lineno))
        self.generic_visit(node)


def extract_functions_from_file(filepath: Path) -> List[Tuple[str, str, int]]:
    """Extract all functions from a Python file using AST parsing."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content, filename=str(filepath))
        extractor = FunctionExtractor(str(filepath))
        extractor.visit(tree)
        return extractor.functions

    except SyntaxError as e:
        print(f"Syntax error in {filepath}: {e}")
        return []
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return []


EXCLUDE_DIRS = {
    '__pycache__',
    '.git',
    '.mypy_cache',
    '.pytest_cache',
    '.venv',
    'venv',
    'build',
    'dist',
}


def scan_directory(directory: Path) -> List[Tuple[str, str, int]]:
    """Recursively scan directory for Python files and extract functions."""
    all_functions = []

    # Walk through directory
    for root, dirs, files in os.walk(directory):
        # Skip directories we never want to inspect
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        for filename in sorted(files):
            if filename.endswith('.py'):
                filepath = Path(root) / filename
                print(f"Scanning: {filepath}")
                functions = extract_functions_from_file(filepath)
                all_functions.extend(functions)
                print(f"  Found {len(functions)} functions")

    return all_functions


def generate_csv(functions: List[Tuple[str, str, int]], output_path: Path):
    """Generate CSV file with function inventory."""
    # Sort by file path, then line number
    functions.sort(key=lambda x: (x[1], x[2]))

    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['function_name', 'py_file', 'line_number'])

        for function_name, filepath, line_number in functions:
            # Convert to relative path from project root
            rel_path = os.path.relpath(filepath, '/home/david/secureusb')
            writer.writerow([function_name, rel_path, line_number])

    print(f"\nGenerated {output_path}")
    print(f"Total functions: {len(functions)}")


def main():
    """Main function to extract functions and generate CSV."""
    src_dir = Path('/home/david/secureusb')
    output_csv = Path('/home/david/secureusb/function_inventory.csv')

    print("=" * 70)
    print("Function Inventory Generator")
    print("=" * 70)
    print(f"Scanning directory: {src_dir}")
    print(f"Output CSV: {output_csv}")
    print("=" * 70)
    print()

    # Extract all functions
    all_functions = scan_directory(src_dir)

    # Generate CSV
    generate_csv(all_functions, output_csv)

    print()
    print("=" * 70)
    print("Summary by File:")
    print("=" * 70)

    # Group by file for summary
    by_file = {}
    for function_name, filepath, line_number in all_functions:
        rel_path = os.path.relpath(filepath, '/home/david/secureusb')
        if rel_path not in by_file:
            by_file[rel_path] = []
        by_file[rel_path].append(function_name)

    for filepath in sorted(by_file.keys()):
        print(f"{filepath}: {len(by_file[filepath])} functions")

    print("=" * 70)


if __name__ == '__main__':
    main()
