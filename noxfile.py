import nox


@nox.session
def tests(session):
    session.install(".")
    session.run("python", "-m", "unittest", "discover", "-s", "tests")
