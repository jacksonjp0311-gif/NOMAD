# Running a bounded repair on the ROG

NOMAD remains v0.18.0. This workflow uses the existing CLI and local native
learners. It makes no cloud calls. An unfamiliar repository is never executed
on the host. The current machine still needs the [approved native setup](OPERATIONS_NATIVE_V018.md)
and thirteen actually passing containment probes before a real repair can run.

## Inspect before executing

From the extracted source/runtime folder, with Python 3.11 or later:

```powershell
py -3 -B -m nomad.platform_cli inspect-source --source C:\work\subject
```

This copies within existing source quotas, parses source without importing it,
and reports admitted modules, function names and import edges. Unsupported
Python is an explicit HOLD with a reason. The bounded adapter accepts JSON
function calls and local imports, not arbitrary Python repositories, dependency
installation, classes, reflection or external imports. Inspection is not a
security qualification and does not establish that a repair exists.

Prepare a reviewed contract JSON outside the source with `adapter` set to
`python-functions-v1`, `goal_text`, and disjoint `public`, `challenge`, `final`
case arrays. A case has `module`, `function`, `args`, optional `kwargs`, and
`expected` or a supported `raises` exception name. Only public outcomes influence search.
Challenge and final cases require independent authorship/review; separation
of fields alone does not make a test independent. Do not copy private research
contracts into development examples.

## One command for the supported mission

After native setup and qualification, use the image and exact resource policy
bound by the resulting isolation receipt:

```powershell
py -3 -B -m nomad.platform_cli repair --isolation-receipt runs\native\isolation.json --root runs\repair-001 --source C:\work\subject --contract C:\work\contracts\repair.json --memory-root runs\verified-memory
```

The command verifies the containment receipt, initializes an immutable source
snapshot, inspects/localizes, chooses public diagnostic probes, generates a
bounded inventory including eligible GENESIS expressions, evaluates candidates,
invokes WITNESS, runs the separate final check and retains admissible verified
memory. Its original input folder is not patched. A successful result includes
the proposed diff, source hashes, diagnostic evidence and verification receipts.
Missing infrastructure, an unsupported interface, no supported candidate,
rejection or uncertain execution is reported explicitly; none becomes success.

Typed function missions default to conventional temporal learning with the
unreliable detector disabled and selective warm states. `--mechanism native`
selects the unchanged original BGR runtime; `--mechanism frequency` selects the
cheap baseline. These are operating choices, not performance claims. Explicit
legacy `--ranker` and research controller options remain available and mutually
exclusive; a research configuration can intentionally override these defaults.
The arithmetic adapter retains its existing separate behavior.

Default proposal inventory is at most 64, further capped to 32 for temporal
operation; at most two temporal probes and 1,024 GENESIS evaluations. The default
96 dispatch budget includes public search, independent verification and recovery.
Do not enlarge a budget merely to turn a failed acceptance check into a pass.

## Review, accept or reject, and resume

```powershell
py -3 -B -m nomad.platform_cli status --root runs\repair-001
py -3 -B -m nomad.platform_cli review --root runs\repair-001
py -3 -B -m nomad.platform_cli accept --root runs\repair-001 --output runs\accepted-001
# Alternatively:
py -3 -B -m nomad.platform_cli reject --root runs\repair-001 --output runs\rejected-001
```

Accept/reject records the operator's review decision in a new directory, with
`proposed.patch` and `receipt.json`. It does not apply the patch to the original
repository, deploy code, or change WITNESS's result. Both export commands require
a completed independently checked mission. Inspect a failed or unfinished mission
with `status`; it has no accepted patch to export. To apply an accepted patch,
first check the recorded original file hashes, then use `git apply --check` and
`git apply` explicitly in the original repository after review.

```powershell
py -3 -B -m nomad.platform_cli recover --root runs\repair-001
py -3 -B -m nomad.platform_cli run --root runs\repair-001
```

Recovery confirms disposal of an ambiguous container before retrying. A lost
result cannot authorize success or learning. `run` resumes existing journaled
work and does not repeat an already completed mission. Use a new mission root
when source, policy, implementation or contract changes; incompatible state is
refused, not migrated silently.

## Current authentic repair result

**NOT_RUN.** The [bounded task assessment](../results/AUTHENTIC_TASK_OPERATIONS_V018.json)
records the exact inspected upstream issue/commit/source hashes. Neither checked
full upstream module fits the present admitted interface. An exact function
projection is retained only as a parse fixture, not presented as a full-repository
repair. No public upstream regression was executed on the host, and no substitute
private final contract was fabricated. Actual containment and an eligible complete
task remain prerequisites for an authentic accepted patch.
