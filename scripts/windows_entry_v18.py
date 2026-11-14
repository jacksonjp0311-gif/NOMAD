"""Offline source installation and Windows launcher; no policy changes or downloads."""
from pathlib import Path
import os
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if sys.version_info < (3, 11):
        raise SystemExit('Python 3.11+ is required')
    environment = ROOT / '.venv'
    python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if arguments == ['setup']:
        if not python.exists():
            venv.EnvBuilder(with_pip=False).create(environment)
        site = subprocess.check_output([str(python), '-I', '-c',
                                        'import site; print(site.getsitepackages()[-1])'], text=True).strip()
        destination = Path(site).resolve()
        if not destination.is_relative_to(environment.resolve()):
            raise SystemExit('refusing a site-packages path outside the local virtual environment')
        (destination / 'nomad_source.pth').write_text(str(ROOT) + '\n', encoding='utf-8')
        result = subprocess.run([str(python), '-I', '-B', '-c',
                                 'import nomad; print("NOMAD", nomad.__version__)'], cwd=ROOT)
        if result.returncode:
            return result.returncode
        arguments = ['doctor']
    if not python.exists():
        raise SystemExit('Run NOMAD.cmd setup (or python scripts/windows_entry_v18.py setup) first.')
    if arguments == ['verify']:
        command = [str(python), '-I', '-B', str(ROOT / 'scripts/verify_package_v18.py')]
    else:
        command = [str(python), '-I', '-B', '-m', 'nomad.platform_cli', *(arguments or ['doctor'])]
    return subprocess.run(command, cwd=ROOT).returncode


if __name__ == '__main__':
    raise SystemExit(main())
