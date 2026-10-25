"""Inline the Virgil font so the prototype works as a single self-contained page (an Artifact)."""
import base64, pathlib, sys

here = pathlib.Path(__file__).parent
src = (here / "board.html").read_text()
font = base64.b64encode((here / "fonts/Virgil-Regular.woff2").read_bytes()).decode()
ref = 'url("fonts/Virgil-Regular.woff2")'
assert ref in src, "font reference not found"
out = pathlib.Path(sys.argv[1])
out.write_text(src.replace(ref, f'url("data:font/woff2;base64,{font}")'))
print(out, out.stat().st_size)
