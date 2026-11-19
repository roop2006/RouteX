"""Fail on high/critical advisories except one time-limited dev-only finding.

The production dependency audit has no exceptions. See SECURITY_AND_CREDITS.md.
"""
from datetime import date
import json
import shutil
import subprocess
import sys

KNOWN_DEV_ADVISORY = 'https://github.com/advisories/GHSA-fc5q-39xc-vjpf'
REVIEW_BY = date(2026, 12, 18)


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
    unexpected = []
    known = False
    for name, package in full.get('vulnerabilities', {}).items():
        for advisory in package.get('via', []):
            if not isinstance(advisory, dict) or advisory.get('severity') not in ('high', 'critical'):
                continue
            if name == 'picomatch' and advisory.get('url') == KNOWN_DEV_ADVISORY and date.today() <= REVIEW_BY:
                known = True
            else:
                unexpected.append((name, advisory.get('url')))
    if known:
        print(f'KNOWN DEV-ONLY EXCEPTION: {KNOWN_DEV_ADVISORY}; no patched release; review by {REVIEW_BY}.')
    for name, url in unexpected:
        print(f'BLOCKED: {name}: {url}')
    if not full.get('vulnerabilities'):
        print('Full dependency audit: no known vulnerabilities.')
    return bool(unexpected)


if __name__ == '__main__':
    sys.exit(main())
