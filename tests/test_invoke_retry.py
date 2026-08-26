import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPT = (
    Path(__file__).parents[1] / "scripts" / "invoke_agent_with_retry.sh"
)
BASH = (
    r"C:\Program Files\Git\bin\bash.exe"
    if os.name == "nt"
    else "bash"
)


class InvokeRetryTests(unittest.TestCase):
    def test_retries_through_five_throttles(self):
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            fake_bin = directory_path / "bin"
            fake_bin.mkdir()
            state_path = directory_path / "attempts"
            fake_azd = fake_bin / "azd"
            fake_azd.write_text(
                textwrap.dedent(
                    f"""\
                    #!/usr/bin/env bash
                    count=0
                    if [[ -f "{state_path}" ]]; then
                      count="$(cat "{state_path}")"
                    fi
                    count=$((count + 1))
                    echo "$count" > "{state_path}"
                    if ((count < 6)); then
                      echo 'event: response.failed'
                      echo 'Requests have exceeded the throughput limit'
                      exit 1
                    fi
                    echo 'event: response.completed'
                    echo 'SMOKE_OK'
                    """
                ),
                encoding="utf-8",
            )
            fake_azd.chmod(0o755)
            output_path = directory_path / "response.txt"
            environment = os.environ.copy()
            environment.update(
                {
                    "AZD_COMMAND": fake_azd.as_posix(),
                    "SMOKE_MAX_ATTEMPTS": "6",
                    "SMOKE_RETRY_BASE_SECONDS": "0",
                    "SMOKE_RETRY_MAX_SECONDS": "0",
                }
            )

            result = subprocess.run(
                [
                    BASH,
                    SCRIPT.as_posix(),
                    output_path.as_posix(),
                    "SMOKE_OK",
                    "Test prompt",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(
                "6",
                state_path.read_text(encoding="utf-8").strip(),
            )

    def test_passes_explicit_agent_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            arguments_path = directory_path / "arguments.txt"
            fake_azd = directory_path / "azd"
            fake_azd.write_text(
                textwrap.dedent(
                    f"""\
                    #!/usr/bin/env bash
                    printf '%s\n' "$@" > "{arguments_path}"
                    echo 'event: response.completed'
                    echo 'SMOKE_OK'
                    """
                ),
                encoding="utf-8",
            )
            fake_azd.chmod(0o755)
            output_path = directory_path / "response.txt"
            environment = os.environ.copy()
            environment["AZD_COMMAND"] = fake_azd.as_posix()

            result = subprocess.run(
                [
                    BASH,
                    SCRIPT.as_posix(),
                    output_path.as_posix(),
                    "SMOKE_OK",
                    "Test prompt",
                    "https://example.test/agents/green/responses?api-version=v1",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            arguments = arguments_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(
                [
                    "ai",
                    "agent",
                    "invoke",
                    "--agent-endpoint",
                    "https://example.test/agents/green/responses?api-version=v1",
                    "Test prompt",
                    "--new-session",
                    "--no-prompt",
                    "--output",
                    "raw",
                ],
                arguments,
            )


if __name__ == "__main__":
    unittest.main()
