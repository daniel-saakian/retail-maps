import importlib
import sys
from dataclasses import dataclass
from pathlib import Path

_site_presentations_dir = Path(__file__).parent

@dataclass
class BrandConfig:
    code: str
    label: str
    folder: str
    report_module: str
    report_fn: str = "generate_site_report"

brands: list[BrandConfig] = [
    BrandConfig("HB", "HB Protein", "HB", "hb_site_report"),
    BrandConfig("TGG", "The Great Greek", "TGG", "tgg_site_report"),
    BrandConfig("UGT", "Unique Green Tea", "UGT", "ugt_site_report"),
    BrandConfig("Sourdough", "Sourdough & Co.", "Sourdough", "sourdough_site_report"),
    BrandConfig("MadYolks", "Mad Yolks", "MadYolks", "my_site_report"),
    BrandConfig("PokeHouse", "Poke House", "PokeHouse", "ph_site_report"),
    BrandConfig("ShareTea", "Share Tea", "ShareTea", "st_site_report"),
    BrandConfig("SpikedRich", "Spiked Rich", "SpikedRich", "sr_site_report"),
]

_by_code = {b.code: b for b in brands}

def list_brands() -> list[BrandConfig]:
    return brands

def get_brand(code: str) -> BrandConfig | None:
    return _by_code.get(code)

def _ensure_on_path(path:Path) -> None:
    p = str(path)
    if p not in sys.path:
        sys.path.insert(0,p)

def _ensure_all_brand_paths() -> None:
    _ensure_on_path(_site_presentations_dir)
    for child in _site_presentations_dir.iterdir():
        if child.is_dir() and not child.name.startswith((".", "_")):
            _ensure_on_path(child)

def generate(code: str, address: str, used_names: set | None = None) -> tuple[bytes, str]:
    _ensure_all_brand_paths()
    brand = get_brand(code)
    if not brand:
        raise ValueError(f"Unknown brand code: {code}")

    _ensure_all_brand_paths()

    report_mod = importlib.import_module(brand.report_module)
    report_fn = getattr(report_mod, brand.report_fn)
    return report_fn(address, used_names=used_names)