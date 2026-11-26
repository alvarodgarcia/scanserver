"""Pruebas aisladas de las nuevas defensas: no abren la DB ni el escáner."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
import threading
import time
import unittest
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "web/app.py").read_text(encoding="utf-8")


def isolated_functions(*names, extra=None):
    """Carga las funciones reales por AST sin importar la aplicación."""
    tree = ast.parse(SOURCE)
    funcs = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in names
    ]
    if len(funcs) != len(names):
        raise AssertionError("Faltan funciones solicitadas para pruebas")
    for node in funcs:
        node.decorator_list = []
    scope = {
        "time": time,
        "threading": threading,
        "HTTPException": HTTPException,
        "Request": Request,
        "JSONResponse": JSONResponse,
        "urlsplit": urlsplit,
    }
    scope.update(extra or {})
    code = compile(
        ast.fix_missing_locations(ast.Module(body=funcs, type_ignores=[])),
        str(ROOT / "web/app.py"),
        "exec",
    )
    exec(code, scope)
    return scope


class SameOriginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guard = staticmethod(isolated_functions("same_origin_writes")["same_origin_writes"])

    def req(self, method="POST", origin="http://scan.local:8080",
            host="scan.local:8080", fetch_site="same-origin"):
        headers = {"host": host, "sec-fetch-site": fetch_site}
        if origin is not None:
            headers["origin"] = origin
        return SimpleNamespace(
            method=method,
            url=SimpleNamespace(scheme="http", path="/api/admin/users"),
            headers=headers,
        )

    def dispatch(self, request):
        async def downstream(_):
            return "accepted"
        return asyncio.run(self.guard(request, downstream))

    def test_same_origin_allowed(self):
        self.assertEqual(self.dispatch(self.req()), "accepted")

    def test_cross_site_origin_rejected(self):
        self.assertEqual(
            self.dispatch(self.req(origin="http://other.local:8080")).status_code,
            403,
        )

    def test_missing_origin_rejected(self):
        self.assertEqual(self.dispatch(self.req(origin=None)).status_code, 403)

    def test_fetch_metadata_rejected(self):
        self.assertEqual(
            self.dispatch(self.req(fetch_site="cross-site")).status_code,
            403,
        )

    def test_get_does_not_require_origin(self):
        self.assertEqual(self.dispatch(self.req(method="GET", origin=None)), "accepted")

    def test_referer_fallback(self):
        req = self.req(origin=None)
        req.headers["referer"] = "http://scan.local:8080/"
        self.assertEqual(self.dispatch(req), "accepted")


class LoginRateTests(unittest.TestCase):
    def setUp(self):
        self.scope = isolated_functions(
            "_login_ip", "check_login_rate", "record_login_failure",
            "clear_login_failures",
            extra={
                "LOGIN_WINDOW_SECONDS": 300,
                "LOGIN_MAX_FAILURES": 8,
                "LOGIN_BLOCK_SECONDS": 300,
                "_login_attempts": {},
                "_login_lock": threading.Lock(),
            }
        )
        self.req = SimpleNamespace(client=SimpleNamespace(host="198.51.100.9"))

    def test_eight_failures_block_next_attempt(self):
        for _ in range(8):
            self.scope["record_login_failure"](self.req)
        with self.assertRaises(HTTPException) as ctx:
            self.scope["check_login_rate"](self.req)
        self.assertEqual(ctx.exception.status_code, 429)

    def test_success_resets_failures(self):
        for _ in range(7):
            self.scope["record_login_failure"](self.req)
        self.scope["clear_login_failures"](self.req)
        self.scope["check_login_rate"](self.req)

    def test_other_ip_not_blocked(self):
        for _ in range(8):
            self.scope["record_login_failure"](self.req)
        other = SimpleNamespace(client=SimpleNamespace(host="198.51.100.10"))
        self.scope["check_login_rate"](other)


class StructuralRegressionTests(unittest.TestCase):
    def test_atomic_start_reserves_under_lock(self):
        tree = ast.parse(SOURCE)
        func = next(
            n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "start_session"
        )
        guards = [
            n for n in ast.walk(func)
            if isinstance(n, ast.With)
            and any(
                isinstance(item.context_expr, ast.Name)
                and item.context_expr.id == "lock"
                for item in n.items
            )
        ]
        self.assertTrue(guards, "Debe existir una sección con lock")
        with_guard = guards[0]
        assignments = [
            target.id for n in ast.walk(with_guard)
            if isinstance(n, ast.Assign)
            for target in n.targets if isinstance(target, ast.Name)
        ]
        self.assertIn("current_session", assignments)
        self.assertTrue(any(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "status"
            and n.func.attr == "update"
            for n in ast.walk(with_guard)
        ))

    def test_session_invalidation_is_migrated(self):
        self.assertIn("ALTER TABLE users ADD COLUMN session_version", SOURCE)
        self.assertGreaterEqual(
            SOURCE.count("session_version = session_version + 1"), 2
        )
        self.assertIn('request.session["session_version"]', SOURCE)

    def test_duplex_start_is_atomic(self):
        self.assertIn("duplex: bool = False", SOURCE)
        js = (ROOT / "web/static/app.js").read_text(encoding="utf-8")
        self.assertIn('getElementById("duplex-enabled")?.checked', js)
        self.assertNotIn("window.fetch =", js)
        self.assertNotIn('"?reverse="', js)


if __name__ == "__main__":
    unittest.main()
