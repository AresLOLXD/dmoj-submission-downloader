import httpx
from typing import Any

LANGUAGE_EXTENSIONS: dict[str, str] = {
    "PY3": "py", "PY2": "py", "CPP17": "cpp", "CPP14": "cpp", "CPP11": "cpp",
    "CPP20": "cpp", "C": "c", "JAVA8": "java", "JAVA11": "java", "JAVA17": "java",
    "KOTLIN": "kt", "RUBY": "rb", "RUST": "rs", "GO": "go", "HS": "hs",
    "JS": "js", "CS": "cs", "PAS": "pas", "D": "d", "SWIFT": "swift",
    "PYPY3": "py", "SCALA": "scala", "LUA": "lua", "PHP": "php",
    "PERL": "pl", "BASH": "sh",
}

class ContestNotFoundError(Exception):
    pass

class DMOJClient:
    def __init__(self, base_url: str, token: str) -> None:
        self._base = base_url
        self._headers = {"Authorization": f"Bearer {token}"}
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "DMOJClient":
        self._client = httpx.AsyncClient(headers=self._headers, timeout=30)
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("DMOJClient must be used as an async context manager")
        return self._client

    async def get_contest_participants(self, slug: str) -> list[str]:
        client = self._get_client()
        resp = await client.get(f"{self._base}/api/v2/contest/{slug}")
        if resp.status_code == 404:
            raise ContestNotFoundError(slug)
        resp.raise_for_status()
        rankings = resp.json()["data"]["object"]["rankings"]
        return [r["user"] for r in rankings]

    async def get_contest_submissions(self, slug: str) -> list[dict[str, Any]]:
        client = self._get_client()
        results: list[dict[str, Any]] = []
        params: dict[str, Any] = {"contest": slug, "page_size": 100}
        while True:
            resp = await client.get(f"{self._base}/api/v2/submissions", params=params)
            resp.raise_for_status()
            data = resp.json()["data"]
            results.extend(data["objects"])
            if not data.get("has_more"):
                break
            params["after"] = data["next_page_id"]
        return results

    async def get_submission_source(self, submission_id: int) -> str:
        client = self._get_client()
        resp = await client.get(f"{self._base}/api/v2/submission/{submission_id}")
        resp.raise_for_status()
        return resp.json()["data"]["object"]["source"]

    @staticmethod
    def language_to_ext(language: str) -> str:
        return LANGUAGE_EXTENSIONS.get(language, "txt")
