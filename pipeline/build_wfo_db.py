"""1단계: WFO Plant List(ColDP zip)를 SQLite 데이터베이스로 변환한다.

사용법:
    python -I pipeline/build_wfo_db.py data/raw/wfo-2026-06/wfo_plantlist_2026-06.zip data/plants.db

만들어지는 테이블
    sources   데이터 출처(인용, 라이선스, 버전)
    taxa      받아들여진(accepted) 분류군. 과(family)와 속(genus)을 계산해 둔다.
    synonyms  이명(synonym) -> 받아들여진 분류군 연결
"""
import csv
import io
import json
import sqlite3
import sys
import zipfile
from pathlib import Path

csv.field_size_limit(10_000_000)

SOURCE_ID = "wfo-2026-06"


def rows(zf, name):
    with zf.open(name) as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", newline=""), delimiter="\t", quotechar='"')
        yield from reader


def main(zip_path, db_path):
    zf = zipfile.ZipFile(zip_path)
    meta = json.loads(zf.read("metadata.json"))

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.executescript("""
        PRAGMA journal_mode = OFF;
        PRAGMA synchronous = OFF;
        CREATE TABLE sources (
            id TEXT PRIMARY KEY, title TEXT, version TEXT, issued TEXT,
            doi TEXT, license TEXT, url TEXT, citation TEXT
        );
        CREATE TABLE names (
            id TEXT PRIMARY KEY, name TEXT, author TEXT, rank TEXT,
            genus TEXT, year TEXT
        );
        CREATE TABLE taxon_raw (id TEXT PRIMARY KEY, name_id TEXT, parent_id TEXT, link TEXT);
        CREATE TABLE synonym_raw (name_id TEXT, taxon_id TEXT);
    """)

    con.execute(
        "INSERT INTO sources VALUES (?,?,?,?,?,?,?,?)",
        (
            SOURCE_ID,
            meta.get("title"),
            meta.get("version"),
            meta.get("issued"),
            meta.get("doi"),
            "CC0 1.0",
            "https://wfoplantlist.org",
            f"WFO ({meta.get('issued', '')[:4]}): {meta.get('title')}. https://doi.org/{meta.get('doi')}",
        ),
    )

    print("names ...", flush=True)
    con.executemany(
        "INSERT INTO names VALUES (?,?,?,?,?,?)",
        (
            (r["ID"], r["scientificName"], r["authorship"], r["rank"], r["genus"], r["publishedInYear"])
            for r in rows(zf, "name.tsv")
        ),
    )
    print("taxa ...", flush=True)
    con.executemany(
        "INSERT INTO taxon_raw VALUES (?,?,?,?)",
        ((r["ID"], r["nameID"], r["parentID"], r["link"]) for r in rows(zf, "taxon.tsv")),
    )
    print("synonyms ...", flush=True)
    con.executemany(
        "INSERT INTO synonym_raw VALUES (?,?)",
        ((r["nameID"], r["taxonID"]) for r in rows(zf, "synonym.tsv")),
    )
    con.commit()

    # 상위 분류를 따라 올라가며 과(family)를 찾는다.
    print("families ...", flush=True)
    parent, rank_of, name_of = {}, {}, {}
    for tid, pid, rank, name in con.execute(
        "SELECT t.id, t.parent_id, n.rank, n.name FROM taxon_raw t JOIN names n ON n.id = t.name_id"
    ):
        parent[tid], rank_of[tid], name_of[tid] = pid, rank, name

    family_cache = {}

    def family(tid):
        path = []
        cur = tid
        while cur and cur not in family_cache:
            path.append(cur)
            if rank_of.get(cur) == "family":
                family_cache[cur] = name_of[cur]
                break
            cur = parent.get(cur)
            if len(path) > 60:
                break
        found = family_cache.get(cur)
        for p in path:
            family_cache[p] = found
        return found

    con.execute("""
        CREATE TABLE taxa (
            id TEXT PRIMARY KEY, name TEXT, author TEXT, rank TEXT,
            family TEXT, genus TEXT, parent_id TEXT, year TEXT, link TEXT, source_id TEXT
        )
    """)
    batch = []
    for tid, name, author, rank, genus, pid, year, link in con.execute(
        "SELECT t.id, n.name, n.author, n.rank, n.genus, t.parent_id, n.year, t.link "
        "FROM taxon_raw t JOIN names n ON n.id = t.name_id"
    ).fetchall():
        batch.append((tid, name, author, rank, family(tid), genus or None, pid, year, link, SOURCE_ID))
    con.executemany("INSERT INTO taxa VALUES (?,?,?,?,?,?,?,?,?,?)", batch)

    con.executescript("""
        CREATE TABLE synonyms AS
            SELECT s.name_id AS id, n.name, n.author, n.rank, s.taxon_id AS accepted_id
            FROM synonym_raw s JOIN names n ON n.id = s.name_id;
        CREATE INDEX taxa_name ON taxa(name);
        CREATE INDEX taxa_rank ON taxa(rank);
        CREATE INDEX taxa_family ON taxa(family);
        CREATE INDEX syn_name ON synonyms(name);
        CREATE INDEX syn_acc ON synonyms(accepted_id);
        DROP TABLE taxon_raw;
        DROP TABLE synonym_raw;
        DROP TABLE names;
    """)
    con.commit()

    for label, sql in [
        ("accepted taxa", "SELECT COUNT(*) FROM taxa"),
        ("accepted species", "SELECT COUNT(*) FROM taxa WHERE rank='species'"),
        ("genera", "SELECT COUNT(*) FROM taxa WHERE rank='genus'"),
        ("families", "SELECT COUNT(*) FROM taxa WHERE rank='family'"),
        ("species without family", "SELECT COUNT(*) FROM taxa WHERE rank='species' AND family IS NULL"),
        ("synonyms", "SELECT COUNT(*) FROM synonyms"),
    ]:
        print(f"{label}: {con.execute(sql).fetchone()[0]:,}")
    con.execute("VACUUM")
    con.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1], sys.argv[2])
