"""Internal wrapper that persists a child process exit code."""
import json
import os
from pathlib import Path
import subprocess
import sys

exit_path = Path(sys.argv[1])
cwd = sys.argv[2]
spec = sys.argv[3]
command = json.loads(Path(spec[1:]).read_text(encoding="utf-8") if spec.startswith("@") else spec)
Path(str(exit_path) + ".pid").write_text(str(os.getpid()), encoding="utf-8")
try:
    with Path(str(exit_path)[:-5]).open("w", encoding="utf-8") as output:
        code = subprocess.run(command, cwd=cwd, stdin=subprocess.DEVNULL,
                              stdout=output, stderr=subprocess.STDOUT).returncode
except Exception as error:
    code = 1
    Path(str(exit_path)[:-5]).write_text(str(error), encoding="utf-8")
exit_path.write_text(str(code), encoding="utf-8")
