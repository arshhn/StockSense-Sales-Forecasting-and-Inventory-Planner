"""Download the original UCI workbook without substituting other data."""
from pathlib import Path
from urllib.request import Request, urlopen
import hashlib
import shutil
import zipfile

SOURCE_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
WORKBOOK = "online_retail_II.xlsx"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(directory: Path) -> Path:
    """Reuse an existing workbook, or extract only the named file from UCI."""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / WORKBOOK
    if target.exists():
        return target
    archive = directory / "online_retail_ii.zip"
    temporary = directory / "download.part"
    try:
        request = Request(SOURCE_URL, headers={"User-Agent": "StockSense/0.1 (student project)"})
        with urlopen(request, timeout=120) as response, temporary.open("wb") as out:
            shutil.copyfileobj(response, out)
        temporary.replace(archive)
        with zipfile.ZipFile(archive) as bundle:
            names = [n for n in bundle.namelist() if Path(n).name == WORKBOOK]
            if len(names) != 1:
                raise ValueError("UCI archive did not contain the expected workbook.")
            with bundle.open(names[0]) as source, temporary.open("wb") as out:
                shutil.copyfileobj(source, out)
        temporary.replace(target)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            "Automatic download failed. Open https://archive.ics.uci.edu/dataset/502/online+retail+ii, "
            "click Download, unzip online_retail_ii.zip, and copy online_retail_II.xlsx to "
            f"{directory.resolve()}. Then run python -m stocksense prepare. Details: {exc}"
        ) from exc
    return target
