#!/usr/bin/env python3
"""Generalizability Theory for binary depression judgments.

G-study design: p × m × c  (persons × models × conditions) — fully crossed, all random.
  p = interview / person  (object of measurement)
  m = AI model / judge    (random facet)
  c = input condition     (random facet)

Method (item vs global) is a fixed facet — run separately via --method.

D-study: sweeps n_m', n_c' to find which design maximises
  Phi (Φ) — absolute dependability, for cut-score decisions.
  G   (ρ²) — relative dependability, for ranking persons.

Variance components estimated via EMS equations on the balanced 3-way ANOVA.

Usage
-----
    python scripts/fit_gtheory.py
    python scripts/fit_gtheory.py --method global
    python scripts/fit_gtheory.py --report outputs/gtheory_report.md
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ANALYSIS_DIR = PROJECT_DIR / "outputs" / "analysis"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_analysis_csvs(analysis_dir: Path) -> pd.DataFrame:
    frames = []
    for path in sorted(analysis_dir.glob("*_outputs.csv")):
        with path.open(newline="", encoding="utf-8") as f:
            frames.append(pd.DataFrame(list(csv.DictReader(f))))
    if not frames:
        raise FileNotFoundError(f"No *_outputs.csv found in {analysis_dir}")
    df = pd.concat(frames, ignore_index=True)
    return df.drop_duplicates(
        subset=["interview_id", "model_name", "condition", "metadata_condition"]
    )


def build_long_frame(df: pd.DataFrame, method: str,
                     drop_interviewer_only: bool = True) -> pd.DataFrame:
    col = {"item": "thresholded_item_binary",
           "global": "global_binary_judgment"}[method]
    sub = df[["interview_id", "model_name", "condition",
               "metadata_condition", col]].copy()
    sub = sub.rename(columns={col: "Y"})
    sub["full_condition"] = sub["metadata_condition"] + "_" + sub["condition"]
    if drop_interviewer_only:
        sub = sub[~sub["full_condition"].str.contains("interviewer_only")].copy()
    sub["Y"] = sub["Y"].astype(float)
    return sub[["interview_id", "model_name", "full_condition", "Y"]]


# ---------------------------------------------------------------------------
# G-study: balanced 3-way ANOVA → variance components
# ---------------------------------------------------------------------------

def compute_anova_ms(
    data: pd.DataFrame,
    p_col: str = "interview_id",
    m_col: str = "model_name",
    c_col: str = "full_condition",
    y_col: str = "Y",
) -> dict:
    """Balanced 3-way crossed ANOVA; returns MS for each source."""
    d = data.copy()
    n_p = d[p_col].nunique()
    n_m = d[m_col].nunique()
    n_c = d[c_col].nunique()

    d["mu"]  = d[y_col].mean()
    d["yp"]  = d.groupby(p_col)[y_col].transform("mean")
    d["ym"]  = d.groupby(m_col)[y_col].transform("mean")
    d["yc"]  = d.groupby(c_col)[y_col].transform("mean")
    d["ypm"] = d.groupby([p_col, m_col])[y_col].transform("mean")
    d["ypc"] = d.groupby([p_col, c_col])[y_col].transform("mean")
    d["ymc"] = d.groupby([m_col, c_col])[y_col].transform("mean")

    SS = {
        "p":   ((d["yp"]  - d["mu"]) ** 2).sum(),
        "m":   ((d["ym"]  - d["mu"]) ** 2).sum(),
        "c":   ((d["yc"]  - d["mu"]) ** 2).sum(),
        "pm":  ((d["ypm"] - d["yp"]  - d["ym"] + d["mu"]) ** 2).sum(),
        "pc":  ((d["ypc"] - d["yp"]  - d["yc"] + d["mu"]) ** 2).sum(),
        "mc":  ((d["ymc"] - d["ym"]  - d["yc"] + d["mu"]) ** 2).sum(),
        "pmc": ((d[y_col] - d["ypm"] - d["ypc"] - d["ymc"]
                           + d["yp"] + d["ym"]  + d["yc"] - d["mu"]) ** 2).sum(),
    }
    df_ = {
        "p":   n_p - 1,
        "m":   n_m - 1,
        "c":   n_c - 1,
        "pm":  (n_p - 1) * (n_m - 1),
        "pc":  (n_p - 1) * (n_c - 1),
        "mc":  (n_m - 1) * (n_c - 1),
        "pmc": (n_p - 1) * (n_m - 1) * (n_c - 1),
    }
    MS = {k: SS[k] / df_[k] for k in SS}
    return {"SS": SS, "df": df_, "MS": MS, "n": {"p": n_p, "m": n_m, "c": n_c}}


def estimate_variance_components(anova: dict) -> dict:
    """Solve EMS equations for balanced p × m × c random effects design.

    Sources and their Expected Mean Squares (Brennan 2001):
      E[MS_pmc] = σ²_pmc
      E[MS_mc]  = σ²_pmc + n_p · σ²_mc
      E[MS_pc]  = σ²_pmc + n_m · σ²_pc
      E[MS_pm]  = σ²_pmc + n_c · σ²_pm
      E[MS_c]   = σ²_pmc + n_p·σ²_mc + n_m·σ²_pc + n_p·n_m·σ²_c
      E[MS_m]   = σ²_pmc + n_p·σ²_mc + n_c·σ²_pm + n_p·n_c·σ²_m
      E[MS_p]   = σ²_pmc + n_c·σ²_pm + n_m·σ²_pc + n_m·n_c·σ²_p
    """
    MS = anova["MS"]
    n_p, n_m, n_c = anova["n"]["p"], anova["n"]["m"], anova["n"]["c"]

    raw = {
        "pmc(e)": MS["pmc"],
        "mc":     (MS["mc"] - MS["pmc"]) / n_p,
        "pc":     (MS["pc"] - MS["pmc"]) / n_m,
        "pm":     (MS["pm"] - MS["pmc"]) / n_c,
        "c":      (MS["c"]  - MS["mc"] - MS["pc"] + MS["pmc"]) / (n_p * n_m),
        "m":      (MS["m"]  - MS["mc"] - MS["pm"] + MS["pmc"]) / (n_p * n_c),
        "p":      (MS["p"]  - MS["pm"] - MS["pc"] + MS["pmc"]) / (n_m * n_c),
    }
    vc = {k: max(0.0, v) for k, v in raw.items()}
    vc["total"] = sum(vc.values())
    vc["_raw"] = raw  # keep raw (possibly negative) estimates for diagnostics
    return vc


# ---------------------------------------------------------------------------
# D-study
# ---------------------------------------------------------------------------

def d_study(vc: dict,
            n_m_vals: tuple = (1, 2, 3),
            n_c_vals: tuple = (1, 2, 3, 4)) -> pd.DataFrame:
    """Compute Phi (absolute) and G (relative) for all n_m', n_c' combos.

    Absolute error variance (Phi — cut-score decisions):
      σ²_Δ = σ²_m/n_m + σ²_c/n_c + σ²_mc/(n_m·n_c)
             + σ²_pm/n_m + σ²_pc/n_c + σ²_pmc/(n_m·n_c)

    Relative error variance (G — rank-order decisions):
      σ²_δ = σ²_pm/n_m + σ²_pc/n_c + σ²_pmc/(n_m·n_c)
    """
    rows = []
    for n_m in n_m_vals:
        for n_c in n_c_vals:
            s2_delta = (
                vc["m"]      / n_m
                + vc["c"]      / n_c
                + vc["mc"]     / (n_m * n_c)
                + vc["pm"]     / n_m
                + vc["pc"]     / n_c
                + vc["pmc(e)"] / (n_m * n_c)
            )
            s2_rel = (
                vc["pm"]     / n_m
                + vc["pc"]     / n_c
                + vc["pmc(e)"] / (n_m * n_c)
            )
            s2p = vc["p"]
            rows.append({
                "n_models":     n_m,
                "n_conditions": n_c,
                "Phi":          s2p / (s2p + s2_delta) if (s2p + s2_delta) > 0 else 0.0,
                "G":            s2p / (s2p + s2_rel)   if (s2p + s2_rel)   > 0 else 0.0,
                "sigma2_delta": s2_delta,
                "sigma2_rel":   s2_rel,
            })
    return pd.DataFrame(rows)


def run_gtheory(analysis_dir: Path, method: str,
                drop_interviewer_only: bool = True) -> dict:
    df   = load_analysis_csvs(analysis_dir)
    long = build_long_frame(df, method=method,
                            drop_interviewer_only=drop_interviewer_only)
    anova = compute_anova_ms(long)
    vc    = estimate_variance_components(anova)
    ds    = d_study(vc)
    return {"anova": anova, "vc": vc, "d_study": ds, "method": method}


# ---------------------------------------------------------------------------
# Terminal reporting
# ---------------------------------------------------------------------------

def _best_design(ds: pd.DataFrame, threshold: float = 0.80) -> str:
    good = ds[ds["Phi"] >= threshold].sort_values(
        ["n_models", "n_conditions"]
    )
    if not good.empty:
        r = good.iloc[0]
        return (f"{int(r['n_models'])} model(s) × {int(r['n_conditions'])} condition(s) "
                f"→ Φ = {r['Phi']:.3f}")
    r = ds.sort_values("Phi", ascending=False).iloc[0]
    return (f"No design achieves Φ ≥ {threshold:.2f}. "
            f"Best: {int(r['n_models'])} model(s) × {int(r['n_conditions'])} condition(s) "
            f"→ Φ = {r['Phi']:.3f}")


def print_gtheory_report(gt: dict) -> None:
    vc    = gt["vc"]
    ds    = gt["d_study"]
    n     = gt["anova"]["n"]
    total = vc["total"]

    print("=" * 72)
    print(f"G-Theory  p × m × c   method='{gt['method']}'")
    print(f"  {n['p']} persons × {n['m']} models × {n['c']} conditions  "
          f"(N = {n['p']*n['m']*n['c']})")
    print()

    labels = {
        "p":      "p  (universe score)",
        "m":      "m  (model/judge)",
        "c":      "c  (condition)",
        "pm":     "p×m interaction",
        "pc":     "p×c interaction",
        "mc":     "m×c interaction",
        "pmc(e)": "pmc+e (residual)",
    }
    print(f"  {'Source':<24} {'σ²':>9}  {'%Total':>7}")
    print(f"  {'-'*24} {'-'*9}  {'-'*7}")
    for k, lbl in labels.items():
        pct = 100 * vc[k] / total if total > 0 else 0
        neg = "*" if gt["vc"]["_raw"][k] < 0 else " "
        print(f"  {lbl:<24} {vc[k]:>9.5f}{neg}  {pct:>6.1f}%")
    print(f"  {'Total':<24} {total:>9.5f}")
    print(f"  * clamped to 0 (negative raw estimate)")
    print()

    conds  = sorted(ds["n_conditions"].unique())
    models = sorted(ds["n_models"].unique())
    piv_phi = ds.pivot(index="n_models", columns="n_conditions", values="Phi")
    piv_g   = ds.pivot(index="n_models", columns="n_conditions", values="G")

    for label, piv in [("Phi (absolute)", piv_phi), ("G   (relative)", piv_g)]:
        print(f"  D-study — {label}")
        corner = "n_m\\n_c"
        hdr = f"  {corner:<10}" + "".join(f"  c={c}" for c in conds)
        print(hdr)
        print(f"  {'-'*10}" + "  ----" * len(conds))
        for nm in models:
            row = f"  m={nm:<9}" + "".join(f"  {piv.loc[nm, nc]:.3f}" for nc in conds)
            print(row)
        print()

    print(f"  Best design (Φ ≥ 0.80): {_best_design(ds)}")
    print("=" * 72)
    print()


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def build_markdown_report(results: dict) -> str:
    lines = [
        "# Generalizability Theory — Binary Depression Judgment",
        "",
        "**G-study design:** p × m × c (persons × models × conditions), fully crossed, all random.",
        "",
        "| Symbol | Meaning |",
        "|--------|---------|",
        "| Φ (phi) | Absolute dependability — for cut-score decisions (depressed vs not) |",
        "| G (ρ²) | Relative dependability — for ranking interviews by severity |",
        "| σ²_p | Universe-score variance (true between-person differences) |",
        "| σ²_Δ | Absolute error variance (everything that isn't σ²_p) |",
        "",
        "**Threshold:** Φ ≥ 0.80 is the conventional minimum for clinical measurement.",
        "",
        "---",
        "",
    ]

    for method, gt in results.items():
        vc    = gt["vc"]
        ds    = gt["d_study"]
        n     = gt["anova"]["n"]
        total = vc["total"]

        conds  = sorted(ds["n_conditions"].unique())
        models = sorted(ds["n_models"].unique())
        piv_phi = ds.pivot(index="n_models", columns="n_conditions", values="Phi")
        piv_g   = ds.pivot(index="n_models", columns="n_conditions", values="G")

        col_header = " | ".join(f"c={c}" for c in conds)
        col_sep    = " | ".join(["---"] * len(conds))

        lines += [
            f"## Method: `{method}`",
            f"*{n['p']} persons × {n['m']} models × {n['c']} conditions "
            f"(N = {n['p']*n['m']*n['c']})*",
            "",
            "### Variance Components (G-study)",
            "",
            "| Source | σ² | % Total | Note |",
            "|--------|----|---------|------|",
        ]
        labels = {
            "p":      "p — universe score",
            "m":      "m — model/judge",
            "c":      "c — condition",
            "pm":     "p×m",
            "pc":     "p×c",
            "mc":     "m×c",
            "pmc(e)": "pmc+e (residual)",
        }
        for k, lbl in labels.items():
            pct  = 100 * vc[k] / total if total > 0 else 0
            note = "clamped" if vc["_raw"][k] < 0 else ""
            lines.append(f"| {lbl} | {vc[k]:.5f} | {pct:.1f}% | {note} |")
        lines += [
            f"| **Total** | **{total:.5f}** | 100% | |",
            "",
        ]

        lines += [
            "### D-study — Φ (Absolute Dependability)",
            "",
            f"| n\\_models \\ n\\_cond | {col_header} |",
            f"|---|{col_sep}|",
        ]
        for nm in models:
            vals = " | ".join(f"**{piv_phi.loc[nm, nc]:.3f}**"
                              if piv_phi.loc[nm, nc] >= 0.80
                              else f"{piv_phi.loc[nm, nc]:.3f}"
                              for nc in conds)
            lines.append(f"| m={nm} | {vals} |")
        lines += [""]

        lines += [
            "### D-study — G (Relative Dependability)",
            "",
            f"| n\\_models \\ n\\_cond | {col_header} |",
            f"|---|{col_sep}|",
        ]
        for nm in models:
            vals = " | ".join(f"**{piv_g.loc[nm, nc]:.3f}**"
                              if piv_g.loc[nm, nc] >= 0.80
                              else f"{piv_g.loc[nm, nc]:.3f}"
                              for nc in conds)
            lines.append(f"| m={nm} | {vals} |")
        lines += [""]

        lines += [
            f"**Best design (Φ ≥ 0.80):** {_best_design(ds)}",
            "",
            "---",
            "",
        ]

    lines += [
        "## Key Takeaways",
        "",
        "- **σ²_p** is the only variance that counts toward the score; "
          "everything else is error.",
        "- **σ²_m** (model main effect) is error for absolute decisions: "
          "models disagree systematically, so averaging over more models reduces this.",
        "- **σ²_pm** (person × model interaction) is the dominant random error: "
          "models rank persons differently. More models reduce this too.",
        "- **σ²_c** and **σ²_pc** are small (consistent with the MFRM finding "
          "that no condition β was significant), so adding more conditions "
          "yields diminishing returns.",
        "- To maximise Φ cost-effectively: **increase n_m first**, then n_c.",
        "",
        "*Generated by `scripts/fit_gtheory.py`*",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generalizability Theory for binary LLM depression judgments."
    )
    parser.add_argument("--analysis-dir", type=Path, default=DEFAULT_ANALYSIS_DIR)
    parser.add_argument(
        "--method", choices=["item", "global", "both"], default="both",
        help="Scoring method(s) to analyse (default: both).",
    )
    parser.add_argument(
        "--drop-interviewer-only",
        type=lambda x: x.lower() != "false", default=True, metavar="BOOL",
    )
    parser.add_argument(
        "--report", type=Path, default=None, metavar="PATH",
        help="Save markdown report to this path.",
    )
    return parser.parse_args()


def main() -> None:
    args   = parse_args()
    methods = ("item", "global") if args.method == "both" else (args.method,)

    results = {}
    for m in methods:
        results[m] = run_gtheory(
            args.analysis_dir, method=m,
            drop_interviewer_only=args.drop_interviewer_only,
        )
        print_gtheory_report(results[m])

    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(build_markdown_report(results), encoding="utf-8")
        print(f"Report saved → {args.report}")


if __name__ == "__main__":
    main()
