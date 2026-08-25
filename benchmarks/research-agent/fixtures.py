"""Deterministic fixture data (spec §41).

The benchmark does not require live web APIs -- reproducibility matters more
than realism here, because the number being measured is *reuse*, not accuracy.

Each source is versioned. Bumping a version is what the scenarios do to
simulate the world changing:

``financials_source``
    ``v1 -> v2`` changes the underlying figures.
    ``v2 -> v3`` changes the *raw* payload only -- different field order, a
    renamed key, values in thousands instead of millions -- and normalizes back
    to a byte-identical structured object. That is scenario E (§46), the one
    that proves propagation is driven by output hashes rather than by
    dependency versions.
"""

from __future__ import annotations

from typing import Any

TICKER = "NVDA"

# --------------------------------------------------------------------------
# company profile -- unversioned, changes only if the ticker changes
# --------------------------------------------------------------------------

PROFILE: dict[str, Any] = {
    "ticker": "NVDA",
    "name": "NVIDIA Corporation",
    "sector": "Information Technology",
    "industry": "Semiconductors",
    "headquarters": "Santa Clara, California",
    "employees": 29600,
    "description": (
        "Designs graphics processing units, systems on a chip, and accelerated "
        "computing platforms for gaming, data centre, professional "
        "visualisation and automotive markets."
    ),
    "segments": [
        {
            "name": "Data Centre",
            "detail": (
                "Accelerated computing platforms sold to hyperscale cloud "
                "providers, enterprises and national laboratories. Revenue is "
                "concentrated among a small number of very large customers, and "
                "purchasing is lumpy: a single hyperscaler capacity commitment "
                "can move a quarter materially. Competitive position rests on "
                "the software ecosystem as much as on silicon, since migration "
                "costs for existing training and inference pipelines are high."
            ),
        },
        {
            "name": "Gaming",
            "detail": (
                "Discrete graphics cards sold through add-in-board partners and "
                "integrated into laptops. Demand is seasonal and correlates with "
                "console cycles and title releases. Margins are structurally "
                "below the data centre segment, and channel inventory has "
                "historically been the main source of forecast error."
            ),
        },
        {
            "name": "Professional Visualisation",
            "detail": (
                "Workstation graphics and simulation platforms for design, "
                "media and scientific workloads. Smaller and slower growing than "
                "the other segments, with revenue tied to enterprise refresh "
                "cycles rather than to model training demand."
            ),
        },
        {
            "name": "Automotive",
            "detail": (
                "In-vehicle compute platforms and the associated toolchain for "
                "assisted and autonomous driving. Design wins convert to revenue "
                "over multi-year programme timelines, so reported figures lag "
                "commercial momentum by several quarters."
            ),
        },
    ],
}

# --------------------------------------------------------------------------
# financials -- three raw source versions, two distinct normalized outputs
# --------------------------------------------------------------------------

_FINANCIALS_RAW: dict[str, dict[str, Any]] = {
    # v1 and v2 differ in the actual numbers.
    "v1": {
        "fiscal_year": "FY2025",
        "currency": "USD",
        "unit": "millions",
        "revenue": 130_497,
        "gross_profit": 97_858,
        "operating_income": 81_453,
        "net_income": 72_880,
        "total_assets": 111_601,
        "total_debt": 8_463,
        "shares_outstanding": 24_400,
    },
    "v2": {
        "fiscal_year": "FY2025",
        "currency": "USD",
        "unit": "millions",
        "revenue": 148_512,
        "gross_profit": 111_384,
        "operating_income": 94_207,
        "net_income": 84_119,
        "total_assets": 128_940,
        "total_debt": 8_102,
        "shares_outstanding": 24_350,
    },
    # v3 is v2 restated: keys reordered, one renamed, figures in thousands.
    # Normalization must collapse it back to exactly the v2 structured object.
    "v3": {
        "shares_outstanding": 24_350_000,
        "unit": "thousands",
        "net_earnings": 84_119_000,  # renamed from net_income
        "total_debt": 8_102_000,
        "revenue": 148_512_000,
        "currency": "USD",
        "total_assets": 128_940_000,
        "operating_income": 94_207_000,
        "gross_profit": 111_384_000,
        "fiscal_year": "FY2025",
        "restatement_note": "reported in thousands per filing amendment",
    },
}

_UNIT_TO_MILLIONS = {"millions": 1, "thousands": 1_000, "units": 1_000_000}

#: Management discussion accompanying the FY2025 figures. Carried into the
#: normalized object because a financial analysis step reads it. Unchanged by
#: the v3 restatement, which altered units and field names only.
_MD_AND_A = (
    "Revenue growth in the period was driven principally by data centre "
    "demand, where shipments of accelerated computing platforms exceeded "
    "internal forecasts for the third consecutive quarter. Gross margin "
    "expanded on a favourable mix shift toward higher-value configurations, "
    "partially offset by increased provisions for advanced packaging capacity "
    "secured under take-or-pay terms. Operating expenses rose in absolute "
    "terms on headcount growth in software engineering, but declined as a "
    "proportion of revenue. Management notes three sources of uncertainty in "
    "forward guidance: the pace at which packaging capacity comes online, the "
    "concentration of bookings among a small number of hyperscale customers, "
    "and the evolving licensing regime governing exports of advanced "
    "accelerators. Cash generated from operations was reinvested primarily in "
    "supply commitments and in the expansion of the software platform, with "
    "the remainder returned through the existing repurchase authorisation. "
    "The company continues to view the installed software ecosystem as the "
    "principal determinant of competitive position over a multi-year horizon."
)


def financials(version: str) -> dict[str, Any]:
    """Normalize a raw financial payload into the canonical structured object.

    This is the function scenario E leans on: v2 and v3 carry different raw
    bytes and must come out the other side identical.
    """
    raw = _FINANCIALS_RAW[version]
    divisor = _UNIT_TO_MILLIONS[raw["unit"]]

    def to_millions(value: float) -> float:
        return round(value / divisor, 2)

    net_income = raw.get("net_income", raw.get("net_earnings"))

    return {
        "fiscal_year": raw["fiscal_year"],
        "currency": raw["currency"],
        "unit": "millions",
        "revenue": to_millions(raw["revenue"]),
        "gross_profit": to_millions(raw["gross_profit"]),
        "operating_income": to_millions(raw["operating_income"]),
        "net_income": to_millions(net_income),
        "total_assets": to_millions(raw["total_assets"]),
        "total_debt": to_millions(raw["total_debt"]),
        "shares_outstanding": to_millions(raw["shares_outstanding"]),
        "margins": {
            "gross": round(raw["gross_profit"] / raw["revenue"], 4),
            "operating": round(raw["operating_income"] / raw["revenue"], 4),
            "net": round(net_income / raw["revenue"], 4),
        },
        "management_discussion": _MD_AND_A,
    }


# --------------------------------------------------------------------------
# competitors
# --------------------------------------------------------------------------

_COMPETITORS: dict[str, list[dict[str, Any]]] = {
    "v1": [
        {"note": 'Competes across data centre accelerators and client graphics. Has closed much of the hardware gap on paper; adoption is gated less by silicon than by the maturity of the surrounding software stack and by the cost of migrating established training pipelines.',
         "ticker": "AMD", "name": "Advanced Micro Devices", "share": 0.11},
        {"note": 'Pursuing accelerated computing alongside a foundry strategy that absorbs substantial capital. Share in the accelerator segment remains small, and the near-term question is whether process execution improves enough to support the roadmap.',
         "ticker": "INTC", "name": "Intel Corporation", "share": 0.07},
        {"note": 'Supplies custom accelerators designed with individual hyperscalers, plus the networking silicon these clusters depend on. Competes for the same budget without competing directly on merchant parts.',
         "ticker": "AVGO", "name": "Broadcom", "share": 0.09},
        {"note": 'Strong in mobile and edge inference, marginal in the data centre. Relevant mainly as a constraint on how far inference workloads migrate away from centralised infrastructure.',
         "ticker": "QCOM", "name": "Qualcomm", "share": 0.05},
    ],
    "v2": [
        {"note": 'Competes across data centre accelerators and client graphics. Has closed much of the hardware gap on paper; adoption is gated less by silicon than by the maturity of the surrounding software stack and by the cost of migrating established training pipelines.',
         "ticker": "AMD", "name": "Advanced Micro Devices", "share": 0.13},
        {"note": 'Pursuing accelerated computing alongside a foundry strategy that absorbs substantial capital. Share in the accelerator segment remains small, and the near-term question is whether process execution improves enough to support the roadmap.',
         "ticker": "INTC", "name": "Intel Corporation", "share": 0.05},
        {"note": 'Supplies custom accelerators designed with individual hyperscalers, plus the networking silicon these clusters depend on. Competes for the same budget without competing directly on merchant parts.',
         "ticker": "AVGO", "name": "Broadcom", "share": 0.10},
        {"note": 'Strong in mobile and edge inference, marginal in the data centre. Relevant mainly as a constraint on how far inference workloads migrate away from centralised infrastructure.',
         "ticker": "QCOM", "name": "Qualcomm", "share": 0.05},
        {"note": 'Custom silicon and interconnect for cloud infrastructure. Growing from a small base and, like Broadcom, positioned around hyperscaler in-house programmes rather than merchant accelerators.',
         "ticker": "MRVL", "name": "Marvell Technology", "share": 0.03},
    ],
}


def competitors(version: str) -> list[dict[str, Any]]:
    return [dict(entry) for entry in _COMPETITORS[version]]


# --------------------------------------------------------------------------
# news
# --------------------------------------------------------------------------

_NEWS: dict[str, list[dict[str, Any]]] = {
    "v1": [
        {
            "date": "2026-07-14",
            "headline": "Data centre demand lifts quarterly guidance",
            "body": (
                'Management raised guidance for the coming quarter, attributing the revision to sustained ordering from hyperscale customers and to accelerated computing platforms shipping ahead of the internal plan. Analysts on the call pressed for detail on how much of the increase reflects genuine end-demand versus channel build, and management declined to break the figure out, noting only that backlog coverage extends beyond the guided period.'
            ),
            "sentiment": 0.72,
        },
        {
            "date": "2026-07-28",
            "headline": "New accelerator architecture announced at summit",
            "body": (
                'The architecture announced at the developer summit targets a substantial improvement in performance per watt for inference workloads, with the first systems scheduled to ship to cloud partners before general availability. The accompanying software release preserves compatibility with existing training pipelines, which management framed as the point of the release: customers can adopt without rewriting the workloads they already run.'
            ),
            "sentiment": 0.65,
        },
        {
            "date": "2026-08-02",
            "headline": "Supply constraints ease as packaging capacity expands",
            "body": (
                'Additional advanced packaging capacity came online during the quarter, relieving a bottleneck that had constrained shipments for several periods. Supply chain commentary suggests lead times have shortened but remain above historical norms, and the capacity was secured under take-or-pay terms that raise fixed obligations if demand softens.'
            ),
            "sentiment": 0.48,
        },
    ],
    "v2": [
        {
            "date": "2026-07-14",
            "headline": "Data centre demand lifts quarterly guidance",
            "body": (
                'Management raised guidance for the coming quarter, attributing the revision to sustained ordering from hyperscale customers and to accelerated computing platforms shipping ahead of the internal plan. Analysts on the call pressed for detail on how much of the increase reflects genuine end-demand versus channel build, and management declined to break the figure out, noting only that backlog coverage extends beyond the guided period.'
            ),
            "sentiment": 0.72,
        },
        {
            "date": "2026-07-28",
            "headline": "New accelerator architecture announced at summit",
            "body": (
                'The architecture announced at the developer summit targets a substantial improvement in performance per watt for inference workloads, with the first systems scheduled to ship to cloud partners before general availability. The accompanying software release preserves compatibility with existing training pipelines, which management framed as the point of the release: customers can adopt without rewriting the workloads they already run.'
            ),
            "sentiment": 0.65,
        },
        {
            "date": "2026-08-02",
            "headline": "Supply constraints ease as packaging capacity expands",
            "body": (
                'Additional advanced packaging capacity came online during the quarter, relieving a bottleneck that had constrained shipments for several periods. Supply chain commentary suggests lead times have shortened but remain above historical norms, and the capacity was secured under take-or-pay terms that raise fixed obligations if demand softens.'
            ),
            "sentiment": 0.48,
        },
        {
            "date": "2026-08-19",
            "headline": "Regulator opens review of accelerator export licences",
            "body": (
                'A regulatory body opened a review of the licensing regime governing exports of advanced accelerators, requesting submissions from affected manufacturers. No restriction has been proposed and the review carries no fixed timetable, but the announcement introduces uncertainty into revenue attributable to the affected jurisdictions, which the company has previously described as material but not dominant.'
            ),
            "sentiment": -0.41,
        },
        {
            "date": "2026-08-23",
            "headline": "Two hyperscalers disclose multi-year capacity commitments",
            "body": (
                'Two hyperscale operators disclosed multi-year commitments covering accelerated computing capacity, in both cases naming the company as the primary supplier. The disclosures give unusual visibility into a demand picture that is normally opaque, though they also underline how concentrated the customer base is: the two commitments together represent a meaningful share of forward data centre revenue.'
            ),
            "sentiment": 0.81,
        },
    ],
}


def news(version: str) -> list[dict[str, Any]]:
    return [dict(entry) for entry in _NEWS[version]]


def profile(ticker: str) -> dict[str, Any]:
    if ticker != TICKER:
        raise KeyError(f"no fixture for {ticker!r}; this benchmark covers {TICKER}")
    return dict(PROFILE)
