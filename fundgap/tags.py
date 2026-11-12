"""Candidate XBRL tags (RULE.md sections 2.2 and 2.3).

Companies label the same cash-flow line with different tags, so we list the
candidates here and record the tag each company actually uses in
data/tag_map.csv, with the reason.
"""

OCF_TAGS = [
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
]

CAPEX_TAGS = [
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsToAcquireProductiveAssets",
    "PaymentsToAcquireOilAndGasPropertyAndEquipment",
    "PaymentsToExploreAndDevelopOilAndGasProperties",
    "PaymentsToAcquireOilAndGasProperty",
    "PaymentsToAcquireOtherPropertyPlantAndEquipment",
]

# Not capex under RULE.md, but reported alongside it as descriptive context.
FINANCE_LEASE_TAGS = [
    "FinanceLeasePrincipalPayments",
    "RepaymentsOfLongTermCapitalLeaseObligations",
]

# Used for the RULE.md 2.3 sanity check (capex must not exceed investing outflows).
INVESTING_TAG = "NetCashProvidedByUsedInInvestingActivities"
