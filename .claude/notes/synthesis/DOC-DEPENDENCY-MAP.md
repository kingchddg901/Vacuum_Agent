# Doc-level dependency map (module import graph, generated 2026-08-07)

Regenerate: the script lives in git history of this file's generating commit.
PURPOSE: the interface-change re-validation rule — a closure that alters a doc's
PROVIDES surface flags every doc listing it below as provisional.

CAVEAT (Chris, 2026-08-07): these are REFERENCE edges, not REQUIREMENT edges — doc 32
measured that most are optional consumption through absence-tolerant seams; the atom
(adapter+dispatch+rooms+spine+active_job) runs with all rings absent. Use this map for
interface-change re-validation fan-out, NEVER as a build-requirement graph.

MEASURED: only 5 of 26 docs are dependency-free; the remainder is one mutually-
recursive cluster — a topological ablation order DOES NOT EXIST for this corpus.

| doc | depends on (its modules import theirs) |
|---|---|
| 02-ha-integration | 03-data-model, 04-listeners, 05-core-manager, 08-rooms-system, 10-learning-system, 11-mapping-system, 12-battery-system, 15-setup-system, 21-adapter-system, 23-error-tracker |
| 03-data-model | 25-eufy-adapter |
| 04-listeners | 05-core-manager, 06-job-lifecycle, 08-rooms-system, 10-learning-system, 15-setup-system, 21-adapter-system |
| 05-core-manager | 06-job-lifecycle, 07-queue-engine, 08-rooms-system, 10-learning-system, 11-mapping-system, 13-maintenance-manager, 14-dock-manager, 16-profile-manager, 17-map-manager, 18-onboarding-manager, 21-adapter-system |
| 06-job-lifecycle | 04-listeners, 05-core-manager, 08-rooms-system, 10-learning-system, 21-adapter-system |
| 07-queue-engine | 16-profile-manager, 21-adapter-system |
| 08-rooms-system | 05-core-manager, 15-setup-system, 16-profile-manager, 17-map-manager, 21-adapter-system |
| 09-room-rules-system | — |
| 10-learning-system | 12-battery-system, 16-profile-manager, 17-map-manager, 23-error-tracker |
| 11-mapping-system | 05-core-manager, 08-rooms-system, 17-map-manager, 21-adapter-system, 25-eufy-adapter, 26-eufy-segmentor |
| 12-battery-system | 06-job-lifecycle, 21-adapter-system |
| 13-maintenance-manager | 05-core-manager, 21-adapter-system |
| 14-dock-manager | 05-core-manager, 06-job-lifecycle, 21-adapter-system |
| 15-setup-system | 08-rooms-system, 17-map-manager, 21-adapter-system |
| 16-profile-manager | 05-core-manager, 08-rooms-system, 17-map-manager, 21-adapter-system |
| 17-map-manager | 08-rooms-system, 16-profile-manager |
| 18-onboarding-manager | 08-rooms-system, 21-adapter-system |
| 21-adapter-system | 07-queue-engine, 11-mapping-system |
| 22-adapter-config-reference | — |
| 23-error-tracker | 06-job-lifecycle, 21-adapter-system |
| 25-eufy-adapter | 11-mapping-system, 16-profile-manager |
| 26-eufy-segmentor | — |
| 28-external-run-ingestion | 05-core-manager, 10-learning-system, 11-mapping-system |
| 29-roborock-adapter | — |
| 30-phase-runner | 05-core-manager, 07-queue-engine, 10-learning-system, 21-adapter-system |
| 31-map-source-coordinator | — |
