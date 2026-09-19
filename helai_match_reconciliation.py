"""Historical reconciliation design tool -- ALREADY APPLIED, DO NOT EXECUTE AGAIN.

The reviewed 72-row target is already live. This module retains reusable
verification helpers, but its former SQL-generation CLI is permanently
disabled so an old-value transaction cannot be regenerated or applied.
"""

import argparse
import copy
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

from helai_applicant_ai_audit import load_rows
from helai_maintenance import duplicate_groups
from helai_matching_preview import DERIVED_FIELDS, build_preview
from helai_opportunity_intelligence_backfill import check_runtime_guards
from supabase_client import supabase


EXPECTED_OPPORTUNITIES = 122
EXPECTED_MATCHES = 224
EXPECTED_UNCHANGED = 152
EXPECTED_CHANGED = 72
EXPECTED_NON_ACTIONABLE = 54
EXPECTED_IMPACT = {
    "eligible_true_to_false": 44,
    "eligible_false_to_true": 0,
    "score_changes": 54,
    "readiness_changes": 54,
}
EXPECTED_MATCH_SCHEMA = {
    "id": "uuid", "user_id": "uuid", "opportunity_id": "uuid",
    "eligible": "boolean", "match_score": "integer", "readiness": "integer",
    "reasons": "text[]", "eligibility_gaps": "text[]", "readiness_gaps": "text[]",
    "created_at": "timestamp with time zone", "notified": "boolean",
    "notified_at": "timestamp with time zone", "updated_at": "timestamp with time zone",
}
PREVIEW_PATH = Path(__file__).with_name("helai_final_global_matching_preview_report.json")
SQL_PATH = Path(__file__).with_name("helai_match_reconciliation_transaction.sql")
BACKUP_DIRECTORY = Path(__file__).with_name("helai_match_reconciliation_backups")
REPORT_PATH = Path(__file__).with_name("helai_match_reconciliation_dry_run_report.json")


class SafetyError(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def duplicate_match_count(matches):
    counts = Counter((row.get("user_id"), row.get("opportunity_id")) for row in matches)
    return sum(count > 1 for count in counts.values())


def load_reviewed_preview(path=PREVIEW_PATH):
    report = json.loads(Path(path).read_text(encoding="utf-8"))
    expected = {
        "existing_matches": EXPECTED_MATCHES,
        "proposed_total_matches_after_upsert": EXPECTED_MATCHES,
        "unchanged_matches": EXPECTED_UNCHANGED,
        "eligibility_true_to_false": 44,
        "eligibility_false_to_true": 0,
        "score_changes": 54,
        "readiness_changes": 54,
        "obsolete_non_actionable_matches": EXPECTED_NON_ACTIONABLE,
    }
    actual = {key: report.get(key) for key in expected}
    if actual != expected or report.get("new_matches_proposed") != [] or report.get("errors") != []:
        raise SafetyError(f"reviewed preview is not the exact approved target: {actual}")
    return report


def load_live_match_schema():
    url = str(os.environ.get("SUPABASE_URL") or "").rstrip("/") + "/rest/v1/"
    key = os.environ.get("SUPABASE_SECRET_KEY")
    if not url.startswith("http") or not key:
        raise SafetyError("Supabase schema credentials are unavailable")
    response = requests.get(
        url,
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/openapi+json"},
        timeout=30,
    )
    response.raise_for_status()
    definition = (response.json().get("definitions") or {}).get("matches") or {}
    properties = definition.get("properties") or {}
    schema = {column: (properties.get(column) or {}).get("format") for column in EXPECTED_MATCH_SCHEMA}
    if schema != EXPECTED_MATCH_SCHEMA:
        raise SafetyError(f"live public.matches schema drift: {schema}")
    return schema


def validate_preflight(opportunities, matches, preview, runtime_check=True):
    state = {
        "opportunities": len(opportunities),
        "matches": len(matches),
        "duplicate_opportunity_groups": len(duplicate_groups(opportunities)),
        "duplicate_match_keys": duplicate_match_count(matches),
    }
    if state != {
        "opportunities": EXPECTED_OPPORTUNITIES,
        "matches": EXPECTED_MATCHES,
        "duplicate_opportunity_groups": 0,
        "duplicate_match_keys": 0,
    }:
        raise SafetyError(f"live preflight drift: {state}")
    runtime = check_runtime_guards() if runtime_check else None
    calculated = build_preview(preview["profiles"], opportunities, matches)
    impact = {key: calculated.get(key) for key in EXPECTED_IMPACT}
    if impact != EXPECTED_IMPACT:
        raise SafetyError(f"matching impact drift: {impact}")
    if calculated.get("missing_matches_to_create"):
        raise SafetyError("preview now proposes new match rows")
    if calculated.get("errors"):
        raise SafetyError(f"matching preview errors: {calculated['errors']}")
    changed = calculated["changed_matches"]
    unchanged = calculated["existing_matches_evaluated"] - len(changed)
    if len(changed) != EXPECTED_CHANGED or unchanged != EXPECTED_UNCHANGED:
        raise SafetyError(f"changed/unchanged drift: {len(changed)}/{unchanged}")
    return state, runtime, calculated


def exact_target_rows(matches, calculated):
    live_by_id = {row["id"]: row for row in matches}
    targets = []
    for comparison in calculated["changed_matches"]:
        live = live_by_id[comparison["match_id"]]
        targets.append({
            "id": live["id"],
            "user_id": live["user_id"],
            "opportunity_id": live["opportunity_id"],
            "old": {field: copy.deepcopy(live.get(field)) for field in DERIVED_FIELDS},
            "new": copy.deepcopy(comparison["new"]),
            "preserved": {
                key: copy.deepcopy(value) for key, value in live.items()
                if key not in DERIVED_FIELDS and key != "updated_at"
            },
        })
    return sorted(targets, key=lambda row: row["id"])


def build_backup_payload(opportunities, matches, targets, preflight):
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "MATCH_RECONCILIATION_BACKUP",
        "preflight": copy.deepcopy(preflight),
        "matches": copy.deepcopy(matches),
        "changed_matches": copy.deepcopy(targets),
        "opportunities": copy.deepcopy(opportunities),
    }


def verify_backup_payload(payload, opportunities, matches, targets):
    if payload.get("mode") != "MATCH_RECONCILIATION_BACKUP":
        raise SafetyError("backup mode is invalid")
    if canonical(payload.get("matches")) != canonical(matches) or len(payload.get("matches") or []) != 224:
        raise SafetyError("backup does not contain the exact 224 live match rows")
    if canonical(payload.get("changed_matches")) != canonical(targets):
        raise SafetyError("backup changed-row target differs from dry run")
    if canonical(payload.get("opportunities")) != canonical(opportunities):
        raise SafetyError("backup opportunity validation rows differ from live preflight")
    return True


def create_verified_backup(opportunities, matches, targets, preflight):
    BACKUP_DIRECTORY.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = BACKUP_DIRECTORY / f"helai_matches_{stamp}.json"
    payload = build_backup_payload(opportunities, matches, targets, preflight)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    reread = json.loads(path.read_text(encoding="utf-8"))
    verify_backup_payload(reread, opportunities, matches, targets)
    return path


def sql_literal(value):
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def text_array_literal(value):
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise SafetyError(f"text[] value must be a list of strings: {value!r}")
    if not value:
        return "ARRAY[]::text[]"
    return "ARRAY[" + ",".join(sql_literal(item) for item in value) + "]::text[]"


def boolean_literal(value):
    if value is None:
        return "NULL"
    return "TRUE" if bool(value) else "FALSE"


def timestamp_literal(value):
    return "NULL" if value is None else sql_literal(value) + "::timestamptz"


def generate_transaction_sql(targets):
    if len(targets) != EXPECTED_CHANGED:
        raise SafetyError("SQL target must contain exactly 72 changed rows")
    values = []
    for row in targets:
        old, new = row["old"], row["new"]
        values.append("        (" + ", ".join([
            f"{sql_literal(row['id'])}::uuid", f"{sql_literal(row['user_id'])}::uuid",
            f"{sql_literal(row['opportunity_id'])}::uuid",
            timestamp_literal(row["preserved"].get("created_at")),
            boolean_literal(row["preserved"].get("notified")),
            timestamp_literal(row["preserved"].get("notified_at")),
            "TRUE" if bool(old["eligible"]) else "FALSE", str(int(old["match_score"] or 0)),
            str(int(old["readiness"] or 0)), text_array_literal(old["reasons"] or []),
            text_array_literal(old["eligibility_gaps"] or []), text_array_literal(old["readiness_gaps"] or []),
            "TRUE" if bool(new["eligible"]) else "FALSE", str(int(new["match_score"] or 0)),
            str(int(new["readiness"] or 0)), text_array_literal(new["reasons"] or []),
            text_array_literal(new["eligibility_gaps"] or []), text_array_literal(new["readiness_gaps"] or []),
        ]) + ")")
    value_sql = ",\n".join(values)
    return f"""-- GENERATED from the reviewed 122/224 matching preview. DO NOT EDIT ROWS BY HAND.
BEGIN;
LOCK TABLE public.opportunities IN SHARE MODE;
LOCK TABLE public.matches IN SHARE ROW EXCLUSIVE MODE;

DO $$
DECLARE n integer;
BEGIN
  SELECT count(*) INTO n FROM public.opportunities;
  IF n <> 122 THEN RAISE EXCEPTION 'opportunity count drift: %', n; END IF;
  SELECT count(*) INTO n FROM public.matches;
  IF n <> 224 THEN RAISE EXCEPTION 'match count drift: %', n; END IF;
  SELECT count(*) INTO n FROM (SELECT user_id, opportunity_id FROM public.matches GROUP BY 1,2 HAVING count(*) > 1) d;
  IF n <> 0 THEN RAISE EXCEPTION 'duplicate match keys: %', n; END IF;
END $$;

CREATE TEMP TABLE _helai_match_target (
  id uuid PRIMARY KEY, user_id uuid NOT NULL, opportunity_id uuid NOT NULL,
  old_created_at timestamptz, old_notified boolean, old_notified_at timestamptz,
  old_eligible boolean NOT NULL, old_score integer NOT NULL, old_readiness integer NOT NULL,
  old_reasons text[] NOT NULL, old_eligibility_gaps text[] NOT NULL, old_readiness_gaps text[] NOT NULL,
  new_eligible boolean NOT NULL, new_score integer NOT NULL, new_readiness integer NOT NULL,
  new_reasons text[] NOT NULL, new_eligibility_gaps text[] NOT NULL, new_readiness_gaps text[] NOT NULL
) ON COMMIT DROP;

INSERT INTO _helai_match_target VALUES
{value_sql};

DO $$
DECLARE n integer;
BEGIN
  SELECT count(*) INTO n FROM _helai_match_target;
  IF n <> 72 THEN RAISE EXCEPTION 'target row count drift: %', n; END IF;
  SELECT count(*) INTO n FROM _helai_match_target WHERE old_eligible AND NOT new_eligible;
  IF n <> 44 THEN RAISE EXCEPTION 'True-to-False target drift: %', n; END IF;
  SELECT count(*) INTO n FROM _helai_match_target WHERE NOT old_eligible AND new_eligible;
  IF n <> 0 THEN RAISE EXCEPTION 'False-to-True target is forbidden: %', n; END IF;
  SELECT count(*) INTO n FROM _helai_match_target t JOIN public.matches m USING (id)
   WHERE m.user_id=t.user_id AND m.opportunity_id=t.opportunity_id
     AND m.created_at IS NOT DISTINCT FROM t.old_created_at
     AND m.notified IS NOT DISTINCT FROM t.old_notified
     AND m.notified_at IS NOT DISTINCT FROM t.old_notified_at
     AND m.eligible IS NOT DISTINCT FROM t.old_eligible
     AND m.match_score IS NOT DISTINCT FROM t.old_score
     AND m.readiness IS NOT DISTINCT FROM t.old_readiness
     AND m.reasons IS NOT DISTINCT FROM t.old_reasons
     AND m.eligibility_gaps IS NOT DISTINCT FROM t.old_eligibility_gaps
     AND m.readiness_gaps IS NOT DISTINCT FROM t.old_readiness_gaps;
  IF n <> 72 THEN RAISE EXCEPTION 'live old-value/identity drift: only % exact rows', n; END IF;
END $$;

WITH updated AS (
  UPDATE public.matches m SET
    eligible=t.new_eligible, match_score=t.new_score, readiness=t.new_readiness,
    reasons=t.new_reasons, eligibility_gaps=t.new_eligibility_gaps,
    readiness_gaps=t.new_readiness_gaps
  FROM _helai_match_target t WHERE m.id=t.id
  RETURNING m.id
)
SELECT CASE WHEN count(*)=72 THEN count(*) ELSE 1/(count(*)-count(*)) END AS updated_rows FROM updated;

DO $$
DECLARE n integer;
BEGIN
  SELECT count(*) INTO n FROM _helai_match_target t JOIN public.matches m USING (id)
   WHERE m.user_id=t.user_id AND m.opportunity_id=t.opportunity_id
     AND m.created_at IS NOT DISTINCT FROM t.old_created_at
     AND m.notified IS NOT DISTINCT FROM t.old_notified
     AND m.notified_at IS NOT DISTINCT FROM t.old_notified_at
     AND m.eligible IS NOT DISTINCT FROM t.new_eligible
     AND m.match_score IS NOT DISTINCT FROM t.new_score
     AND m.readiness IS NOT DISTINCT FROM t.new_readiness
     AND m.reasons IS NOT DISTINCT FROM t.new_reasons
     AND m.eligibility_gaps IS NOT DISTINCT FROM t.new_eligibility_gaps
     AND m.readiness_gaps IS NOT DISTINCT FROM t.new_readiness_gaps;
  IF n <> 72 THEN RAISE EXCEPTION 'final-value verification failed: %', n; END IF;
  SELECT count(*) INTO n FROM public.matches;
  IF n <> 224 THEN RAISE EXCEPTION 'final match count drift: %', n; END IF;
END $$;
COMMIT;
"""


def run(mode):
    raise SafetyError(
        "ALREADY APPLIED / DO NOT EXECUTE AGAIN; use "
        "helai_match_reconciliation_verify.py for read-only verification"
    )
    # Historical implementation retained below for auditability only.
    reviewed = load_reviewed_preview()
    live_schema = load_live_match_schema()
    opportunities, matches, profiles = load_rows()
    context = {"profiles": profiles}
    preflight, runtime, calculated = validate_preflight(opportunities, matches, context)
    targets = exact_target_rows(matches, calculated)
    sql = generate_transaction_sql(targets)
    SQL_PATH.write_text(sql, encoding="utf-8")
    backup_path = None
    if mode == "backup-only":
        backup_path = create_verified_backup(opportunities, matches, targets, preflight)
    report = {
        "mode": mode, "preflight": preflight, "runtime_guard": runtime,
        "live_match_schema": live_schema,
        "reviewed_preview_mode": reviewed.get("mode"),
        "existing_matches": 224, "changed_existing_matches": len(targets),
        "unchanged_matches": 152, "new_matches": 0, "deletions": 0,
        **EXPECTED_IMPACT, "non_actionable_matches_reconciled": 54,
        "targets": targets, "sql_path": str(SQL_PATH.resolve()),
        "backup_path": str(backup_path.resolve()) if backup_path else None,
        "supabase_writes": 0,
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "targets"}, indent=2, default=str))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-only", action="store_true")
    args = parser.parse_args(argv)
    run("backup-only" if args.backup_only else "dry-run")


if __name__ == "__main__":
    try:
        main()
    except SafetyError as error:
        print(f"SAFETY STOP: {error}", file=sys.stderr)
        raise SystemExit(2)
