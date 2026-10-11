"""Build ForgeGUI clips from specs: uv run python streams/clipping/campaigns/forgegui/build_specs.py <spec module>... [--v N]"""
import importlib.util, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from fgclip import build
v = sys.argv[sys.argv.index("--v") + 1] if "--v" in sys.argv else "1"
for name in [a for a in sys.argv[1:] if a.endswith(".py")]:
    p = Path(__file__).parent / "specs" / name
    spec = importlib.util.spec_from_file_location(p.stem, p); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    build(m.SPEC, v, "spec build")
