"""Exercise the console entry point used by Docker, not python -m alembic."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

def test_console_migration_from_another_directory(tmp_path):
    backend=Path(__file__).resolve().parents[1]
    executable=shutil.which('alembic') or str(Path(sys.executable).parent/'alembic')
    if not Path(executable).exists():
        executable=str(Path.home()/'.local/bin/alembic')
    env={**os.environ,'DATABASE_URL':'sqlite:///'+str(tmp_path/'migration.db')}
    env.pop('PYTHONPATH',None)
    for command in ['upgrade','current']:
        args=[executable,'-c',str(backend/'alembic.ini'),command]
        if command=='upgrade': args.append('head')
        result=subprocess.run(args,cwd=tmp_path,env=env,capture_output=True,text=True)
        assert result.returncode==0,result.stdout+result.stderr
        if command=='current': assert '0001' in result.stdout
