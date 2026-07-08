#!/usr/bin/env python3
"""
Залить папку .tdl от DiGR в v2-service как проект.

`python tools/digr_bridge/push_to_service.py --email you@ex.com --password secret`
`python tools/digr_bridge/push_to_service.py ... --project "дискретка" --build`
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_DEFAULT_IN = _REPO / "src" / "digr" / "ontology-pipeline" / "data" / "tdl"


class Client:
    """Тонкий cookie-клиент к v2-service поверх urllib."""

    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar)
        )

    def _request(
        self, method: str, path: str, *, json_body=None, form=None
    ) -> tuple[int, bytes]:
        url = self.base + path
        headers = {}
        data: bytes | None = None
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif form is not None:
            data = urllib.parse.urlencode(form).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self._opener.open(req, timeout=60) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def register(self, email: str, password: str) -> None:
        status, body = self._request(
            "POST", "/auth/register", json_body={"email": email, "password": password}
        )
        if status in (200, 201):
            print(f"  регистрация: создан {email}")
        elif status == 400:  # уже существует — норма
            print(f"  регистрация: {email} уже есть, пропускаю")
        else:
            raise SystemExit(f"регистрация не удалась ({status}): {body[:200]!r}")

    def login(self, email: str, password: str) -> None:
        status, body = self._request(
            "POST",
            "/auth/cookie/login",
            form={"username": email, "password": password},
        )
        if status not in (200, 204):
            raise SystemExit(f"логин не удался ({status}): {body[:200]!r}")
        print("  логин: ок")

    def create_project(self, name: str) -> str:
        status, body = self._request("POST", "/projects", json_body={"name": name})
        if status not in (200, 201):
            raise SystemExit(f"проект не создан ({status}): {body[:200]!r}")
        pid = json.loads(body)["id"]
        print(f"  проект: {name} -> {pid}")
        return pid

    def add_file(self, pid: str, name: str, content: str) -> bool:
        status, body = self._request(
            "POST",
            f"/projects/{pid}/files",
            json_body={"name": name, "content": content},
        )
        if status in (200, 201):
            return True
        print(f"    ! {name}: файл не залит ({status}): {body[:150]!r}")
        return False

    def build(self, pid: str, entry: str) -> str:
        status, body = self._request(
            "POST", f"/projects/{pid}/build", json_body={"entry": entry}
        )
        if status != 200:
            return f"HTTP {status}"
        data = json.loads(body)
        return "ok" if not data.get("error") else f"error: {data['error'][:120]}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Импорт DiGR .tdl в v2-service")
    ap.add_argument("--base", default="http://localhost:8000", help="URL сервиса")
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--in", dest="in_dir", default=str(_DEFAULT_IN))
    ap.add_argument("--project", default="DiGR импорт")
    ap.add_argument(
        "--build", action="store_true", help="собрать каждый файл после заливки"
    )
    args = ap.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    in_dir = Path(args.in_dir)
    files = sorted(in_dir.glob("*.tdl"))
    if not files:
        print(f"В {in_dir} нет .tdl", file=sys.stderr)
        return 2

    cli = Client(args.base)
    print(f"Сервис: {args.base}")
    cli.register(args.email, args.password)
    cli.login(args.email, args.password)
    pid = cli.create_project(args.project)

    uploaded = 0
    for path in files:
        if cli.add_file(pid, path.name, path.read_text(encoding="utf-8")):
            uploaded += 1
    print(f"  файлов залито: {uploaded}/{len(files)}")

    if args.build:
        print("Сборка:")
        for path in files:
            print(f"  {path.name}: {cli.build(pid, path.name)}")

    print("Готово.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
