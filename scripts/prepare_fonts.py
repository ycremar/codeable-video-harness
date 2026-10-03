"""Restore the original licensed CJK font offline; never replace unknown bytes."""
from pathlib import Path
import hashlib
import lzma
import os
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RELATIVE = Path("assets/fonts/NotoSerifSC.ttf")
SIZE = 25_125_512
SHA256 = "050080d9255a86808f2945bffac582b31ef32bc36411ce29563b4961670c66f9"


def restore(root=ROOT):
    destination = Path(root) / RELATIVE
    if destination.exists():
        if destination.stat().st_size != SIZE or hashlib.sha256(destination.read_bytes()).hexdigest() != SHA256:
            raise ValueError("Existing NotoSerifSC.ttf has unexpected bytes; refusing to overwrite it")
        return destination
    source = destination.with_suffix(".ttf.xz")
    temporary = None
    try:
        h, total = hashlib.sha256(), 0
        with lzma.open(source, "rb") as archive, tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as target:
            temporary = Path(target.name)
            for chunk in iter(lambda: archive.read(1024 * 1024), b""):
                total += len(chunk)
                if total > SIZE:
                    raise ValueError("Font archive exceeds the expected original size")
                target.write(chunk)
                h.update(chunk)
        if total != SIZE or h.hexdigest() != SHA256:
            raise ValueError("Font checksum mismatch; destination was not created")
        os.replace(temporary, destination)
        temporary = None
        return destination
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    print(f"Verified original font: {restore()}")
