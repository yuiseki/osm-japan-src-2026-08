#!/usr/bin/env python3
"""Verify the Japan extract.

Three checks, and the third is the one that matters. A clip can look fine by
every count and still have dropped a single boundary way, which silently costs
that prefecture its Overpass area: the ring no longer closes, area generation
skips it, and `area["name"="東京都"]` quietly returns nothing instead of
failing. That is not hypothetical; it happened to Setagaya in the Tokyo cut of
this same snapshot, from a boundary one year older than the data.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PBF = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "japan-260831.osm.pbf"
TMP = ROOT / "tmp"

# The 47. Named rather than counted, so that a check cannot pass by finding 47
# of something else: the box reaches into Korea, Sakhalin and Taiwan, and all
# of them have admin_level=4 divisions too.
PREFECTURES = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
    "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
    "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
    "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]


# OPL escapes anything outside a small ASCII set as %XXXX%, the code point in
# hex between two per-cent signs: 大阪府 arrives as %5927%%962a%%5e9c%. A
# reader that skips this finds no prefecture at all and reports all 47 as
# missing, which is what the first version of this file did.
OPL_ESCAPE = re.compile(r"%([0-9a-fA-F]{1,6})%")


def unescape_opl(text: str) -> str:
    return OPL_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), text)


def run(cmd: list[str]) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def fileinfo() -> None:
    for line in run(["osmium", "fileinfo", "-e", str(PBF)]).splitlines():
        line = line.strip()
        if line.startswith(("Number of ", "Bounding box:")):
            print(f"  {line}")


def place_nodes() -> bool:
    """Every prefecture has a place node inside the extract."""
    out = TMP / "verify_places.osm.pbf"
    subprocess.run(
        ["osmium", "tags-filter", "-o", str(out), "--overwrite", str(PBF),
         "n/place=city,town,village,suburb,state,province"],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    seq = run(["osmium", "export", "-f", "geojsonseq", str(out)])
    names = set()
    for line in seq.replace("\x1e", "").splitlines():
        if line.strip():
            names.add(json.loads(line)["properties"].get("name"))
    # A prefecture's own place node, or failing that any place node whose name
    # is one of its cities, is not what is being asked: this checks that the
    # prefecture itself is nameable in the file.
    missing = [p for p in PREFECTURES if p not in names]
    print(f"  place ノードのある都道府県: {len(PREFECTURES) - len(missing)}/{len(PREFECTURES)}")
    if missing:
        print(f"  欠落: {missing}")
    return not missing


def prefecture_relations() -> dict[str, str]:
    """name -> relation id, for the 47 at admin_level=4."""
    rels = TMP / "verify_admin4.osm.pbf"
    subprocess.run(
        ["osmium", "tags-filter", "-o", str(rels), "--overwrite", "-R",
         str(PBF), "r/admin_level=4"],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    want = set(PREFECTURES)
    out = {}
    for line in run(["osmium", "cat", "-f", "opl", str(rels)]).splitlines():
        if not line.startswith("r"):
            continue
        m = re.search(r" T(\S*)", line)
        if not m:
            continue
        tags = dict(
            kv.split("=", 1) for kv in m.group(1).split(",") if "=" in kv)
        name = unescape_opl(tags.get("name", ""))
        if name in want and tags.get("boundary") == "administrative":
            out.setdefault(name, line.split()[0][1:])
    return out


def prefecture_rings() -> bool:
    """Every boundary way of every prefecture is present in the file."""
    rels = TMP / "verify_admin4.osm.pbf"
    ids = prefecture_relations()
    if len(ids) != len(PREFECTURES):
        print(f"  リレーションが足りない: "
              f"{sorted(set(PREFECTURES) - set(ids))}")
        return False

    members: dict[str, list[str]] = {}
    by_id = {v: k for k, v in ids.items()}
    for line in run(["osmium", "cat", "-f", "opl", str(rels)]).splitlines():
        if not line.startswith("r"):
            continue
        rid = line.split()[0][1:]
        if rid not in by_id:
            continue
        m = re.search(r" M(\S*)", line)
        members[rid] = (
            [x[1:].split("@")[0] for x in m.group(1).split(",")
             if x.startswith("w")] if m else [])

    wanted = sorted({w for ws in members.values() for w in ws})
    idfile = TMP / "verify_pref_ways.txt"
    idfile.write_text("\n".join("w" + w for w in wanted) + "\n")
    hits = TMP / "verify_pref_ways.osm.pbf"
    # Not check=True: osmium getid exits non-zero when an id is not found, and
    # that is precisely the case this function exists to report. Letting it
    # raise would turn the one detection into a traceback.
    subprocess.run(
        ["osmium", "getid", f"--id-file={idfile}", "-o", str(hits),
         "--overwrite", str(PBF)],
        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not hits.exists():
        print("  osmium getid produced nothing", file=sys.stderr)
        return False
    have = {
        line.split()[0][1:]
        for line in run(["osmium", "cat", "-f", "opl", str(hits)]).splitlines()
        if line.startswith("w")
    }

    ok = True
    for rid, ways in sorted(members.items(), key=lambda kv: by_id[kv[0]]):
        missing = [w for w in ways if w not in have]
        if missing:
            ok = False
            print(f"  {by_id[rid]} (r{rid}): way "
                  f"{len(missing)}/{len(ways)} 欠落 -> {missing[:5]}")
    print(f"  境界 way: {len(have)}/{len(wanted)}")
    if ok:
        print(f"  {len(PREFECTURES)}都道府県すべての境界 way が完全")
    return ok


def main() -> int:
    TMP.mkdir(exist_ok=True)
    print("== ファイル情報")
    fileinfo()
    print("== place ノード")
    a = place_nodes()
    print("== 都道府県境界リングの完全性")
    b = prefecture_rings()
    print()
    if a and b:
        print("すべて通過")
        return 0
    print("検証に失敗した項目があります")
    return 1


if __name__ == "__main__":
    sys.exit(main())
