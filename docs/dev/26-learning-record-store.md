# 26 — The Learning Record Store

**Scope.** Where learning keeps what it knows: the per-vacuum directory layout, the three record
kinds on disk, and the read and write disciplines that stop a torn file from becoming a wrong
statistic. What qualifies a run for learning is [27](27-learning-eligibility.md); how records
become statistics is [28](28-learning-statistics.md). The run-side half — how a run reaches
finalization at all — is [06 — How a Run Ends](06-run-end.md).

This layer holds one rule above the rest, stated in the module's own header: **all finalized jobs
may be archived to history; only eligible completed jobs are used for learning.** Archiving and
learning are different decisions about the same file, and every design below follows from keeping
them separate.

---

## 1. JSON is the source of truth and CSV is an export

`learning/history_store.py::LearningHistoryStore` writes JSON files and treats them as primary.
CSV exists so a person can open the history in a spreadsheet, and it is regenerated wholesale from
the JSON rather than maintained alongside it.

That is a deliberate asymmetry. A store with two authorities has to reconcile them; a store with
one authority and a projection only has to regenerate. The cost is that a CSV refresh is O(all
jobs) — see §8.

---

## 2. Six directories, three record kinds

`learning/history_store.py::get_paths` resolves six directories per vacuum:

| directory | holds |
|---|---|
| `jobs/` | completed-job records — **and phase children** |
| `learned/` | the derived stores: room stats, job stats, jobs index, accuracy stats |
| `exports/` | the CSV projections |
| `live/` | the in-flight snapshot |
| `phases/` | break records — a wait or a charge |
| `phased_jobs/` | parents — the run a user actually started |

Three record kinds live in them, and each carries `schema_version` and an explicit `record_type`:
`completed_job`, `phased_job`, and the phase break record. Typing the record rather than inferring
its kind from its directory is what lets
`learning/history_store.py::is_learning_job` refuse anything that is not a completed job in one
check, wherever the file came from.

---

## 3. A phase child is still a job, and that is the whole design

When a run can pause to charge and resume, the obvious modelling is a new job kind that contains
phases. This does the opposite: **children keep living in `jobs/` as ordinary completed-job
records**, and the two new directories hold new *record kinds* rather than a new kind of job.

The reason is stated in the dataclass itself — a child is a job in the full sense, so every
existing consumer of `jobs/` keeps working on it unchanged. The alternative would have required
every reader of job history to learn about phases before it could read anything at all.

What the parent adds is the things only a parent knows. `learning/history_store.py::close_phased_job`
resolves each unreached phase to one of two outcomes, and the distinction is user-facing rather
than internal: a run that was torn down records its later phases as cancelled upstream, while a run
that simply ended early records them as never run. `learning/history_store.py::_CANCEL_REASONS` is
the set that decides which — *"you stopped it" reads differently from "it ended early."*

---

## 4. Reads are tri-state, and the difference is load-bearing

`learning/history_store.py::read_json_outcome` returns one of three outcomes — OK, absent, or
unreadable — rather than a payload-or-`None`. The contract on top of it is explicit:

> Destructive read-modify-write callers MUST refuse on UNREADABLE; read-only paths may keep
> treating both non-OK outcomes as "no data".

This is the difference between *nothing was ever written here* and *something is written here and
we cannot read it*, and collapsing them destroys data. A rebuild that reads a corrupt stats file as
"absent" will happily write a fresh one over the top; the same rebuild that sees "unreadable"
refuses and leaves the evidence in place.

Two details make it work in practice:

- **A zero-byte file is unreadable, not absent.** An empty file is a torn write, not a store that
  never existed, and it is classified accordingly.
- **Corruption is recoverable for readers and fatal for writers.** The derived statistics can be
  rebuilt from the job records, so a reader may proceed; a writer must never overwrite. It
  self-heals on the next atomic write.

`learning/history_store.py::read_json` remains as a `None`-tolerant wrapper so existing read paths
keep their old behaviour. It is a compatibility shim, not the interface to reach for.

---

## 5. The record's rooms are the job's own, frozen at launch

`learning/history_store.py::build_completed_job_payload` takes room identity from the active-job
snapshot captured at launch — **never** from the live payload or queue.

This is not defensive style; it is a fix for an observed corruption. Re-queueing rooms on top of a
running job caused the composer to re-hydrate the live payload, and the running job's record was
rewritten to match: a Kitchen + Hallway + zone run was recorded as Dining + Kitchen + Hallway, with
the zone dropped.

For a phased run the precedence goes further — the record takes the **union of all phases' rooms**,
deduplicated and in order. Trusting the parent's top-level list is wrong, because advancing a phase
overwrites it with only the phase just entered. A stepped run ending on a room phase would record
just the last room and drop the earlier ones from both the room count and learning; one ending on a
roomless zone phase would record no rooms at all and be discarded as invalid.

The record's `outcome` block is where the eligibility verdict is stored — status, the learning flag,
the sanity result, and the specific blockers — so a record carries the reason it was or was not
learned from, not merely the verdict. Doc 27 covers how those are decided.

---

## 6. `job_id` is untrusted input on two service paths

Job ids round-trip through the exclude and restore services, so on those paths the id is
user-supplied, and the path getter interpolates it directly into a filesystem path. `pathlib` does
not normalise `..`.

`learning/history_store.py::_JOB_ID_RE` guards it, and the choice recorded in place is to **reject
rather than sanitise**: a malformed id can never be a real job's file, so there is nothing to
recover by rewriting it. The pattern stays permissive about shape — the finalizer generates
timestamped ids, but imports, tests and external tooling use other shapes — and excludes only path
separators. The external-run path applies the same reasoning to its own ids.

---

## 7. What the path is derived from, and what that costs

`learning/history_store.py::_vacuum_slug` derives the per-vacuum directory from the entity id's
object id. Everything a vacuum has ever learned lives under that name.

⚠ **Renaming the vacuum entity therefore orphans its entire history**, and the predictor restarts
from nothing. And the tree is the smaller half: seventeen sections of the HA store are keyed by the
same entity id, so a rename strands every room, run profile and setting too — the vacuum comes back
as brand new. Nothing detects it ([03 §5](03-data-model.md)).

The file's own invariant block records this as a known finding attributed to a repair
packet — and that same block warns, in its own words, that a packet id there is an *attribution*
rather than a verification, with 35 of 60 claims naming a packet whose commits never touched the
file the claim sits in. Treat the closure as unverified until read.

`learning/history_store.py::ensure_dirs` is reached from thirteen path getters, one per warm-path
operation, and is memoized per process and vacuum so only the first call does the `mkdir` pass. The
declared invariant behind it is that no disk work belongs on the event loop; the slug is the cache
key so differently-cased callers collapse onto one entry. The three derived stores are separately
cached for reads, and `learning/history_store.py::warm_estimate_caches` fills them ahead of the
estimator rather than letting the first prediction pay for the disk.

---

## 8. Surfaces that do not do what they say

**The O(1) CSV path exists, is tested, and is used by nothing — deliberately.**
`learning/history_store.py::append_csv_row` appends a single row and manages the header correctly.
Its only callers are unit tests. Every production CSV refresh goes through
`learning/history_store.py::rebuild_jobs_csv` and its rooms counterpart, which re-read the whole
job history and rewrite the file. The tests prove the function works, which is exactly why it read
as live — a passing test demonstrates behaviour, never use.

The hazard was never the dead code; it was that wiring it looks like an obvious win. It is the O(1)
answer to an O(all jobs) refresh, it is correct, and it has passing tests beside it. **Wiring it
would undo §1.** JSON is the single authority precisely so the projection cannot drift; an
incremental append makes the CSV a second source of truth, and one missed append — a failed write,
a job excluded after the fact — leaves the two disagreeing with nothing to detect it. The O(all
jobs) cost is what buys that guarantee.

The function now says so in its own docstring, and a test asserts it has no production caller, so
the reasoning has to be argued with rather than merely noticed. If the refresh needs to be faster,
make `rebuild_jobs_csv` cheaper.

**`read_json` looks like the read API and is the compatibility shim.** It is the shorter, more
obvious name, it is what a new caller will reach for, and it silently discards the distinction §4
exists to preserve. Its docstring now says LEGACY SHIM and states the rule: read-only paths may use
it, and any caller that then WRITES must use `read_json_outcome` and refuse on UNREADABLE.

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
