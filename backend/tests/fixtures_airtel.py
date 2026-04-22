"""Fixture: real Airtel Money messages from the user's export, annotated with
expected parser outputs.

Each entry is (message, expected_dict_or_None).
- expected_dict: partial dict of fields we assert on
- None: message should be SKIPPED (OTP, FAILED)
- "FAIL": regex should miss; used to pin the LLM fallback cases

Keep this file pristine — it's the source of truth for parser correctness.
When new message templates appear in future exports, add them here first.
"""
from decimal import Decimal

from app.schemas.transaction import Direction, Network, ParseMethod, TransactionType


# Each expected dict only lists fields we care about asserting on.
FIXTURES: list[tuple[str, object]] = [
    # --- CASH DEPOSIT ---
    (
        "CASH DEPOSIT of UGX 200,000 from  SC BANK SC BANK. Bal UGX 228,702. TID 142853569804. 15-March-2026 02:01",
        dict(
            type=TransactionType.DEPOSIT,
            direction=Direction.IN,
            amount=Decimal("200000"),
            counterparty_name="SC BANK",
            balance_after=Decimal("228702"),
            transaction_id="142853569804",
            network=Network.AIRTEL,
            parse_method=ParseMethod.REGEX,
        ),
    ),
    (
        "CASH DEPOSIT of UGX 70,000 from  MTN MOBILE MONEY UGANDA LTD. Bal UGX 123,702. TID 143480461088. 23-March-2026 18:25",
        dict(
            type=TransactionType.DEPOSIT,
            direction=Direction.IN,
            amount=Decimal("70000"),
            counterparty_name="MTN MOBILE MONEY UGANDA LTD",
            balance_after=Decimal("123702"),
            transaction_id="143480461088",
        ),
    ),
    (
        "CASH DEPOSIT of UGX 5,000,000 from  Bonna Gyaviira Morgan Bonna Gyaviira Morgan. Bal UGX 5,025,112. TID 142097994755. 04-March-2026 18:18",
        dict(
            type=TransactionType.DEPOSIT,
            direction=Direction.IN,
            amount=Decimal("5000000"),
            counterparty_name="Bonna Gyaviira Morgan",   # doubled name deduped
            balance_after=Decimal("5025112"),
        ),
    ),

    # --- PAID (merchant / bill) ---
    (
        "PAID.TID 142853590171. UGX 179,000 to LA GATOS SERVICES LTD Charge UGX 0. Bal UGX 49,702. 15-March-2026 02:04",
        dict(
            type=TransactionType.BILL_PAYMENT,
            direction=Direction.OUT,
            amount=Decimal("179000"),
            counterparty_name="LA GATOS SERVICES LTD",
            fee=Decimal("0"),
            balance_after=Decimal("49702"),
            transaction_id="142853590171",
        ),
    ),
    (
        "PAID.TID 143018891189. UGX 50,000 to Data bundle  Mobile App Charge UGX 0. Bal UGX 49,702. 17-March-2026 12:37",
        dict(
            type=TransactionType.BUNDLE,   # auto-detected from 'bundle' keyword
            direction=Direction.OUT,
            amount=Decimal("50000"),
            counterparty_name="Data bundle  Mobile App",
            balance_after=Decimal("49702"),
        ),
    ),
    (
        "PAID.TID 145070291446. UGX 310,000 to URA STANBIC BANK U LTD Charge UGX 5,050. Bal UGX 11,202. 15-April-2026 06:19",
        dict(
            type=TransactionType.BILL_PAYMENT,
            direction=Direction.OUT,
            amount=Decimal("310000"),
            counterparty_name="URA STANBIC BANK U LTD",
            fee=Decimal("5050"),
        ),
    ),
    (
        "PAID.TID 142148748177. UGX 500,460 to GUARANTY TRUST BANK UGANDA LTD Charge UGX 6,150. Bal UGX 5,473,002. 05-March-2026 13:16",
        dict(
            type=TransactionType.BILL_PAYMENT,
            amount=Decimal("500460"),
            counterparty_name="GUARANTY TRUST BANK UGANDA LTD",
            fee=Decimal("6150"),
        ),
    ),
    (
        "PAID.TID 142210017007. UGX 5,000,000 to SC Bank Charge UGX 11,300. Bal UGX 461,702. 06-March-2026 11:12",
        dict(
            type=TransactionType.BILL_PAYMENT,
            amount=Decimal("5000000"),
            counterparty_name="SC Bank",
            fee=Decimal("11300"),
        ),
    ),
    (
        "PAID.TID 144860121533. UGX 110,000 to QUIDEXPLUS UGANDA LIMITED Charge UGX 950. Bal UGX 41,252. 12-April-2026 06:34",
        dict(
            type=TransactionType.BILL_PAYMENT,
            amount=Decimal("110000"),
            counterparty_name="QUIDEXPLUS UGANDA LIMITED",
            fee=Decimal("950"),
        ),
    ),
    (
        "PAID.TID 142648252270. UGX 50,000 to Bundles Mobile APP Charge UGX 0. Bal UGX 110,702. 12-March-2026 10:57",
        dict(
            type=TransactionType.BUNDLE,
            amount=Decimal("50000"),
            counterparty_name="Bundles Mobile APP",
        ),
    ),

    # --- SENT (P2P) ---
    (
        "SENT.TID 142103669037. UGX 45,000 to JOEL AKUMA  0740204439. Fee UGX 500. Bal UGX 5,979,612. Date 04-March-2026 19:18.",
        dict(
            type=TransactionType.SENT,
            direction=Direction.OUT,
            amount=Decimal("45000"),
            counterparty_name="JOEL AKUMA",
            counterparty_number="0740204439",
            fee=Decimal("500"),
            balance_after=Decimal("5979612"),
            transaction_id="142103669037",
        ),
    ),
    (
        "SENT.TID 143387638450. UGX 100,000 to Charles Twongyere  0702379275. Fee UGX 1,000. Bal UGX 129,702. Date 22-March-2026 12:37.",
        dict(
            type=TransactionType.SENT,
            amount=Decimal("100000"),
            counterparty_name="Charles Twongyere",
            counterparty_number="0702379275",
            fee=Decimal("1000"),
        ),
    ),
    (
        "SENT.TID 143874301281. UGX 50,000 to JOEL AKUMA  0740204439. Fee UGX 500. Bal UGX 73,202. Date 29-March-2026 13:44.",
        dict(
            type=TransactionType.SENT,
            amount=Decimal("50000"),
            counterparty_name="JOEL AKUMA",
            counterparty_number="0740204439",
        ),
    ),
    (
        "SENT.TID 144324677440. UGX 50,000 to JOVIA LAIKE  0749910221. Fee UGX 500. Bal UGX 22,702. Date 04-April-2026 17:56.",
        dict(
            type=TransactionType.SENT,
            amount=Decimal("50000"),
            counterparty_name="JOVIA LAIKE",
            counterparty_number="0749910221",
        ),
    ),
    (
        "SENT.TID 144439762724. UGX 20,000 to ISAAC OGWAL  0701323625. Fee UGX 500. Bal UGX 2,202. Date 06-April-2026 09:44.",
        dict(
            type=TransactionType.SENT,
            amount=Decimal("20000"),
            counterparty_name="ISAAC OGWAL",
            counterparty_number="0701323625",
        ),
    ),
    (
        "SENT.TID 142847674619. UGX 100,000 to JOVIA LAIKE  0749910221. Fee UGX 1,000. Bal UGX 28,702. Date 14-March-2026 22:22.",
        dict(
            type=TransactionType.SENT,
            amount=Decimal("100000"),
            counterparty_name="JOVIA LAIKE",
        ),
    ),

    # --- WITHDRAWN (agent cashout) ---
    (
        "WITHDRAWN. TID 143251777870. UGX400,000 with Agent ID: 678447.Fee UGX 7,000.Tax UGX 2,000.Bal UGX 40,702. 20-March-2026 13:33.",
        dict(
            type=TransactionType.WITHDRAW,
            direction=Direction.OUT,
            amount=Decimal("400000"),
            agent_id="678447",
            fee=Decimal("9000"),      # Fee 7000 + Tax 2000 combined
            balance_after=Decimal("40702"),
            transaction_id="143251777870",
        ),
    ),

    # --- DEBITED (app send, no recipient) ---
    (
        "You have been debited UGX 75,000. Fee UGX 1,000. Bal UGX 53,702. TID 143416174774.Send using MyAirtel App https://bit.ly/3ZgpiNw",
        dict(
            type=TransactionType.SENT,
            direction=Direction.OUT,
            amount=Decimal("75000"),
            fee=Decimal("1000"),
            balance_after=Decimal("53702"),
            transaction_id="143416174774",
            counterparty_name=None,
        ),
    ),
    (
        "You have been debited UGX 200,000. Fee UGX 1,000. Bal UGX 160,702. TID 142648183545.Send using MyAirtel App https://bit.ly/3ZgpiNw",
        dict(
            type=TransactionType.SENT,
            amount=Decimal("200000"),
            transaction_id="142648183545",
        ),
    ),
    (
        "You have been debited UGX 100,000. Fee UGX 1,000. Bal UGX 9,702. TID 142662756014.Send using MyAirtel App https://bit.ly/3ZgpiNw",
        dict(
            type=TransactionType.SENT,
            amount=Decimal("100000"),
            transaction_id="142662756014",
        ),
    ),

    # --- Airtime outgoing ---
    (
        "Top up of UGX 10,000 for 0758152159. Bal : UGX 30,702.",
        dict(
            type=TransactionType.AIRTIME,
            direction=Direction.OUT,
            amount=Decimal("10000"),
            counterparty_number="0758152159",
            balance_after=Decimal("30702"),
        ),
    ),

    # --- Airtime incoming ---
    (
        "You have received Airtime Topup of UGX 3,000 from ELVIN ISAAC. Dial *185# for more AirtelMoney transactions.",
        dict(
            type=TransactionType.AIRTIME,
            direction=Direction.IN,
            amount=Decimal("3000"),
            counterparty_name="ELVIN ISAAC",
        ),
    ),

    # --- SKIPPED: OTP notices ---
    (
        "Withdrawal of UGX 400000 initiated. Secret Code: 189037. Expires on 20-March-2026 13:35.",
        None,
    ),

    # --- SKIPPED: FAILED transactions ---
    (
        "FAILED. TID 142209904941 Amount entered is not within the allowed range. Please enter the correct amount.",
        None,
    ),
]
