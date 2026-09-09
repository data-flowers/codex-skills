#!/usr/bin/env python3
"""Run portable, offline Ptah behavioral, syntax, and reference checks."""
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote

root = Path(__file__).resolve().parents[1]
errors = []
python_files = list((root / 'scripts').rglob('*.py'))
js_files = list((root / 'scripts').rglob('*.mjs'))
for path in python_files:
    try:
        ast.parse(path.read_text(), filename=str(path))
    except SyntaxError as error:
        errors.append(str(error))
for path in js_files:
    check = subprocess.run(['node', '--check', str(path)], capture_output=True, text=True)
    if check.returncode:
        errors.append(check.stderr)
for path in root.rglob('*.md'):
    for link in re.findall(r'\]\(([^)]+)\)', path.read_text()):
        if '://' in link or link.startswith('#'):
            continue
        target = (path.parent / unquote(link.split('#')[0])).resolve()
        if not target.is_file():
            errors.append(f'{path.relative_to(root)}: missing link {link}')
for command in ([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(root/'scripts/tests')],
                ['node', '--test', str(root/'scripts/tests/airtable.test.mjs')]):
    result = subprocess.run(command, cwd=root, capture_output=True, text=True,
                            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    if result.returncode:
        errors.append(result.stdout + result.stderr)
for error in errors:
    print(error, file=sys.stderr)
print(json.dumps({'passed': not errors, 'python_files': len(python_files), 'javascript_files': len(js_files),
                  'behavioral_suites': 2, 'errors': len(errors)}))
raise SystemExit(bool(errors))
