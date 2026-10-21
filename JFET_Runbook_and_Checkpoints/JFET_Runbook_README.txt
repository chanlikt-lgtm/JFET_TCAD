4H-SiC VERTICAL JFET - TECHNICAL RUNBOOK AND CHECKPOINT KIT
Version 1.0 - 21 October 2026

Included files:
 - JFET_Simulation_Setup_and_Execution_Guide.md: full technical setup/run procedure
 - JFET_Checkpoint_Validator.py: optional read-only checkpoint checks
 - JFET_Checkpoint_Baseline_Results.json: example audit of supplied saved data
 - JFET_Runbook_README.txt: this short file

NOT included:
 - kem948_fig5_package.zip (download the original source separately)
 - The original research article PDF (download separately)

Runbook applicability:
 - The existing Python electron-only reduced model of KEM 948 Figures 5.1/5.2.
 - This package is NOT a quantitative Sentaurus reproduction.

Recommended workflow:
1. Preserve and extract original kem948_fig5_package.zip into a working copy.
2. Install Python 3.13 in a virtual environment plus requirements_kem948.txt.
3. Run simulate_kem948_fig5.py --self-test.
4. Run smoke, coarse nominal+control, and fine nominal+control cases.
5. Use JFET_Checkpoint_Validator.py and retain its JSON report.
6. Review the known geometry and DIBL blockers before any physical claims.

This validator does not modify the simulation source or numerical datasets.
--run-self-test explicitly runs the original numerical self-test.
When --strict is selected, known physical blockers deliberately produce a nonzero exit.

The sample JSON includes machine-specific Python/dependency versions recorded in the
current audit container; it is EXAMPLE evidence, not a claim about your computer.
