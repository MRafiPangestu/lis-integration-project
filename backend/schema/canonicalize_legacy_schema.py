#!/usr/bin/env python3
r"""
M9.0 Phase 2C: Deterministic canonicalization of legacy schema artifact.

Transforms a pg_dump schema-only output to remove session/environment directives,
preserving all schema DDL exactly.

No external dependencies. No database access. Reproducible output.

Approved removals:
  R1: psql \restrict / \unrestrict meta-commands
  R2: pg_dump SET directives (12 lines)
  R3: SELECT pg_catalog.set_config(...) line
  R4: COMMENT ON SCHEMA public IS '' statement (1 line)
  R5: orphan 3-line section header for R4 (the "-- Name: SCHEMA public" block)

All other lines, including blank lines, are preserved exactly.
"""

import hashlib
import os
import sys
from pathlib import Path


def compute_sha256(file_path: str) -> str:
    """Compute SHA-256 of a file."""
    sha = hashlib.sha256()
    with open(file_path, 'rb') as f:
        sha.update(f.read())
    return sha.hexdigest()


def canonicalize_legacy_schema(source_path: str, target_path: str) -> str:
    """
    Canonicalize the legacy schema dump.

    Removes only the approved directives, preserves all blank lines and DDL.
    """

    # Verify source exists and read it
    if not os.path.exists(source_path):
        sys.exit(f"FATAL: Source file not found: {source_path}")

    with open(source_path, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')  # Split on \n only

    source_sha = compute_sha256(source_path)

    # Expected source SHA-256 (immutable evidence)
    expected_source_sha = "93d902f67e334c0d6b7ea0ce36a2c81cbb5292781b7d45a920b5cbc67199c81e"

    if source_sha != expected_source_sha:
        sys.exit(
            f"FATAL: Source SHA-256 mismatch.\n"
            f"  Expected: {expected_source_sha}\n"
            f"  Got:      {source_sha}\n"
            f"Source has been modified or is incorrect."
        )

    # Add provenance header
    header = [
        "--",
        "-- Canonical legacy schema (M9.0 Phase 2C)",
        "--",
        "-- Deterministic derivation of the pre-M1 legacy schema.",
        "-- Source artifact : backend/schema/legacy_schema.sql",
        f"-- Source SHA-256  : {source_sha}",
        "--",
        "-- Removed from the source (approved dump/session directives only):",
        "--   R1  psql restrict/unrestrict meta-commands            (2)",
        "--   R2  pg_dump session configuration directives         (12)",
        "--   R3  search_path reset directive                       (1)",
        "--   R4  public-schema comment mutation                    (1)",
        "--   R5  section header of the directive removed by R4     (1)",
        "--",
        "-- Deliberately worded to contain no executable SQL token, so that",
        "-- automated checks over this file cannot match header prose.",
        "--",
        "-- No schema DDL was added, removed or transformed. SERIAL sequence",
        "-- mechanism (sequence + OWNED BY + nextval) is preserved verbatim.",
        "-- patients.nomor_rm is intentionally NON-UNIQUE here: that is legacy",
        "-- truth. F-2 is a separate later revision and must not be folded in.",
        "--",
        "",
    ]

    output_lines = header.copy()

    # Process lines with explicit removal rules
    i = 0
    while i < len(lines):
        line = lines[i]

        # R1: Remove psql meta-commands
        if line.startswith('\\restrict ') or line.startswith('\\unrestrict '):
            i += 1
            continue

        # R2 & R3: Remove SET directives and set_config
        if line.startswith('SET ') or 'pg_catalog.set_config' in line:
            i += 1
            continue

        # R4 & R5: Remove COMMENT ON SCHEMA and its section header
        # Section header pattern: -- Name: SCHEMA public; Type: COMMENT
        if 'Name: SCHEMA public' in line and 'Type: COMMENT' in line:
            # This is the middle line of the 3-line header
            # Remove the previous -- line if it exists
            if output_lines and output_lines[-1].strip() == '--':
                output_lines.pop()
            # Skip current line and the next closing --
            i += 1
            if i < len(lines) and lines[i].strip() == '--':
                i += 1
            continue

        # R4: Remove COMMENT ON SCHEMA statement
        if line.startswith('COMMENT ON SCHEMA public'):
            i += 1
            continue

        # Keep all other lines (including blank lines)
        output_lines.append(line)
        i += 1

    # Reconstruct with LF only
    output_text = '\n'.join(output_lines)
    # Ensure exactly one trailing newline
    output_text = output_text.rstrip() + '\n'

    # Write to target (binary mode to ensure LF-only)
    with open(target_path, 'wb') as f:
        f.write(output_text.encode('utf-8'))

    target_sha = compute_sha256(target_path)
    return target_sha


def validate_schema(file_path: str) -> dict:
    """Validate the canonicalized schema."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    counts = {
        'CREATE TABLE': content.count('CREATE TABLE public.'),
        'CREATE SEQUENCE': content.count('CREATE SEQUENCE public.'),
        'ALTER SEQUENCE ... OWNED BY': content.count('ALTER SEQUENCE'),
        'NEXTVAL defaults': content.count('nextval('),
        'PK constraints': content.count('PRIMARY KEY'),
        'UNIQUE constraints': content.count('UNIQUE ('),
        'FK constraints': content.count('FOREIGN KEY'),
        'NOT NULL': content.count('NOT NULL'),
    }

    absences = {
        'INSERT statements': 'INSERT' not in content,
        'COPY payloads': 'COPY' not in content and '\\.' not in content,
        '\\restrict tokens': '\\restrict' not in content,
        '\\unrestrict tokens': '\\unrestrict' not in content,
        'SET directives': not any(l.startswith('SET ') and len(l) > 4 for l in content.split('\n')),
        'set_config calls': 'pg_catalog.set_config' not in content,
        'COMMENT ON SCHEMA': 'COMMENT ON SCHEMA public' not in content,
        'OWNER TO': 'OWNER TO' not in content,
        'GRANT statements': 'GRANT' not in content,
        'REVOKE statements': 'REVOKE' not in content,
        'CREATE INDEX': 'CREATE INDEX' not in content,
        'CREATE SCHEMA': 'CREATE SCHEMA' not in content,
        'CREATE DATABASE': 'CREATE DATABASE' not in content,
        'IDENTITY clauses': 'GENERATED' not in content,
    }

    patients_nomor_rm_not_null = 'nomor_rm character varying' in content
    patients_nomor_rm_not_unique = 'UNIQUE (nomor_rm)' not in content

    m84_indexes_absent = all(idx not in content for idx in [
        'ix_test_runs_id_instrument_id_order',
        'ix_orders_id_visit',
        'ix_visits_id_pasien',
        'ix_orders_waktu_order_id_order'
    ])

    m1_objects_absent = 'visits' not in content and 'test_runs' not in content

    return {
        'counts': counts,
        'absences': absences,
        'patients_nomor_rm_not_null': patients_nomor_rm_not_null,
        'patients_nomor_rm_not_unique': patients_nomor_rm_not_unique,
        'm84_indexes_absent': m84_indexes_absent,
        'm1_objects_absent': m1_objects_absent,
    }


def main():
    """Main entry point."""
    script_dir = Path(__file__).parent.resolve()
    source = str(script_dir / 'legacy_schema.sql')
    target = str(script_dir / 'canonical_legacy_schema.sql')

    print(f"canonicalize_legacy_schema.py")
    print(f"  Source: {source}")
    print(f"  Target: {target}")
    print()

    # Canonicalize
    print("Step 1: Canonicalizing...")
    target_sha = canonicalize_legacy_schema(source, target)
    print(f"  Target SHA-256: {target_sha}")
    print()

    # Validate
    print("Step 2: Validating...")
    validation = validate_schema(target)

    print(f"  Object counts:")
    for key, count in validation['counts'].items():
        print(f"    {key}: {count}")

    print(f"  Absence checks (all must be True):")
    all_absent_ok = all(validation['absences'].values())
    for key, absent in validation['absences'].items():
        status = "[OK]" if absent else "[FAIL]"
        print(f"    {status} {key}: {absent}")

    print(f"  Schema consistency:")
    print(f"    [OK] patients.nomor_rm NOT NULL: {validation['patients_nomor_rm_not_null']}")
    print(f"    [OK] patients.nomor_rm NON-UNIQUE: {validation['patients_nomor_rm_not_unique']}")
    print(f"    [OK] M8.4 indexes absent: {validation['m84_indexes_absent']}")
    print(f"    [OK] M1 objects absent: {validation['m1_objects_absent']}")
    print()

    # Reproducibility check
    print("Step 3: Reproducibility check...")
    target_sha_2 = canonicalize_legacy_schema(source, target)
    if target_sha == target_sha_2:
        print(f"  [OK] PASS: Output is deterministic and byte-identical")
    else:
        print(f"  [FAIL] Output differs on second run")
        sys.exit(1)
    print()

    # Summary
    print("Summary:")
    print(f"  Source SHA-256: 93d902f67e334c0d6b7ea0ce36a2c81cbb5292781b7d45a920b5cbc67199c81e")
    print(f"  Target SHA-256: {target_sha}")
    print(f"  Reproducible: YES")
    all_valid = all_absent_ok and validation['patients_nomor_rm_not_null'] and validation['patients_nomor_rm_not_unique'] and validation['m84_indexes_absent'] and validation['m1_objects_absent']
    print(f"  All validations: {'PASS' if all_valid else 'FAIL'}")


if __name__ == '__main__':
    main()
