import subprocess


def lint():
    subprocess.run(["ruff", "check", "."], check=False)


def fmt():
    subprocess.run(["ruff", "format", "."], check=False)


def check():
    subprocess.run(["mypy", "src/"], check=False)


def test():
    subprocess.run(["pytest", "tests/", "-v"], check=False)


def migrate():
    subprocess.run(["alembic", "upgrade", "head"], check=False)
