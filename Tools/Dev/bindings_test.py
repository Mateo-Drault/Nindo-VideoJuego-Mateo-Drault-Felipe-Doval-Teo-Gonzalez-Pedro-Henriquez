"""
Pruebas de la tabla de controles reasignables SIN abrir Unity.

Compila Input/BindingTable.cs, Input/BindingCatalog.cs y Tools/Dev/bindings_test/BindingsTest.cs como un programa
de consola (dotnet) con la DLL del Input System del proyecto (solo usa sus enums Key y GamepadButton) y lo corre:
las de fábrica sin choques e iguales a las del InputReader de antes, intercambios, rechazos, quitar, guardar y
cargar, la llegada de una acción nueva (el mapa) y cientos de miles de cambios al azar.

Uso:
  python Tools/Dev/bindings_test.py [--project RUTA_AL_PROYECTO_UNITY_CON_LIBRARY] [--src RUTA_Assets]

Sale con código 0 si todo pasa. Requisitos: dotnet SDK y haber abierto el proyecto en Unity (Library/ScriptAssemblies).
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None, help="proyecto Unity con Library/ScriptAssemblies")
    ap.add_argument("--src", default=os.path.join(REPO, "Nindo", "Assets"), help="carpeta Assets con los .cs a probar")
    a = ap.parse_args()

    project = a.project
    if project is None:
        # como compile_check: los worktrees viven en <principal>/.claude/worktrees/<x>
        cand = [os.path.join(REPO, "Nindo")]
        m = re.search(r"^(.*)[\\/]\.claude[\\/]worktrees[\\/][^\\/]+$", REPO)
        if m:
            cand.insert(0, os.path.join(m.group(1), "Nindo"))
        project = next((c for c in cand if os.path.exists(os.path.join(c, "Library", "ScriptAssemblies", "Unity.InputSystem.dll"))), None)
    dll = os.path.join(project or "", "Library", "ScriptAssemblies", "Unity.InputSystem.dll")
    if not os.path.exists(dll):
        sys.exit("No encuentro Library/ScriptAssemblies/Unity.InputSystem.dll: abrí el proyecto en Unity una vez o pasá --project")

    scripts = os.path.join(os.path.abspath(a.src), "Nindo", "Scripts", "Input")
    files = [os.path.join(scripts, "BindingTable.cs"), os.path.join(scripts, "BindingCatalog.cs"),
             os.path.join(HERE, "bindings_test", "BindingsTest.cs")]
    items = "".join('\n    <Compile Include="%s" />' % f for f in files)
    proj_text = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net9.0</TargetFramework>
    <LangVersion>9.0</LangVersion>
    <Nullable>disable</Nullable>
    <EnableDefaultCompileItems>false</EnableDefaultCompileItems>
    <NoWarn>CS0618</NoWarn>
  </PropertyGroup>
  <ItemGroup>%s
    <Reference Include="Unity.InputSystem"><HintPath>%s</HintPath><Private>true</Private></Reference>
  </ItemGroup>
</Project>
""" % (items, dll)
    # carpeta temporal propia que se borra al terminar (varios agentes compilan a la vez)
    tmp = tempfile.mkdtemp(prefix="nindo_bt_")
    try:
        proj = os.path.join(tmp, "BindingsTest.csproj")
        open(proj, "w", encoding="utf-8").write(proj_text)
        r = subprocess.run(["dotnet", "run", "--project", proj, "-v:q", "-nologo"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", cwd=tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
