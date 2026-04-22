"""Category taxonomy for personal finance.

17 categories covering the typical Ugandan mobile money spending profile.

Note on SELF_TRANSFER: mobile money is often used as a pass-through between
a user's own accounts (e.g., Airtel -> SC Bank, bank -> URA tax payment).
These transactions must NOT be counted as spending in analytics, so they
get their own category.
"""
from enum import Enum


class Category(str, Enum):
    FAMILY_SENT = "family_sent"
    FAMILY_RECEIVED = "family_received"
    RENT_HOUSING = "rent_housing"
    UTILITIES = "utilities"
    AIRTIME_BUNDLES = "airtime_bundles"
    TRANSPORT = "transport"
    GROCERIES_FOOD = "groceries_food"
    DINING_ENTERTAINMENT = "dining_entertainment"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    SAVINGS_INVESTMENTS = "savings_investments"
    LOAN_CREDIT = "loan_credit"
    CASH_WITHDRAWAL = "cash_withdrawal"
    CASH_DEPOSIT = "cash_deposit"
    FEES_CHARGES = "fees_charges"
    SELF_TRANSFER = "self_transfer"
    OTHER = "other"


CATEGORY_DESCRIPTIONS: dict[Category, str] = {
    Category.FAMILY_SENT: "Money sent to family members or close friends (non-commercial).",
    Category.FAMILY_RECEIVED: "Money received from family members or close friends.",
    Category.RENT_HOUSING: "Rent payments and housing-related expenses.",
    Category.UTILITIES: "UMEME (electricity), NWSC (water), internet, DSTV, garbage.",
    Category.AIRTIME_BUNDLES: "Airtime top-ups and data/voice bundles.",
    Category.TRANSPORT: "Fuel, boda, SafeBoda, Uber, Bolt, taxi, bus fares.",
    Category.GROCERIES_FOOD: "Supermarket, market, and grocery purchases.",
    Category.DINING_ENTERTAINMENT: "Restaurants, bars, events, streaming services.",
    Category.HEALTHCARE: "Hospitals, clinics, pharmacies, health insurance.",
    Category.EDUCATION: "School fees, tuition, books, training programs.",
    Category.SAVINGS_INVESTMENTS: "MoKash savings, SACCOs, investment platforms.",
    Category.LOAN_CREDIT: "Loans borrowed or repaid (MoKash, Wewole, etc.).",
    Category.CASH_WITHDRAWAL: "Cash withdrawn from an agent or ATM.",
    Category.CASH_DEPOSIT: "Cash deposited via an agent (not from your own bank).",
    Category.FEES_CHARGES: "Telco transaction fees, taxes (excise duty).",
    Category.SELF_TRANSFER: (
        "Pass-through transfers between the user's own accounts: "
        "deposits from their own bank, payments to URA/tax, transfers back to bank. "
        "NOT real spending or income — excluded from spend/income analytics."
    ),
    Category.OTHER: "Anything that doesn't clearly fit another category.",
}
