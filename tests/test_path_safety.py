"""Run path validators in isolation; never import the live application or touch user data."""
import ast
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
import unittest

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]


def load_path_helpers():
    source = (ROOT / "web/app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    accepted = {"relative_path", "safe_user_path"}
    funcs = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in accepted]
    if len(funcs) != 2:
        raise RuntimeError("Expected path validation functions not found")
    module = ast.Module(body=funcs, type_ignores=[])
    scope = {"Path": Path, "PurePosixPath": PurePosixPath, "HTTPException": HTTPException}
    exec(compile(ast.fix_missing_locations(module), str(ROOT / "web/app.py"), "exec"), scope)
    return scope["safe_user_path"]


class PathIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validate = staticmethod(load_path_helpers())

    def test_inside_root_allowed(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "user"
            (root / "docs").mkdir(parents=True)
            file = root / "docs" / "demo.pdf"
            file.write_bytes(b"%PDF-1.4\n")
            self.assertEqual(self.validate(root, "docs/demo.pdf", must_exist=True), file.resolve())

    def test_parent_traversal_rejected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "user"
            root.mkdir()
            with self.assertRaises(HTTPException):
                self.validate(root, "../other/secret.pdf")

    def test_absolute_path_rejected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "user"
            root.mkdir()
            with self.assertRaises(HTTPException):
                self.validate(root, "/etc/passwd")

    def test_symlink_outside_root_rejected(self):
        with TemporaryDirectory() as temp:
            temp = Path(temp)
            root = temp / "user"
            root.mkdir()
            outside = temp / "private.pdf"
            outside.write_bytes(b"%PDF-1.4\n")
            (root / "linked.pdf").symlink_to(outside)
            with self.assertRaises(HTTPException):
                self.validate(root, "linked.pdf", must_exist=True)


if __name__ == "__main__":
    unittest.main()
