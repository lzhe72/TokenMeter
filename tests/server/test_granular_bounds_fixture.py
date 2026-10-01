"""Real migrated SQLite and Argon2 checks for the D42-BOUNDS fixture."""

import json
from pathlib import Path
import sqlite3

import pytest

from scripts import granular_bounds_fixture as bounds


@pytest.mark.parametrize("variant_id,username", list(bounds.VARIANTS.items()))
def test_generate_verify_and_reset_boundary_sqlite(tmp_path: Path, variant_id: str, username: str):
    private = tmp_path.resolve() / variant_id[-1] / "private"
    evidence = tmp_path.resolve() / variant_id[-1] / "evidence"
    run_id = "bounds-" + variant_id[-1].lower()
    database, fixture, sql = bounds.generate(private, evidence, run_id, variant_id)
    assert sql.is_file() and fixture.is_dir() and database.is_file()
    assert sql.stat().st_mode & 0o777 == 0o600
    assert database.stat().st_mode & 0o777 == 0o600
    text = sql.read_text()
    assert "$argon2" in text
    assert bounds.BOUNDARY_PASSWORD not in text
    assert "TEST-ONLY-alice-42!" not in text
    assert bounds.verify(database, run_id, variant_id)["account_count"] == 5
    expected = json.loads((fixture / "expected.json").read_text())
    assert expected["boundary"]["username"] == username
    assert expected["boundary"]["username_length"] == len(username)
    assert len(expected["users"]) == 5
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        rows = connection.execute("SELECT username,password_hash FROM users ORDER BY username").fetchall()
        assert len(rows) == 5
        assert all(value.startswith("$argon2") for _, value in rows)
        assert connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
    bounds.reset(private, run_id, variant_id)
    assert not database.exists() and not (private / bounds.OWNER_FILE).exists()
    assert sql.is_file()  # Preserve source evidence after owned DB reset.


def test_random_salt_and_wrong_owner_refusal(tmp_path: Path):
    hashes = []
    for number in (1, 2):
        root = tmp_path.resolve() / str(number)
        database, _, _ = bounds.generate(root / "private", root / "evidence",
                                          f"bounds-{number}", "TC-TM001-LOGIN-19#A")
        with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
            hashes.append(connection.execute("SELECT password_hash FROM users WHERE username='a_1'").fetchone()[0])
        with pytest.raises(ValueError):
            bounds.reset(root / "private", "wrong-owner", "TC-TM001-LOGIN-19#A")
        assert database.is_file()
        bounds.reset(root / "private", f"bounds-{number}", "TC-TM001-LOGIN-19#A")
    assert hashes[0] != hashes[1]
