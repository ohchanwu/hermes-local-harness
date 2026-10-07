# Release CI portability

Use these checks when a deployment release gate passes locally but fails on a hosted Linux runner.

## Reproduce the runner, not the laptop

1. Record the failing step and every downstream step skipped by the early exit.
2. Reproduce the exact workflow command, including its explicit interpreter. A command such as `sh script.sh` overrides the file's shebang, so Bash-only syntax fails even when the script starts with `#!/usr/bin/env bash`; enforce the supported interpreter in both the workflow and its contract tests.
3. Run the focused contract in a container matching the hosted runner OS and the relevant tool major version.
4. Keep the local check, container check, and hosted workflow check distinct; one does not substitute for another.
5. After the focused fix, rerun the complete release workflow path so skipped race, integration, build, and packaging gates execute.

## jq 1.6 object values

Parenthesize a complete concatenation used as an object value. Older jq parsers can reject an otherwise plausible expression at the `+` token.

```jq
{
  resource_changes: ((base_changes) + [extra_change])
}
```

Exercise both valid fixtures and every fail-closed rejection fixture under jq 1.6.

## BSD/GNU command probes

Never let stdout from a failed compatibility probe enter command substitution. Some GNU commands print output before returning failure for BSD-style flags.

```bash
file_mode() {
  local path="$1"
  local mode
  if mode="$(stat -f '%Lp' "$path" 2>/dev/null)"; then
    printf '%s\n' "$mode"
  else
    stat -c '%a' "$path"
  fi
}
```

Test the failed-probe path explicitly with a stub that writes noisy stdout and returns nonzero; the result must contain only the fallback value.

## Mutation-test portability

Run shell mutation suites under both the hosted distribution and a BusyBox/Alpine environment when they parse or rewrite YAML. Assert that each mutation actually changed exactly the intended occurrence before treating the checker result as meaningful; otherwise a non-portable rewrite can leave the fixture unchanged and create a false acceptance.

Do not pass a replacement line ending in a backslash through `awk -v`; awk implementations disagree about when that trailing escape is consumed. Export the literal as an environment variable and read it through `ENVIRON`, then assert the source count changed from the expected number to the expected result before running the mutated checker.

## POSIX shell percent decoding

Treat URI credential decoding as byte-preservation and secret-handling code. Do not use `printf %b` with `\xHH` when the runtime shell may be dash, because hexadecimal escapes are not portable. Convert validated hex pairs to octal escapes, reject encoded NUL, and never use `eval`.

Command substitution strips trailing newline bytes. When decoded output can contain `%0A`, append a known non-newline sentinel inside the substitution and remove exactly that sentinel afterward; otherwise an embedded or newline-only password is silently corrupted. Test at least lowercase and uppercase hex, reserved URI characters, shell metacharacters, malformed/incomplete escapes, encoded NUL, `%0A` in the middle, and `%0A` as the entire value. Verify the decoded secret reaches only the intended transient environment variable and never command arguments, logs, error text, or archive output.

## Coupled artifact digests

When a test fixture or infrastructure plan embeds the digest of a runtime asset, update that digest in the same candidate as every byte change to the asset. Recompute it from the exact repository bytes, assert the current digest occurs at the expected count and the stale digest is absent, then run the consuming contract under the hosted-runner environment. A locally green producer test does not prove its downstream digest fixture is current.

## Local integration database ownership

Use the repository's managed database startup path when integration tests validate container or Compose ownership. A generic disposable container on the expected port can pass direct database tests while failing preview or bootstrap ownership checks. Inspect the workflow and startup contract before reserving that port, and create a uniquely named test database inside the supported managed instance rather than substituting the instance. Do not enable optional database variables for a broad suite until every subprocess's routing has been inspected.

## Real-process timeout enforcement

Exercise timeout and cleanup behavior against a real disposable local child in the actual execution environment before certifying a bounded live probe. Mocked process-group kills do not establish syscall permission. A failed kill or reap is failed acceptance even when later inspection finds no surviving child. This validates a technical operation timeout; it does not create a campaign deadline.

## Bundled CLI SDK contracts

When reusing an SDK bundled inside a pinned cloud CLI, inspect that installation's import and retry contracts rather than assuming standalone-library behavior. Some distributions install aliases only after importing the CLI package or interpret `max_attempts` as total attempts. Validate the exact configuration with an offline stub before using it in an authorized packet.

## TLS-terminating database bridges

A terminating PostgreSQL bridge creates two TLS sessions with different certificates. A client choosing `SCRAM-SHA-256-PLUS` binds its proof to the bridge certificate, not the upstream certificate, so a byte relay cannot preserve end-to-end channel binding. Prefer a direct endpoint-verifying or transparent tunnel. If a reviewed one-shot bridge is unavoidable, make any ordinary-SCRAM disposition explicit, retain upstream CA and hostname verification, keep each TLS socket's relay operations in one bounded nonblocking owner, and stress the exact client handshake plus shutdown behavior against disposable peers.

## Synthetic Git repositories

Tests that create commits must supply `user.name` and `user.email` through command-scoped `git -c` options. Verify them with system and global Git configuration disabled and `user.useConfigOnly=true`; relying on a developer's ambient identity makes the test fail only on clean runners and weakens isolation.

## Workflow credentials

Inspect workflow source rather than copied logs. A redaction marker such as `***` must never appear as the literal authorization value. Bind the approved scoped token through `env`, reference that variable in the request header, and mutation-test the exact token source plus the exact count and ordering of pre/post publication visibility checks.
