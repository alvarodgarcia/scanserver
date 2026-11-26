import sys

from ocrmypdf import hookimpl


def clean(value):
    return str(value or "").replace("|", "/").replace("\n", " ")


class ScanServerProgress:

    def __init__(
        self,
        *,
        total=None,
        desc=None,
        unit=None,
        disable=False,
        **kwargs
    ):
        self.total = float(total or 0)
        self.current = 0.0
        self.desc = clean(desc)
        self.unit = clean(unit)
        self.disable = disable

        self.emit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):

        if exc_type is None and self.total:
            self.current = self.total
            self.emit()

        return False

    def update(self, n=1, *, completed=None):

        if completed is not None:
            self.current = float(completed)
        else:
            self.current += float(n)

        self.emit()

    def emit(self):

        if self.disable:
            return

        if self.total > 0:
            percent = min(
                100.0,
                max(
                    0.0,
                    self.current / self.total * 100.0
                )
            )
        else:
            percent = 0.0

        print(
            "OCRPROGRESS|"
            f"{percent:.1f}|"
            f"{self.desc}|"
            f"{self.current:.0f}|"
            f"{self.total:.0f}|"
            f"{self.unit}",
            file=sys.stderr,
            flush=True,
        )


@hookimpl
def get_progressbar_class():
    return ScanServerProgress
