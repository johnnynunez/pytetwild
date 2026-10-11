"""Build exact PyTetWild 0.3.0; keep [all]/upstream test gate mandatory."""
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import sysconfig

assert sys.platform == 'win32' and sysconfig.get_platform() == 'win-arm64'
root = Path(os.environ['GITHUB_WORKSPACE'])
source = root / 'source'
out = root / 'evidence'
out.mkdir(exist_ok=True)
work = Path(os.environ['RUNNER_TEMP']) / 'geometry-tet'
work.mkdir(exist_ok=True)
for key in ('PIP_CACHE_DIR', 'CIBW_CACHE_PATH', 'NUGET_PACKAGES', 'NUGET_HTTP_CACHE_PATH', 'NUGET_PLUGINS_CACHE_PATH', 'VIRTUALENV_OVERRIDE_APP_DATA', 'UV_CACHE_DIR', 'UV_PYTHON_INSTALL_DIR', 'UV_PYTHON_BIN_DIR'):
    os.environ[key] = str(work / key)
os.environ['CMAKE_BUILD_PARALLEL_LEVEL'] = '4'
os.environ['CMAKE_GENERATOR'] = 'Ninja'
os.environ['VCPKG_DEFAULT_BINARY_CACHE'] = str(work/'vcpkg-cache')
(work/'vcpkg-cache').mkdir(exist_ok=True)
log = (out/'commands.log').open('a', encoding='utf-8')

def run(args, cwd=work):
    print('RUN', args, flush=True); log.write('RUN '+repr(args)+'\n'); log.flush()
    proc = subprocess.Popen([str(x) for x in args], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
    for line in proc.stdout:
        print(line, end='', flush=True); log.write(line); log.flush()
    code = proc.wait()
    if code:
        raise subprocess.CalledProcessError(code, args)

sha = subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
assert sha == 'eea46df87ef58e861956b7a710f42ab58eaa02a0'
(out/'provenance.json').write_text(json.dumps({'source_sha':sha,'python':sys.version,'platform':platform.platform(),'gpu':False,'vtk_required':'9.6.2','full_extra_required':'pytetwild[all,tests]','vcpkg_sha':'e456309491fd875487bf02b8a0dca76c1b1b00cc'},indent=2))
run([sys.executable,'-m','pip','install','build','cmake==3.29.6','ninja','delvewheel','pefile','numpy','pytest','pytest-timeout'])
run(['git','clone','https://github.com/microsoft/vcpkg.git',work/'vcpkg','--filter=blob:none','--no-checkout'])
run(['git','checkout','e456309491fd875487bf02b8a0dca76c1b1b00cc'],work/'vcpkg')
run(['cmd','/c',work/'vcpkg/bootstrap-vcpkg.bat','-disableMetrics'])
triplets = work/'triplets';triplets.mkdir(exist_ok=True)
(triplets/'arm64-native.cmake').write_text('set(VCPKG_TARGET_ARCHITECTURE arm64)\nset(VCPKG_CRT_LINKAGE dynamic)\nset(VCPKG_LIBRARY_LINKAGE static)\nset(VCPKG_BUILD_TYPE release)\nset(VCPKG_PLATFORM_TOOLSET v143)\nset(VCPKG_PLATFORM_TOOLSET_VERSION 14.44)\n')
run([work/'vcpkg/vcpkg.exe','install','gmp:arm64-native',f'--overlay-triplets={triplets}','--host-triplet=arm64-native','--disable-metrics'])
os.environ['GMP_INC'] = str(work/'vcpkg/installed/arm64-native/include')
os.environ['GMP_LIB'] = str(work/'vcpkg/installed/arm64-native/lib')
try:
    run([sys.executable,'-m','build','--wheel','--outdir',out/'raw'],source)
finally:
    for name in ('CMakeCache.txt','compile_commands.json'):
        candidate = source/'build'/name
        if candidate.exists():
            shutil.copy(candidate,out/name)
deps = work/'deps';deps.mkdir(exist_ok=True)
for file in (source/'build').rglob('*.dll'):
    shutil.copy(file,deps/file.name)
wheel = next((out/'raw').glob('*.whl'))
run([sys.executable,'-m','delvewheel','repair','--add-path',deps,'-w',out/'wheels',wheel])
run([sys.executable,root/'ci/native/wheel_audit.py',out/'wheels',out/'wheel-audit.json'])
run([sys.executable,'-m','venv',work/'test-venv'])
py = work/'test-venv/Scripts/python.exe'
wheel = next((out/'wheels').glob('*.whl'))
run([py,'-m','pip','install',wheel,'numpy','pytest','pytest-timeout'])
run([py,'-m','pytest',root/'ci/native/test_tet_native.py','-v','--timeout=300',f'--junitxml={out/"native-oracle.xml"}'])
# Do not omit or turn a missing VTK into a green feature skip.
run([py,'-m','pip','install',f'{wheel}[all,tests]','vtk==9.6.2','pyvista==0.48.4','--only-binary=:all:'])
run([py,'-m','pytest',source/'tests','-v','--timeout=300',f'--junitxml={out/"upstream.xml"}'])
(out/'PASS').write_text('Native build, repaired wheel, numerical oracle and complete [all]/upstream suite passed. CPU only.\n')
