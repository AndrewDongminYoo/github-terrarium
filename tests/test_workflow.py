"""Standard-library text checks for the daily generation workflow.

Each check reads the workflow source as text.
`WorkflowTests.test_every_check_fails_on_a_mutated_copy` breaks a copy once per
check and requires that check to fail, so a pass is not a read of a pattern
that can never miss.
"""

import os
import re
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/generate.yml"
REPOSITORY = "AndrewDongminYoo/github-terrarium"
DEFAULT_BRANCH = (
    "github.ref == format('refs/heads/{0}', github.event.repository.default_branch)"
)
BOOTSTRAP_ENV = (
    "BOOTSTRAP: ${{ github.event_name == 'workflow_dispatch' && inputs.bootstrap }}"
)


def block(text, key, indent=0):
    """Return the lines under the first `key:` line at `indent` spaces."""
    lines = text.splitlines()
    head = " " * indent + key + ":"
    for index, line in enumerate(lines):
        if line == head or line.startswith(head + " "):
            body = []
            for child in lines[index + 1 :]:
                if child.strip() and len(child) - len(child.lstrip()) <= indent:
                    break
                if child.strip():
                    body.append(child)
            return body
    return []


def keys(lines, indent):
    pattern = re.compile(rf"^ {{{indent}}}([A-Za-z_-]+):")
    return [m.group(1) for m in map(pattern.match, lines) if m]


def run_script(text):
    """Return the `run:` script of the generation step, dedented."""
    lines = text.splitlines()
    start = lines.index("        run: |") + 1
    return "\n".join(line[10:] for line in lines[start:] if line.startswith(" " * 10))


def check_triggers(text):
    events = block(text, "on")
    assert keys(events, 2) == ["schedule", "workflow_dispatch"], keys(events, 2)
    for name in ("push", "pull_request", "pull_request_target", "branches"):
        assert not re.search(rf"^\s*{name}:", text, re.M), name


def check_cron(text):
    assert re.findall(r"cron:\s*(.+)", text) == ["'23 0 * * *'"]


def check_dispatch_input(text):
    dispatch = block(text, "workflow_dispatch", 2)
    assert keys(dispatch, 6) == ["bootstrap"], keys(dispatch, 6)
    options = "\n".join(dispatch)
    assert "        type: boolean" in options
    assert "        default: false" in options


def check_top_permissions(text):
    assert "\npermissions: {}\n" in text
    assert re.findall(r"^\s*contents: (\w+)", text, re.M) == ["write"]


def check_job_permissions(text):
    jobs = block(text, "jobs")
    assert keys(jobs, 2) == ["generate"], keys(jobs, 2)
    job = block(text, "generate", 2)
    assert keys(block("\n".join(job), "permissions", 4), 6) == ["contents"]
    assert "    permissions:\n      contents: write" in "\n".join(job)


def job_condition(text):
    return [line for line in block(text, "generate", 2) if line.startswith("    if:")]


def check_branch_guard(text):
    (line,) = job_condition(text)
    assert f"(github.event_name == 'schedule' || {DEFAULT_BRANCH})" in line, (
        "default-branch guard"
    )


def check_repository_guard(text):
    (line,) = job_condition(text)
    assert line.startswith(f"    if: github.repository == '{REPOSITORY}' && ")
    assert not re.search(r"^\s+if:", text.split("    steps:")[1], re.M)


def check_checkout_credentials(text):
    steps = text.split("- uses: actions/checkout@")[1:]
    assert steps, "checkout"
    for step in steps:
        assert step.split("\n      - ")[0].count("persist-credentials: false") == 1


def check_pins(text):
    uses = re.findall(r"uses:\s*(\S+)", text)
    assert uses, "uses"
    for action in uses:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", action), action


def check_concurrency(text):
    assert text.count("concurrency:") == 1
    job = "\n".join(block(text, "generate", 2))
    assert block(job, "concurrency", 4) == [
        "      group: terrarium-output",
        "      cancel-in-progress: false",
    ]


def check_timeout(text):
    assert re.findall(r"timeout-minutes:\s*(\S+)", text) == ["15"]


def check_bootstrap_reachability(text):
    assert text.count("--bootstrap") == 1
    assert text.count("inputs.bootstrap") == 1
    assert f"          {BOOTSTRAP_ENV}\n" in text
    assert 'if [ "$BOOTSTRAP" = "true" ]; then set -- --bootstrap; fi' in text


def check_token_and_expressions(text):
    assert "secrets." not in text
    assert "github.token" in text
    expressions = [line.strip() for line in text.splitlines() if "${{" in line]
    assert expressions == ["GH_TOKEN: ${{ github.token }}", BOOTSTRAP_ENV]


CHECKS = [
    check_triggers,
    check_cron,
    check_dispatch_input,
    check_top_permissions,
    check_job_permissions,
    check_branch_guard,
    check_repository_guard,
    check_checkout_credentials,
    check_pins,
    check_concurrency,
    check_timeout,
    check_bootstrap_reachability,
    check_token_and_expressions,
]

MUTATIONS = {
    check_triggers: [
        (
            "  workflow_dispatch:\n",
            "  push:\n    branches: [output]\n  workflow_dispatch:\n",
        ),
        ("  workflow_dispatch:\n", "  pull_request_target:\n  workflow_dispatch:\n"),
    ],
    check_cron: [("'23 0 * * *'", "'23 1 * * *'")],
    check_dispatch_input: [("        default: false", "        default: true")],
    check_top_permissions: [
        ("\npermissions: {}\n", "\npermissions:\n  contents: write\n")
    ],
    check_job_permissions: [
        ("      contents: write", "      contents: write\n      actions: write"),
    ],
    check_branch_guard: [
        ("github.ref == format", "github.ref != format"),
        ("github.event_name == 'schedule' ||", "github.event_name != 'x' ||"),
    ],
    check_repository_guard: [
        ("'AndrewDongminYoo/github-terrarium'", "'fork/github-terrarium'")
    ],
    check_checkout_credentials: [
        ("persist-credentials: false", "persist-credentials: true")
    ],
    check_pins: [("@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0", "@v7")],
    check_concurrency: [("cancel-in-progress: false", "cancel-in-progress: true")],
    check_timeout: [("timeout-minutes: 15", "timeout-minutes: 360")],
    check_bootstrap_reachability: [
        ('"$@"', '"$@" --bootstrap'),
        ("github.event_name == 'workflow_dispatch' && inputs.bootstrap", "true"),
    ],
    check_token_and_expressions: [
        ("${{ github.token }}", "${{ secrets.PERSONAL_TOKEN }}"),
        ('--repository "$GITHUB_REPOSITORY"', "--repository ${{ github.repository }}"),
    ],
}


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_passes_every_check(self):
        for check in CHECKS:
            with self.subTest(check=check.__name__):
                check(self.text)

    def test_every_check_fails_on_a_mutated_copy(self):
        self.assertEqual(set(MUTATIONS), set(CHECKS))
        for check, cases in MUTATIONS.items():
            for old, new in cases:
                with self.subTest(check=check.__name__, old=old):
                    self.assertIn(old, self.text)
                    with self.assertRaises(AssertionError):
                        check(self.text.replace(old, new, 1))

    def test_run_script_passes_bootstrap_only_for_a_true_input(self):
        script = run_script(self.text)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "python"
            fake.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$ARGS_FILE"\n')
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            for value, expected in (("true", True), ("false", False), ("", False)):
                with self.subTest(bootstrap=value):
                    args = root / "args"
                    env = {
                        "ARGS_FILE": str(args),
                        "BOOTSTRAP": value,
                        "GITHUB_REPOSITORY": REPOSITORY,
                        "GITHUB_STEP_SUMMARY": str(root / "summary.md"),
                        "PATH": f"{root}{os.pathsep}{os.environ['PATH']}",
                    }
                    subprocess.run(["bash", "-e", "-c", script], env=env, check=True)
                    argv = args.read_text().splitlines()
                    self.assertEqual(
                        argv[:9],
                        [
                            "-m",
                            "github_terrarium",
                            "generate",
                            "--config",
                            "terrarium.toml",
                            "--repository",
                            REPOSITORY,
                            "--summary",
                            str(root / "summary.md"),
                        ],
                    )
                    self.assertEqual(argv[9:], ["--bootstrap"] if expected else [])


if __name__ == "__main__":
    unittest.main()
