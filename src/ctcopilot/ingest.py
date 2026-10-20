"""Run the ingestion: fetch from the API (or cache), parse, load into DuckDB.

Usage: python -m ctcopilot.ingest [--refresh]
"""

import argparse

from ctcopilot.client import StudiesClient
from ctcopilot.config import Settings
from ctcopilot.parser import parse_page
from ctcopilot.store import connect, count_studies, upsert_studies


def run(settings: Settings, use_cache: bool = True) -> None:
    client = StudiesClient(settings)
    records = []
    total_reported = None
    for page in client.iter_pages(use_cache=use_cache):
        total_reported = total_reported or page.get("totalCount")
        records.extend(parse_page(page))

    con = connect(settings.db_path)
    try:
        written = upsert_studies(con, records)
        in_table = count_studies(con)
    finally:
        con.close()

    print(f"API totalCount:        {total_reported}")
    print(
        f"Pages read:            {client.pages_from_api} from API, "
        f"{client.pages_from_cache} from cache"
    )
    print(f"Studies fetched:       {len(records)}")
    print(f"Studies loaded:        {written} (distinct nct_id)")
    print(f"Rows in studies table: {in_table}  ({settings.db_path})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh", action="store_true", help="ignore cached pages and call the API again"
    )
    args = parser.parse_args()
    run(Settings(), use_cache=not args.refresh)


if __name__ == "__main__":
    main()
