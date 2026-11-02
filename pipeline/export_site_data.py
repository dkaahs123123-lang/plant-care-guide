"""plants.db에서 웹사이트가 읽을 정적 JSON 파일을 만든다.

사용법:
    python -I pipeline/export_site_data.py data/plants.db site/data

만들어지는 파일
    meta.json            출처와 전체 개수
    families.json        [과, 속 수, 종 수]
    genera.json          [속, 과, 종 수]
    sp/<키>.json         속 이름 앞 두 글자별 종 목록 {속: [[id, 나머지 이름, 저자, 연도, [이명...]]]}
    syn/<키>.json        이명 앞 두 글자별 [[이명, 저자, 받아들여진 id, 받아들여진 학명]]
"""
import json
import re
import shutil
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

RANKS = ("species", "subspecies", "variety", "form")
MAX_SYNS_PER_TAXON = 30


def key_for(name):
    letters = re.sub(r"[^a-z]", "", (name or "").lower())
    return (letters[:2] or "__").ljust(2, "_")


def short_id(wfo_id):
    return wfo_id[4:] if wfo_id.startswith("wfo-") else wfo_id


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def main(db_path, out_dir):
    out = Path(out_dir)
    for sub in ("sp", "syn"):
        shutil.rmtree(out / sub, ignore_errors=True)
    con = sqlite3.connect(db_path)
    marks = ",".join("?" * len(RANKS))

    syns_of = defaultdict(list)
    syn_buckets = defaultdict(list)
    accepted = {
        tid: name
        for tid, name in con.execute(f"SELECT id, name FROM taxa WHERE rank IN ({marks})", RANKS)
    }
    for sname, sauthor, acc in con.execute("SELECT name, author, accepted_id FROM synonyms ORDER BY name"):
        if acc not in accepted:
            continue
        if len(syns_of[acc]) < MAX_SYNS_PER_TAXON:
            syns_of[acc].append(sname)
        syn_buckets[key_for(sname)].append([sname, sauthor or "", short_id(acc), accepted[acc]])

    sp_buckets = defaultdict(lambda: defaultdict(list))
    genus_count = defaultdict(int)
    for tid, name, author, rank, genus, year in con.execute(
        f"SELECT id, name, author, rank, genus, year FROM taxa WHERE rank IN ({marks}) ORDER BY name", RANKS
    ):
        genus = genus or name.split(" ")[0]
        rest = name[len(genus):].strip() if name.startswith(genus) else name
        sp_buckets[key_for(genus)][genus].append([short_id(tid), rest, author or "", year or "", syns_of.get(tid, [])])
        if rank == "species":
            genus_count[genus] += 1

    genera = []
    for name, family in con.execute("SELECT name, family FROM taxa WHERE rank = 'genus' ORDER BY name"):
        genera.append([name, family or "", genus_count.get(name, 0)])

    fam_genera, fam_species = defaultdict(int), defaultdict(int)
    for g, fam, n in genera:
        fam_genera[fam] += 1
        fam_species[fam] += n
    families = [
        [f, fam_genera[f], fam_species[f]]
        for (f,) in con.execute("SELECT name FROM taxa WHERE rank = 'family' ORDER BY name")
    ]

    src = con.execute("SELECT id, title, version, issued, doi, license, url, citation FROM sources").fetchall()
    meta = {
        "sources": [dict(zip(("id", "title", "version", "issued", "doi", "license", "url", "citation"), s)) for s in src],
        "counts": {
            "species": con.execute("SELECT COUNT(*) FROM taxa WHERE rank='species'").fetchone()[0],
            "infraspecific": con.execute("SELECT COUNT(*) FROM taxa WHERE rank IN ('subspecies','variety','form')").fetchone()[0],
            "genera": len(genera),
            "families": len(families),
            "synonyms": sum(len(v) for v in syn_buckets.values()),
        },
    }

    dump(out / "meta.json", meta)
    dump(out / "genera.json", genera)
    dump(out / "families.json", families)
    for k, v in sp_buckets.items():
        dump(out / "sp" / f"{k}.json", v)
    for k, v in syn_buckets.items():
        dump(out / "syn" / f"{k}.json", v)

    sizes = sorted(((p.stat().st_size, p.relative_to(out).as_posix()) for p in out.rglob("*.json")), reverse=True)
    total = sum(s for s, _ in sizes)
    print(f"files: {len(sizes):,}  total: {total / 1e6:.1f} MB")
    print("largest:", ", ".join(f"{p} {s / 1e6:.1f}MB" for s, p in sizes[:5]))
    print(json.dumps(meta["counts"]))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1], sys.argv[2])
