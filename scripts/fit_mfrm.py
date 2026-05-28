#!/usr/bin/env python3
"""Many-Facet Rasch Model (MFRM) for binary depression judgments.

Treats each binary prediction as a measurement event:
    interview  → object being measured  (θ_i: depression severity)
    model/API  → rater/judge            (α_m: judge severity bias)
    condition  → rating condition       (γ_c: input-condition bias)
    method     → scoring format         (δ_method: item-threshold vs global bias)

Fitted model (fixed-effects logistic):
    logit P(Y_imc = 1) = θ_i + α_m + γ_c + δ_method

This reframes accuracy comparisons as facet estimates: which judge is more
severe? which input condition inflates positive ratings? does the method
(item-threshold vs global) shift the rating threshold?

Usage
-----
    python scripts/fit_mfrm.py
    python scripts/fit_mfrm.py --drop-interviewer-only false
    python scripts/fit_mfrm.py --method global --ref-model gpt-4o
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Optional

import pandas as pd
import statsmodels.api as sm

PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ANALYSIS_DIR = PROJECT_DIR / "outputs" / "analysis"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_analysis_csvs(analysis_dir: Path) -> pd.DataFrame:
    """Load all *_outputs.csv files and return a deduplicated wide DataFrame."""
    frames = []
    for path in sorted(analysis_dir.glob("*_outputs.csv")):
        with path.open(newline="", encoding="utf-8") as f:
            frames.append(pd.DataFrame(list(csv.DictReader(f))))
    if not frames:
        raise FileNotFoundError(f"No *_outputs.csv files found in {analysis_dir}")
    df = pd.concat(frames, ignore_index=True)
    # Guard against duplicate (interview × model × condition × metadata_condition) rows
    df = df.drop_duplicates(
        subset=["interview_id", "model_name", "condition", "metadata_condition"]
    )
    return df


def build_long_frame(
    df: pd.DataFrame,
    include_methods: tuple[str, ...] = ("item", "global"),
) -> pd.DataFrame:
    """Melt wide format to long: one row per (interview, model, condition, method).

    Parameters
    ----------
    df : wide-format DataFrame from load_analysis_csvs
    include_methods : subset of {"item", "global"} to include as method levels

    Returns
    -------
    DataFrame with columns: interview_id, model_name, full_condition, method, Y, PHQ8_Binary
    """
    method_col = {"item": "thresholded_item_binary", "global": "global_binary_judgment"}
    parts = []
    for key in include_methods:
        if key not in method_col:
            raise ValueError(f"Unknown method '{key}'. Choose from {list(method_col)}")
        sub = df[
            ["interview_id", "model_name", "condition", "metadata_condition",
             method_col[key], "PHQ8_Binary"]
        ].copy()
        sub = sub.rename(columns={method_col[key]: "Y"})
        sub["method"] = key
        parts.append(sub)

    long = pd.concat(parts, ignore_index=True)
    long["full_condition"] = long["metadata_condition"] + "_" + long["condition"]
    long["Y"] = long["Y"].astype(int)
    long["PHQ8_Binary"] = long["PHQ8_Binary"].astype(int)
    return long[["interview_id", "model_name", "full_condition", "method", "Y", "PHQ8_Binary"]]


# ---------------------------------------------------------------------------
# Model fitting
# ---------------------------------------------------------------------------

def fit_many_facet_rasch(
    analysis_dir: Optional[Path | str] = None,
    df: Optional[pd.DataFrame] = None,
    include_methods: tuple[str, ...] = ("item", "global"),
    reference_interview: Optional[str] = None,
    reference_model: Optional[str] = None,
    reference_condition: Optional[str] = None,
    reference_method: Optional[str] = None,
    drop_interviewer_only: bool = True,
) -> dict:
    """Fit a many-facet Rasch logistic model to binary depression judgments.

    logit P(Y=1) = θ_i + α_m + γ_c + δ_method

    Facets
    ------
    θ_i      interview severity (depression)       — one param per interview
    α_m      model/judge severity bias             — one param per API
    γ_c      input-condition bias                  — one param per condition
    δ_method scoring-format bias                   — one param when both methods used

    Each facet is dummy-coded; the specified reference level is fixed at 0.
    The model intercept absorbs the log-odds at all reference levels combined.

    Parameters
    ----------
    analysis_dir : directory containing *_outputs.csv (default: outputs/analysis)
    df : pre-loaded wide DataFrame (alternative to analysis_dir)
    include_methods : which binary outcomes to include; pass ("global",) to fix method facet
    reference_interview : interview_id held at 0 (default: numerically smallest)
    reference_model : model name held at 0 (default: first alphabetically)
    reference_condition : full_condition string held at 0 (default: first alphabetically)
    reference_method : "item" or "global" held at 0 (default: "global")
    drop_interviewer_only : exclude interviewer_only rows (near-zero variance, unreliable)

    Returns
    -------
    dict with keys
        result      : statsmodels GLMResultsWrapper (full model object)
        params      : DataFrame[name, facet, level, estimate, se, z, p, ci_lower, ci_upper]
        theta       : Series of interview severity estimates indexed by interview_id
        alpha       : Series of model bias estimates indexed by model_name
        gamma       : Series of condition bias estimates indexed by full_condition
        delta       : Series of method bias estimates (None if single method)
        long_df     : long-format DataFrame used for fitting
        reference   : dict of reference levels for each facet
    """
    if df is None:
        if analysis_dir is None:
            analysis_dir = DEFAULT_ANALYSIS_DIR
        df = load_analysis_csvs(Path(analysis_dir))

    long = build_long_frame(df, include_methods=include_methods)

    if drop_interviewer_only:
        long = long[~long["full_condition"].str.contains("interviewer_only")].copy()

    if long.empty:
        raise ValueError("Long-format DataFrame is empty after filtering.")

    # Determine reference levels
    ref_interview = reference_interview or min(long["interview_id"].unique(), key=int)
    ref_model = reference_model or sorted(long["model_name"].unique())[0]
    ref_condition = reference_condition or sorted(long["full_condition"].unique())[0]
    ref_method = reference_method or (
        "global" if "global" in long["method"].unique() else sorted(long["method"].unique())[0]
    )

    # Dummy-code facets, dropping the reference level from each
    interview_dummies = pd.get_dummies(long["interview_id"], prefix="theta").astype(int)
    interview_dummies = interview_dummies.drop(
        columns=[f"theta_{ref_interview}"], errors="ignore"
    )

    model_dummies = pd.get_dummies(long["model_name"], prefix="alpha").astype(int)
    model_dummies = model_dummies.drop(columns=[f"alpha_{ref_model}"], errors="ignore")

    condition_dummies = pd.get_dummies(long["full_condition"], prefix="gamma").astype(int)
    condition_dummies = condition_dummies.drop(
        columns=[f"gamma_{ref_condition}"], errors="ignore"
    )

    X_parts: list[pd.DataFrame] = [interview_dummies, model_dummies, condition_dummies]

    fit_method_facet = len(include_methods) > 1
    if fit_method_facet:
        method_dummies = pd.get_dummies(long["method"], prefix="delta").astype(int)
        method_dummies = method_dummies.drop(columns=[f"delta_{ref_method}"], errors="ignore")
        X_parts.append(method_dummies)

    X = pd.concat(X_parts, axis=1).astype(float)
    X = sm.add_constant(X, has_constant="add")
    y = long["Y"].astype(float)

    result = sm.GLM(y, X, family=sm.families.Binomial()).fit(disp=False)

    # Build readable parameter table
    coef = result.params
    se = result.bse
    tval = result.tvalues
    pval = result.pvalues
    ci = result.conf_int()

    def _row(name: str, facet: str, level: str) -> dict:
        return {
            "name": name,
            "facet": facet,
            "level": level,
            "estimate": float(coef[name]),
            "se": float(se[name]),
            "z": float(tval[name]),
            "p": float(pval[name]),
            "ci_lower": float(ci.loc[name, 0]),
            "ci_upper": float(ci.loc[name, 1]),
        }

    rows = [_row("const", "intercept",
                 f"ref interview={ref_interview}, model={ref_model}, "
                 f"condition={ref_condition}"
                 + (f", method={ref_method}" if fit_method_facet else ""))]

    for col in interview_dummies.columns:
        rows.append(_row(col, "theta (interview severity)", col.removeprefix("theta_")))
    for col in model_dummies.columns:
        rows.append(_row(col, "alpha (model severity bias)", col.removeprefix("alpha_")))
    for col in condition_dummies.columns:
        rows.append(_row(col, "gamma (condition bias)", col.removeprefix("gamma_")))
    if fit_method_facet:
        for col in method_dummies.columns:
            rows.append(_row(col, "delta (method bias)", col.removeprefix("delta_")))

    params_df = pd.DataFrame(rows)

    # Reconstruct full facet Series including reference level (fixed at 0)
    def _extract_facet(prefix: str, ref_level: str) -> pd.Series:
        mask = params_df["name"].str.startswith(prefix + "_")
        sub = params_df.loc[mask].set_index("level")["estimate"]
        sub.index = sub.index.astype(str)
        ref_label = str(ref_level)
        if ref_label not in sub.index:
            sub.loc[ref_label] = 0.0
        return sub.sort_index()

    theta = _extract_facet("theta", ref_interview)
    alpha = _extract_facet("alpha", ref_model)
    gamma = _extract_facet("gamma", ref_condition)
    delta = _extract_facet("delta", ref_method) if fit_method_facet else None

    return {
        "result": result,
        "params": params_df,
        "theta": theta,
        "alpha": alpha,
        "gamma": gamma,
        "delta": delta,
        "long_df": long,
        "reference": {
            "interview": ref_interview,
            "model": ref_model,
            "condition": ref_condition,
            "method": ref_method if fit_method_facet else None,
        },
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _sig_stars(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    if p < 0.10:
        return "."
    return ""


def build_markdown_report(mfrm: dict) -> str:
    """Return a markdown report string for the fitted MFRM."""
    result = mfrm["result"]
    ref = mfrm["reference"]
    params = mfrm["params"]
    theta = mfrm["theta"]

    has_method = ref["method"] is not None
    formula = "logit P(Y=1) = θ_i + α_m + γ_c" + (" + δ_method" if has_method else "")

    lines: list[str] = []
    lines += [
        "# Many-Facet Rasch Model — Binary Depression Judgment",
        "",
        f"**Formula:** `{formula}`  ",
        f"**N observations:** {int(result.nobs)}  ",
        f"**Log-likelihood:** {result.llf:.2f}  ",
        f"**Null deviance:** {result.null_deviance:.2f} | "
        f"**Residual deviance:** {result.deviance:.2f} (df = {int(result.df_resid)})  ",
        f"**McFadden R²:** {1 - result.llf / (result.null_deviance / -2):.3f}",
        "",
    ]

    facet_order = [
        ("alpha (model severity bias)", "α — Model Severity Bias", ref["model"]),
        ("gamma (condition bias)",       "γ — Input-Condition Bias", ref["condition"]),
        ("delta (method bias)",          "δ — Method (Scoring Format) Bias", ref["method"]),
    ]

    for facet_key, header, ref_level in facet_order:
        sub = params[params["facet"] == facet_key]
        if sub.empty:
            continue
        lines += [
            f"## {header}",
            f"*Reference level (fixed at 0): `{ref_level}`*",
            "",
            "| Level | Estimate [95% CI] | SE | z | p | |",
            "|-------|-------------------|----|----|---|--|",
        ]
        for _, row in sub.iterrows():
            stars = _sig_stars(row["p"])
            lines.append(
                f"| {row['level']} | {row['estimate']:+.3f} [{row['ci_lower']:+.3f}, {row['ci_upper']:+.3f}]"
                f" | {row['se']:.3f} | {row['z']:.2f} | {row['p']:.4f} | {stars} |"
            )
        lines += ["", f"*95 % CI shown in parentheses; computed from SE.*", ""]

    # Interview severity section
    top5 = theta.nlargest(5)
    bot5 = theta.nsmallest(5)
    lines += [
        "## θ — Interview Severity",
        f"*{len(theta)} interviews; reference interview: `{ref['interview']}` (fixed at 0)*",
        "",
        f"| Statistic | Value |",
        f"|-----------|-------|",
        f"| Range | [{theta.min():.3f}, {theta.max():.3f}] |",
        f"| Mean  | {theta.mean():.3f} |",
        f"| SD    | {theta.std():.3f} |",
        "",
        "**5 highest-severity interviews:**",
        "",
        "| Interview | θ̂ |",
        "|-----------|-----|",
    ]
    for k, v in top5.items():
        lines.append(f"| {k} | {v:+.3f} |")
    lines += [
        "",
        "**5 lowest-severity interviews:**",
        "",
        "| Interview | θ̂ |",
        "|-----------|-----|",
    ]
    for k, v in bot5.items():
        lines.append(f"| {k} | {v:+.3f} |")

    lines += [
        "",
        "---",
        "*Significance codes: \\*\\*\\* p<.001 · \\*\\* p<.01 · \\* p<.05 · . p<.10*",
    ]
    return "\n".join(lines)


def print_facet_summary(mfrm: dict) -> None:
    """Print a compact facet-level summary of the fitted MFRM."""
    result = mfrm["result"]
    ref = mfrm["reference"]

    print("=" * 72)
    print("Many-Facet Rasch Model — binary depression judgment")
    print("logit P(Y=1) = θ_i + α_m + γ_c" +
          (" + δ_method" if ref["method"] is not None else ""))
    print(f"N observations : {int(result.nobs)}")
    print(f"Log-likelihood : {result.llf:.2f}   Null deviance: {result.null_deviance:.2f}")
    print(f"Residual dev.  : {result.deviance:.2f}   df: {int(result.df_resid)}")
    print()

    # Print each non-intercept facet group
    params = mfrm["params"]
    facet_order = [
        ("alpha (model severity bias)", "α — Model severity bias", ref["model"]),
        ("gamma (condition bias)", "γ — Condition bias", ref["condition"]),
        ("delta (method bias)", "δ — Method bias", ref["method"]),
    ]

    for facet_key, header, ref_level in facet_order:
        sub = params[params["facet"] == facet_key]
        if sub.empty:
            continue
        print(header + f"  [ref: {ref_level} = 0]")
        print(f"  {'Level':<40} {'Est':>7} {'SE':>6} {'z':>7} {'p':>8}")
        print(f"  {'-'*40} {'-'*7} {'-'*6} {'-'*7} {'-'*8}")
        for _, row in sub.iterrows():
            stars = _sig_stars(row["p"])
            print(f"  {row['level']:<40} {row['estimate']:>7.3f} {row['se']:>6.3f}"
                  f" {row['z']:>7.2f} {row['p']:>8.4f} {stars}")
        print()

    # Interview severity distribution
    theta = mfrm["theta"]
    print(f"θ — Interview severity  [{len(theta)} interviews, ref={ref['interview']}]")
    print(f"  Range  : [{theta.min():.3f}, {theta.max():.3f}]")
    print(f"  Mean   : {theta.mean():.3f}   SD: {theta.std():.3f}")
    # Top and bottom 5 by severity
    top5 = theta.nlargest(5)
    bot5 = theta.nsmallest(5)
    print(f"  Highest severity interviews: "
          + ", ".join(f"{k}({v:+.2f})" for k, v in top5.items()))
    print(f"  Lowest  severity interviews: "
          + ", ".join(f"{k}({v:+.2f})" for k, v in bot5.items()))
    print()
    print("Signif. codes: *** p<.001  ** p<.01  * p<.05  . p<.10")
    print("=" * 72)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fit a many-facet Rasch model to binary LLM depression judgments."
    )
    parser.add_argument(
        "--analysis-dir", type=Path, default=DEFAULT_ANALYSIS_DIR,
        help="Directory containing *_outputs.csv files.",
    )
    parser.add_argument(
        "--method", choices=["item", "global", "both"], default="both",
        help="Which binary outcome(s) to include (default: both).",
    )
    parser.add_argument(
        "--drop-interviewer-only", type=lambda x: x.lower() != "false", default=True,
        metavar="BOOL",
        help="Exclude interviewer_only condition rows (default: true).",
    )
    parser.add_argument("--ref-interview", default=None, help="Reference interview_id.")
    parser.add_argument("--ref-model", default=None, help="Reference model name.")
    parser.add_argument("--ref-condition", default=None, help="Reference full_condition.")
    parser.add_argument(
        "--ref-method", choices=["item", "global"], default=None,
        help="Reference method level when --method both.",
    )
    parser.add_argument(
        "--report", type=Path, default=None, metavar="PATH",
        help="Save a markdown report to this path (e.g. outputs/mfrm_report.md).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    include = ("item", "global") if args.method == "both" else (args.method,)

    mfrm = fit_many_facet_rasch(
        analysis_dir=args.analysis_dir,
        include_methods=include,
        reference_interview=args.ref_interview,
        reference_model=args.ref_model,
        reference_condition=args.ref_condition,
        reference_method=args.ref_method,
        drop_interviewer_only=args.drop_interviewer_only,
    )

    print_facet_summary(mfrm)

    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(build_markdown_report(mfrm), encoding="utf-8")
        print(f"\nReport saved → {args.report}")


if __name__ == "__main__":
    main()
