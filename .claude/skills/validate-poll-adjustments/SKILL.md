---
name: validate-poll-adjustments
description: Validate the presidential polling project's weighted averages, smoothing, historical bias adjustments, uncertainty displays, and experimental models. Use when changing formulas, calibration data, dashboard charts, or claims about 2027 polling trends.
---

# Validate poll adjustments

Read `AGENT.md` and `METHODOLOGIE_BIAIS_ET_AJUSTEMENTS.md`, then inspect the relevant reference data, calculation, dashboard label, and tests.

1. Name the input source, fieldwork period, election or round, scenario, party mapping, correction baseline, and data version. Separate the 2022 presidential first-round baseline from the experimental 2024 legislative second-round benchmark.
2. Write down the formula, weights, exclusions, time window, and missing-value policy before changing a computation. Verify units, finite values, totals, duplicate handling, and sample-size assumptions.
3. Compare raw and adjusted series on identical inputs. Check representative historical examples and sensitivity to plausible changes in weights, window, or calibration set.
4. Identify uncertainty from sampling, extraction, modeling, and extrapolation separately when possible. Label observed, reconstructed, corrected, smoothed, simulated, and sample values distinctly in exports and charts.
5. Treat ML outputs as bias-correction experiments. Document the target, train/test separation, baseline, metrics, seeds, and limits before interpreting a result.
6. Add focused numerical and regression tests for the changed behavior. Report test commands, data provenance, important differences, and unresolved limitations.

Do not describe an aggregate or correction as a certain election prediction.
