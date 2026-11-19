"""Conservative publication guard. Prints paths, never matching secret values."""
from pathlib import Path
import re
import subprocess
import sys

PATTERNS = [rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
            rb'gh[pousr]_[A-Za-z0-9]{30,}', rb'AKIA[A-Z0-9]{16}']


def main():
    paths = subprocess.check_output(['git', 'ls-files', '-z']).decode().split('\0')
    findings = []
    for relative in filter(None, paths):
        path = Path(relative)
        if not path.is_file():
            continue
        if path.name == '.env' or (path.name.startswith('.env.') and path.name != '.env.example'):
            findings.append((relative, 'private environment file'))
        data = path.read_bytes()
        if len(data) > 25 * 1024 * 1024:
            findings.append((relative, 'large file >25 MiB'))
        if any(re.search(pattern, data) for pattern in PATTERNS):
            findings.append((relative, 'credential pattern'))
    for path, reason in findings:
        print(f'{path}: {reason}')
    print(f'Repository guard: {len(findings)} finding(s). Review is also required.')
    return bool(findings)


if __name__ == '__main__':
    sys.exit(main())
