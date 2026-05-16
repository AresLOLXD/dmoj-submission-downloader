import io
import zipfile
import pytest
from app.zip_builder import sanitize_name, build_submission_filename, stream_contest_zip

def test_sanitize_name_replaces_special_chars():
    assert sanitize_name("user@123") == "user_123"
    assert sanitize_name("José García") == "Jos__Garc_a"
    assert sanitize_name("normal_user-1") == "normal_user-1"

def test_sanitize_name_truncates_to_64_chars():
    long = "a" * 100
    result = sanitize_name(long)
    assert len(result) == 64

def test_sanitize_name_does_not_truncate_short_names():
    assert sanitize_name("alice") == "alice"

def test_build_submission_filename():
    name = build_submission_filename(
        index=1,
        username="user1",
        date_str="2025-05-15",
        time_str="14-30-22",
        verdict="AC",
        ext="py",
    )
    assert name == "1_user1_2025-05-15_14-30-22_AC.py"

def test_stream_contest_zip_produces_valid_zip():
    submissions = [
        {
            "sanitized_username": "user1",
            "problem": "prob_a",
            "index": 1,
            "date_str": "2025-05-15",
            "time_str": "14-30-22",
            "verdict": "AC",
            "ext": "py",
            "source": b"print('hello')",
        }
    ]
    chunks = list(stream_contest_zip(iter(submissions)))
    buffer = io.BytesIO(b"".join(chunks))
    with zipfile.ZipFile(buffer) as zf:
        names = zf.namelist()
        assert "user1/prob_a/1_user1_2025-05-15_14-30-22_AC.py" in names
        assert zf.read("user1/prob_a/1_user1_2025-05-15_14-30-22_AC.py") == b"print('hello')"

def test_stream_contest_zip_multiple_users_and_problems():
    submissions = [
        {"sanitized_username": "alice", "problem": "a", "index": 1, "date_str": "2025-01-01",
         "time_str": "10-00-00", "verdict": "AC", "ext": "py", "source": b"code_a"},
        {"sanitized_username": "bob", "problem": "b", "index": 1, "date_str": "2025-01-01",
         "time_str": "10-05-00", "verdict": "WA", "ext": "cpp", "source": b"code_b"},
    ]
    chunks = list(stream_contest_zip(iter(submissions)))
    buffer = io.BytesIO(b"".join(chunks))
    with zipfile.ZipFile(buffer) as zf:
        names = zf.namelist()
    assert "alice/a/1_alice_2025-01-01_10-00-00_AC.py" in names
    assert "bob/b/1_bob_2025-01-01_10-05-00_WA.cpp" in names
