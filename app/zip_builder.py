import re
import zipstream
from typing import Any, Iterator


def sanitize_name(name: str) -> str:
    """Replace any character that is not alphanumeric, underscore, or hyphen with underscore.

    Args:
        name: Raw name string to sanitize.

    Returns:
        Sanitized string truncated to 64 characters.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)
    return sanitized[:64]


def build_submission_filename(
    index: int,
    username: str,
    date_str: str,
    time_str: str,
    verdict: str,
    ext: str,
) -> str:
    """Build a deterministic filename for a single submission.

    Args:
        index: Submission order index within the contest/problem.
        username: Already-sanitized username.
        date_str: Date portion of the submission timestamp (e.g. "2025-05-15").
        time_str: Time portion of the submission timestamp (e.g. "14-30-22").
        verdict: Submission verdict string (e.g. "AC", "WA").
        ext: File extension without the leading dot (e.g. "py", "cpp").

    Returns:
        Filename string like "1_user1_2025-05-15_14-30-22_AC.py".
    """
    return f"{index}_{username}_{date_str}_{time_str}_{verdict}.{ext}"


def stream_contest_zip(submissions: Iterator[dict[str, Any]]) -> Iterator[bytes]:
    """Yield ZIP file chunks for a stream of submission dicts.

    Each submission dict must contain:
        sanitized_username (str), problem (str), index (int),
        date_str (str), time_str (str), verdict (str), ext (str),
        source (bytes | str).

    Args:
        submissions: Iterator of submission metadata dicts.

    Yields:
        Raw bytes chunks that together form a valid ZIP archive.
    """
    zf = zipstream.ZipFile(mode="w", compression=zipstream.ZIP_DEFLATED)
    for sub in submissions:
        filename = build_submission_filename(
            index=sub["index"],
            username=sub["sanitized_username"],
            date_str=sub["date_str"],
            time_str=sub["time_str"],
            verdict=sub["verdict"],
            ext=sub["ext"],
        )
        arcname = f"{sub['sanitized_username']}/{sanitize_name(sub['problem'])}/{filename}"
        source = sub["source"]
        zf.writestr(arcname, source if isinstance(source, bytes) else source.encode())
    yield from zf
