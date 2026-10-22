# Execution ledger: 2026-10-22-cpu-optimizations.md

- Baseline: 40 existing tests pass. No Git checkout is present; implementation proceeds in place.
- Pre-flight: settings revisions feed worker snapshots and parked-worker conditions; rendering consumes the same settings snapshot as notification overlays. Frame advancement remains independent from output composition. Packet validation remains mandatory on cache hits.
- Ruling: benchmark normalizes transport to a fake write, so performance runs cannot compete with the user's existing keyboard controller. Whole-app post-update CPU sampling requires the updated app to run; do not compare a stale process as if it ran new code.
- Task 1: baseline saved to cpu-baseline.json before product changes. No-copy test failed before the fix and passed afterward, including odd/non-RGB image equivalence.
- Task 2: revision and flag API tests failed before implementation; snapshots now copy only on changes, GUI get remains defensive, notifications receive revision-tagged snapshots.
- Tasks 3 and 5: cache instrumentation and advance/render tests failed before implementation. ReferenceEngine freezes the old algorithm and verifies exact outputs across 5 capture rates and 3 smoothing values. Main-loop fake clock verifies fewer render calls than loop wakes, each paired with a requested USB write.
- Task 4: condition, wakeup, and parked-worker tests failed before implementation. Shutdown notifies conditions before joins. Enabled key scanning and notification intervals remain unchanged.
- Final independent review identified stale supplied notification snapshots and a query-cancellation missed-wakeup race. Both now have failing-then-passing regressions; direct test-file execution also works after moving its main guard below the reference class.
- Ruling: notification overlay now takes an optional revision alongside supplied options and refuses older snapshots. Cost: one extra integer argument on the internal render path; fixes capture-time settings races.
- Ruling: disabled notification parking uses the revision captured with the disabled decision, not a revision another path may publish during query cancellation. Cost: an immediate recheck after a concurrent settings update, instead of a missed wakeup.
- Ruling: packet validation is retained on every send, including a cache hit. Cost: encoding-cache improvement is intentionally smaller than a version that skipped validation.
- Ruling: the benchmark's previous changing_frame actually recaptured a static image, so the baseline metric was relabeled resampled_static_frame without changing its value. A genuinely alternating-image case is reported separately without a misleading pre-change comparison.
- All 56 tests pass, including direct execution of test_performance.py and the full unittest suite.
- Measurements saved to cpu-optimized.json. Average mapping CPU: 8.594 -> 3.516 ms/call; spatial: 9.766 -> 4.688; stable frame: 0.250 -> 0.007812; repeated fake send: 0.160156 -> 0.136719. Unchanged snapshot: 0.000516 ms/call versus GUI deep copy 0.042969. These are component comparisons, not total-app CPU savings.
- Native worker smoke check: Connected, no old notification replay, Disabled after settings change, both threads stopped in about 1.5 ms using stop plus condition wakeup. Temporary settings only; no keyboard writes.
- Ruling: leave the user's pre-existing tray process and saved preferences intact. Cost: matched whole-app before/after CPU measurement and physical confirmation remain pending after restart; the final result makes no total-CPU reduction claim.
- Implementation, final review fixes, component benchmarking, native worker verification, and documentation complete. Pending checks are explicitly listed in VALIDATION.md.
