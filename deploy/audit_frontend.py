"""Fail on high/critical npm advisories, including development dependencies."""
import json
import shutil
import subprocess
import sys


def audit(*extra):
    command = [shutil.which('npm'), '--prefix', 'frontend', 'audit', '--json', *extra]
    result = subprocess.run(command, capture_output=True, text=True)
    try:
        report = json.loads(result.stdout)
    except ValueError:
        raise RuntimeError('npm audit did not return a valid report')
    if report.get('error') or result.returncode not in (0, 1):
        raise RuntimeError('npm audit service failed; security check is incomplete')
    return report


def main():
    production = audit('--omit=dev')
    counts = production['metadata']['vulnerabilities']
    print('Production dependency advisories:', counts)
    if counts['high'] or counts['critical']:
        return 1
    full = audit()
    counts = full['metadata']['vulnerabilities']
    print('Full dependency advisories:', counts)
    return bool(counts['high'] or counts['critical'])


if __name__ == '__main__':
    sys.exit(main())
