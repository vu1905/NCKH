"""
generate_aw_contracts.py
========================
Generates CUAD-style PDF contracts for each unique AdventureWorks SalesOrderID.
- Party A (Seller):  Adventure Works Cycles, Inc.
- Party B (Buyer):   CustomerDisplayName from AW data
- Uses DejaVuSans Unicode font for full character support.

Output: d:\CUAD\cuad\CUAD_v1\aw_contracts\aw_contract_<SalesOrderNumber>.pdf
Index:  d:\CUAD\cuad\CUAD_v1\aw_contracts\aw_contracts_index.csv
"""

import os, sys, random, textwrap
from datetime import datetime, timedelta
import pandas as pd
from fpdf import FPDF

sys.stdout.reconfigure(encoding="utf-8")

# -- Font paths ---------------------------------------------------------------
FONT_DIR   = r"d:\CUAD\fonts\dejavu-fonts-ttf-2.37\ttf"
FONT_REG   = os.path.join(FONT_DIR, "DejaVuSans.ttf")
FONT_BOLD  = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
FONT_ITAL  = os.path.join(FONT_DIR, "DejaVuSans-Oblique.ttf")
FONT_BOLDITAL = os.path.join(FONT_DIR, "DejaVuSans-BoldOblique.ttf")

# -- Paths --------------------------------------------------------------------
AW_CSV    = r"d:\CUAD\cuad\adventureworks_merged_200.csv"
OUT_DIR   = r"d:\CUAD\cuad\CUAD_v1\aw_contracts"
INDEX_CSV = os.path.join(OUT_DIR, "aw_contracts_index.csv")
os.makedirs(OUT_DIR, exist_ok=True)

# -- CUAD-derived legal templates ---------------------------------------------
GOVERNING_LAWS = [
    "State of Washington", "State of California", "State of New York",
    "Province of Ontario, Canada", "State of Georgia", "State of Texas",
    "Province of British Columbia, Canada", "State of Arizona",
]

PAYMENT_TERMS = [
    "Net 30 days from the date of invoice.",
    "Payment due within 45 days of receipt of goods.",
    "Net 60 days; early payment discount of 2% if paid within 10 days.",
    "50% upon execution; 50% upon delivery and acceptance.",
    "Wire transfer within 30 days of invoice date.",
]

SHIP_CLAUSES = {
    "CARGO TRANSPORT 5": (
        "Delivery shall be made via Cargo Transport 5 freight carrier. "
        "Risk of loss shall transfer to Buyer upon handover to the carrier at Seller's shipping facility."
    ),
    "XRQ - TRUCK GROUND": (
        "Goods shall be shipped ground freight (XRQ Truck Ground). "
        "Buyer assumes risk of loss upon departure from Seller's warehouse."
    ),
    "ZY - EXPRESS": (
        "Delivery shall be performed via ZY Express expedited service. "
        "Seller shall bear cost of shipping; title passes upon delivery to Buyer's designated address."
    ),
    "OVERNIGHT J-FAST": (
        "Overnight delivery via J-Fast courier. Seller is responsible for any shipping damage "
        "until confirmed delivery and signed receipt by Buyer."
    ),
}
DEFAULT_SHIP_CLAUSE = (
    "Goods shall be shipped by the carrier specified in the Purchase Order. "
    "Risk of loss transfers to Buyer upon tender to the carrier."
)

CONFIDENTIALITY_CLAUSE = (
    "Each Party agrees to maintain in strict confidence all Confidential Information received "
    "from the other Party and shall not disclose such information to any third party without "
    "prior written consent, except as required by applicable law or regulation. This obligation "
    "shall survive termination of this Agreement for a period of five (5) years."
)

INDEMNIFICATION_CLAUSE = (
    "Each Party ('Indemnifying Party') shall indemnify, defend, and hold harmless the other "
    "Party and its officers, directors, employees, and agents ('Indemnified Party') from and "
    "against any claims, losses, liabilities, damages, costs, and expenses (including reasonable "
    "attorneys' fees) arising from: (i) the Indemnifying Party's breach of this Agreement; "
    "(ii) gross negligence or willful misconduct; or (iii) infringement of any third-party "
    "intellectual property rights."
)

TERMINATION_CLAUSE = (
    "Either Party may terminate this Agreement for convenience upon thirty (30) days' prior "
    "written notice to the other Party. In the event of a material breach, the non-breaching "
    "Party may terminate immediately upon written notice if the breach is not cured within "
    "fifteen (15) days of such notice. Upon termination, all outstanding payment obligations "
    "shall become immediately due and payable."
)

AUDIT_CLAUSE = (
    "Buyer shall have the right, upon reasonable notice and during normal business hours, to "
    "audit Seller's books and records directly related to transactions under this Agreement. "
    "Seller shall maintain accurate records for a minimum of three (3) years following each "
    "transaction. Any overpayment identified through audit shall be refunded within thirty (30) days."
)

WARRANTY_CLAUSE = (
    "Seller warrants that all goods delivered under this Agreement shall: (i) conform to the "
    "specifications set forth in the relevant Purchase Order; (ii) be free from defects in "
    "materials and workmanship for a period of twelve (12) months from the date of delivery; "
    "and (iii) be fit for their intended commercial purpose. This warranty is in addition to "
    "any statutory rights of Buyer."
)

ANTI_ASSIGNMENT_CLAUSE = (
    "Neither Party may assign or transfer this Agreement or any rights or obligations hereunder "
    "without the prior written consent of the other Party, which shall not be unreasonably "
    "withheld. Any attempted assignment in violation of this clause shall be void ab initio."
)

LIMITATION_LIABILITY_CLAUSE = (
    "IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, "
    "CONSEQUENTIAL, OR PUNITIVE DAMAGES ARISING OUT OF OR IN CONNECTION WITH THIS AGREEMENT. "
    "EACH PARTY'S AGGREGATE LIABILITY SHALL NOT EXCEED THE TOTAL AMOUNTS PAID OR PAYABLE "
    "UNDER THIS AGREEMENT IN THE TWELVE (12) MONTHS PRECEDING THE CLAIM."
)

ENTIRE_AGREEMENT_CLAUSE = (
    "This Agreement, together with all Exhibits and Purchase Orders incorporated herein by "
    "reference, constitutes the entire agreement between the Parties with respect to its "
    "subject matter and supersedes all prior negotiations, representations, warranties, and "
    "understandings. Amendments must be in writing and signed by authorized representatives "
    "of both Parties."
)

SELLER_ADDRESS = (
    "Adventure Works Cycles, Inc.\n"
    "1 Bike Way, Building A\n"
    "Redmond, Washington 98052\n"
    "United States of America\n"
    "EIN: 91-1234567"
)

GOVERNING_LAW_CLAUSE = (
    "This Agreement shall be governed by and construed in accordance with the laws of {gov_law}, "
    "without regard to its conflict-of-law provisions. Any disputes arising hereunder shall be "
    "resolved by binding arbitration in {city}, {territory}."
)


# -- Helpers ------------------------------------------------------------------
def fmt_date(raw: str) -> str:
    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).strftime("%B %d, %Y")
        except Exception:
            pass
    return raw.strip()


def fmt_money(val) -> str:
    try:
        return "${:,.2f} USD".format(float(val))
    except Exception:
        return str(val)


# -- PDF Class ----------------------------------------------------------------
class ContractPDF(FPDF):
    def __init__(self, order_number: str):
        super().__init__()
        self.order_number = order_number
        self.set_margins(25, 20, 25)
        self.set_auto_page_break(True, margin=20)
        # Register DejaVu Unicode font
        self.add_font("DejaVu",  "",  FONT_REG)
        self.add_font("DejaVu",  "B", FONT_BOLD)
        self.add_font("DejaVu",  "I", FONT_ITAL)
        self.add_font("DejaVu",  "BI",FONT_BOLDITAL)

    def header(self):
        self.set_font("DejaVu", "B", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 7, "SALES AND DISTRIBUTION AGREEMENT  |  Ref: " + self.order_number, align="R")
        self.ln(3)
        self.set_draw_color(180, 180, 180)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-18)
        self.set_font("DejaVu", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 8, "Page " + str(self.page_no()) + " of {nb}  |  CONFIDENTIAL & PROPRIETARY", align="C")
        self.set_text_color(0, 0, 0)

    def title_block(self, title: str):
        self.set_font("DejaVu", "B", 15)
        self.ln(4)
        self.cell(0, 10, title, align="C")
        self.ln(5)
        self.set_draw_color(40, 80, 160)
        self.set_line_width(0.8)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.set_line_width(0.2)
        self.set_draw_color(0, 0, 0)
        self.ln(5)

    def section_heading(self, number: str, heading: str):
        self.ln(4)
        self.set_fill_color(235, 241, 255)
        self.set_font("DejaVu", "B", 11)
        self.cell(0, 8, number + ".  " + heading.upper(), fill=True)
        self.ln(6)

    def body_text(self, text: str):
        self.set_font("DejaVu", "", 9.5)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def indented_text(self, text: str, indent: float = 8):
        self.set_font("DejaVu", "", 9.5)
        x0 = self.l_margin + indent
        self.set_x(x0)
        self.multi_cell(self.w - self.r_margin - x0, 5.5, text)
        self.ln(1)

    def kv(self, label: str, value: str):
        label_w = 58
        val_w   = self.w - self.l_margin - self.r_margin - label_w
        self.set_font("DejaVu", "B", 9.5)
        y0 = self.get_y()
        self.cell(label_w, 6, label + ":", new_x="RIGHT", new_y="TOP")
        self.set_font("DejaVu", "", 9.5)
        self.multi_cell(val_w, 6, value)
        # Ensure y is below both columns
        if self.get_y() < y0 + 6:
            self.set_y(y0 + 6)

    def party_block(self, party_label: str, role: str, name: str, address: str):
        self.set_font("DejaVu", "B", 10)
        self.cell(0, 6, party_label + " - " + role, new_x="LMARGIN", new_y="NEXT")
        self.set_font("DejaVu", "", 9.5)
        self.multi_cell(0, 5.5, name + "\n" + address)
        self.ln(3)


# -- Contract builder ---------------------------------------------------------
def generate_contract(row: pd.Series, seq: int) -> dict:
    soid    = str(row["SalesOrderID"])
    sonum   = str(row["SalesOrderNumber"])
    cname   = str(row["CustomerName"])
    city    = str(row["City"])
    state   = str(row["State"])
    country = str(row["Country"])
    postal  = str(row["PostalCode"])
    terr    = str(row["TerritoryName"])
    po_num  = str(row["PurchaseOrderNumber"])
    ship_m  = str(row["ShipMethod"])
    track   = str(row["CarrierTracking"])
    card    = str(row["CardType"])
    sub     = fmt_money(row["SubTotal"])
    tax     = fmt_money(row["TaxAmt"])
    freight = fmt_money(row["Freight"])
    total   = fmt_money(row["TotalDue"])
    prods   = str(row["Products"])
    cats    = str(row["ProductCategories"])
    subcats = str(row["ProductSubcategories"])
    items   = int(row["TotalLineItems"])
    o_date  = fmt_date(str(row["OrderDate"]))
    d_date  = fmt_date(str(row["DueDate"]))
    s_date  = fmt_date(str(row["ShipDate"]))

    gov_law    = random.choice(GOVERNING_LAWS)
    pay_terms  = random.choice(PAYMENT_TERMS)
    ship_clause= SHIP_CLAUSES.get(ship_m, DEFAULT_SHIP_CLAUSE)

    try:
        exp_dt   = datetime.strptime(row["DueDate"].strip(), "%m/%d/%Y %I:%M:%S %p") + timedelta(days=365)
        exp_date = exp_dt.strftime("%B %d, %Y")
    except Exception:
        exp_date = "June 12, 2012"

    buyer_address = city + ", " + state + " " + postal + "\n" + country
    contract_no   = "AWC-" + sonum + "-" + "{:03d}".format(seq)
    pdf_filename  = "aw_contract_" + sonum + ".pdf"
    pdf_path      = os.path.join(OUT_DIR, pdf_filename)

    # -- Build PDF ------------------------------------------------------------
    pdf = ContractPDF(sonum)
    pdf.alias_nb_pages()
    pdf.add_page()

    # Title block
    pdf.title_block("SALES AND DISTRIBUTION AGREEMENT")
    pdf.set_font("DejaVu", "", 10)
    pdf.cell(0, 6, "Contract No.: " + contract_no, new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "Purchase Order Ref.: " + po_num + "   |   Sales Order: " + sonum, new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "Agreement Date: " + o_date, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Recitals
    pdf.set_font("DejaVu", "I", 9.5)
    pdf.multi_cell(0, 5.5,
        "WHEREAS, Adventure Works Cycles, Inc. is a manufacturer and distributor of high-performance "
        "bicycles, cycling accessories, and related sporting goods; and\n\n"
        "WHEREAS, " + cname + " (hereinafter \"Buyer\") desires to purchase certain goods from Seller "
        "under the terms and conditions set forth herein;\n\n"
        "NOW, THEREFORE, in consideration of the mutual covenants and agreements contained herein, "
        "the Parties agree as follows:"
    )
    pdf.ln(4)

    # Section 1 - Parties
    pdf.section_heading("1", "Parties to the Agreement")
    pdf.party_block("PARTY A", "Seller / Vendor", "Adventure Works Cycles, Inc.", SELLER_ADDRESS)
    pdf.party_block("PARTY B", "Buyer / Distributor", cname, buyer_address)

    # Section 2 - Scope of Goods
    pdf.section_heading("2", "Scope of Goods and Services")
    pdf.body_text(
        "Seller agrees to supply, and Buyer agrees to purchase, the following goods as specified "
        "in Sales Order " + sonum + " and incorporated Purchase Order " + po_num + ":"
    )
    pdf.indented_text("Product Categories:    " + cats)
    pdf.indented_text("Product Subcategories: " + subcats)
    pdf.indented_text("Total Line Items:      " + str(items))
    pdf.indented_text("Specific Products:\n" + prods)
    pdf.body_text(
        "All products shall conform to Adventure Works Cycles published specifications and quality "
        "standards applicable at the time of shipment."
    )

    # Section 3 - Payment
    pdf.section_heading("3", "Contract Value and Payment Terms")
    pdf.kv("Subtotal", sub)
    pdf.kv("Tax Amount", tax)
    pdf.kv("Freight Charges", freight)
    pdf.kv("Total Contract Value", total)
    pdf.ln(3)
    pdf.body_text("Payment Terms: " + pay_terms)
    pdf.body_text(
        "Payment Method: " + card + " card on file under Account No. " + str(row["AccountNumber"]) + ". "
        "All amounts are stated in United States Dollars (USD) unless otherwise agreed in writing."
    )

    # Section 4 - Dates
    pdf.section_heading("4", "Term, Effective Date, and Expiration Date")
    pdf.kv("Effective Date", o_date)
    pdf.kv("Shipment / Due Date", d_date)
    pdf.kv("Ship Date (Estimated)", s_date)
    pdf.kv("Expiration Date", exp_date)
    pdf.ln(3)
    pdf.body_text(
        "This Agreement shall become effective on the Agreement Date and shall remain in force until "
        "the Expiration Date (" + exp_date + "), unless earlier terminated in accordance with "
        "Section 8 below, or extended by mutual written amendment."
    )

    # Section 5 - Delivery
    pdf.section_heading("5", "Delivery and Shipping Terms")
    pdf.kv("Ship Method", ship_m)
    pdf.kv("Carrier Tracking No.", track)
    pdf.kv("Territory", terr + " - " + country)
    pdf.ln(3)
    pdf.body_text(ship_clause)
    pdf.body_text(
        "Delivery shall be made to: " + cname + ", " + city + ", " + state + ", " + country + " " + postal + ". "
        "Seller shall provide advance shipment notification (ASN) to Buyer no later than 24 hours "
        "prior to dispatch."
    )

    # Section 6 - Warranties
    pdf.section_heading("6", "Warranties")
    pdf.body_text(WARRANTY_CLAUSE)

    # Section 7 - Confidentiality
    pdf.section_heading("7", "Confidentiality")
    pdf.body_text(CONFIDENTIALITY_CLAUSE)

    # Section 8 - Termination
    pdf.section_heading("8", "Termination")
    pdf.body_text(TERMINATION_CLAUSE)

    # Section 9 - Indemnification
    pdf.section_heading("9", "Indemnification")
    pdf.body_text(INDEMNIFICATION_CLAUSE)

    # Section 10 - Limitation
    pdf.section_heading("10", "Limitation of Liability")
    pdf.body_text(LIMITATION_LIABILITY_CLAUSE)

    # Section 11 - Audit
    pdf.section_heading("11", "Audit Rights")
    pdf.body_text(AUDIT_CLAUSE)

    # Section 12 - Assignment
    pdf.section_heading("12", "Assignment")
    pdf.body_text(ANTI_ASSIGNMENT_CLAUSE)

    # Section 13 - Governing Law
    pdf.section_heading("13", "Governing Law and Dispute Resolution")
    pdf.body_text(GOVERNING_LAW_CLAUSE.format(gov_law=gov_law, city=city, territory=terr))

    # Section 14 - Entire Agreement
    pdf.section_heading("14", "Entire Agreement; Amendments")
    pdf.body_text(ENTIRE_AGREEMENT_CLAUSE)

    # Signature Page
    pdf.add_page()
    pdf.title_block("SIGNATURE PAGE")
    pdf.body_text(
        "IN WITNESS WHEREOF, the Parties have executed this Sales and Distribution Agreement "
        "as of " + o_date + ", the date first written above."
    )
    pdf.ln(10)

    col_w = (pdf.w - pdf.l_margin - pdf.r_margin) / 2 - 5
    x_left  = pdf.l_margin
    x_right = pdf.l_margin + col_w + 10
    y0 = pdf.get_y()

    pdf.set_font("DejaVu", "B", 10)
    pdf.set_xy(x_left, y0)
    pdf.cell(col_w, 6, "PARTY A - SELLER")
    pdf.set_xy(x_right, y0)
    pdf.cell(col_w, 6, "PARTY B - BUYER")
    pdf.ln(14)

    y1 = pdf.get_y()
    pdf.set_draw_color(80, 80, 80)
    pdf.line(x_left, y1, x_left + col_w, y1)
    pdf.line(x_right, y1, x_right + col_w, y1)
    pdf.ln(2)

    pdf.set_font("DejaVu", "", 9)
    pdf.set_xy(x_left, pdf.get_y())
    sig_left = "Authorized Signature\n\nName: _______________________\nTitle: ________________________\nDate:  ________________________\n\nAdventure Works Cycles, Inc."
    sig_right = "Authorized Signature\n\nName: _______________________\nTitle: ________________________\nDate:  ________________________\n\n" + cname
    pdf.multi_cell(col_w, 5, sig_left)
    pdf.set_xy(x_right, y1 + 2)
    pdf.multi_cell(col_w, 5, sig_right)

    # Exhibit A - Products Table
    pdf.add_page()
    pdf.title_block("EXHIBIT A - SCHEDULE OF GOODS")
    pdf.body_text("Sales Order: " + sonum + "   |   Purchase Order: " + po_num + "   |   Order Date: " + o_date)
    pdf.ln(2)

    # Table header
    pdf.set_fill_color(40, 80, 160)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("DejaVu", "B", 9)
    col_widths = [10, 95, 40, 15]
    for w, h in zip(col_widths, ["#", "Product Name", "Category", "Qty"]):
        pdf.cell(w, 7, h, border=1, fill=True)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)

    product_list = [p.strip() for p in prods.split(";") if p.strip()]
    cat_list     = [c.strip() for c in cats.split(";") if c.strip()]
    for i, prod in enumerate(product_list):
        fill = (i % 2 == 0)
        if fill:
            pdf.set_fill_color(245, 248, 255)
        pdf.set_font("DejaVu", "", 8)
        cat_cell = cat_list[i % len(cat_list)] if cat_list else ""
        prod_disp = prod[:55] + ("..." if len(prod) > 55 else "")
        pdf.cell(col_widths[0], 6, str(i + 1), border=1, fill=fill)
        pdf.cell(col_widths[1], 6, prod_disp, border=1, fill=fill)
        pdf.cell(col_widths[2], 6, cat_cell, border=1, fill=fill)
        pdf.cell(col_widths[3], 6, "1", border=1, fill=fill, align="C")
        pdf.ln()

    pdf.ln(4)
    pdf.set_font("DejaVu", "B", 10)
    pdf.cell(130, 7, "TOTAL CONTRACT VALUE:", border=0)
    pdf.cell(30, 7, total, border=1, align="R")
    pdf.ln()

    pdf.output(pdf_path)
    print("  [{:02d}] Generated: {}  (Buyer: {}, Total: {})".format(seq, pdf_filename, cname, total))

    return {
        "seq": seq,
        "contract_no": contract_no,
        "sales_order_id": soid,
        "sales_order_number": sonum,
        "purchase_order_number": po_num,
        "party_a": "Adventure Works Cycles, Inc.",
        "party_b": cname,
        "customer_id": str(row["CustomerID"]),
        "customer_account": str(row["AccountNumber"]),
        "city": city,
        "state": state,
        "country": country,
        "territory": terr,
        "order_date": o_date,
        "due_date": d_date,
        "ship_date": s_date,
        "expiration_date": exp_date,
        "governing_law": gov_law,
        "ship_method": ship_m,
        "carrier_tracking": track,
        "product_categories": cats,
        "product_subcategories": subcats,
        "total_line_items": items,
        "products": prods,
        "subtotal": str(row["SubTotal"]),
        "tax_amount": str(row["TaxAmt"]),
        "freight": str(row["Freight"]),
        "total_due": str(row["TotalDue"]),
        "card_type": card,
        "pdf_filename": pdf_filename,
        "pdf_path": pdf_path,
    }


def main():
    print("=" * 60)
    print(" AdventureWorks -> CUAD-Style Contract Generator")
    print("=" * 60)

    df = pd.read_csv(AW_CSV, encoding="utf-8-sig")
    agg = df.groupby("SalesOrderID").agg(
        SalesOrderNumber   =("SalesOrderNumber", "first"),
        CustomerID         =("CustomerID", "first"),
        CustomerName       =("CustomerDisplayName", "first"),
        AccountNumber      =("CustomerAccountNumber", "first"),
        City               =("City", "first"),
        State              =("StateProvinceName", "first"),
        Country            =("CountryRegionName", "first"),
        PostalCode         =("PostalCode", "first"),
        TerritoryName      =("TerritoryName", "first"),
        PurchaseOrderNumber=("PurchaseOrderNumber", "first"),
        OrderDate          =("OrderDate", "first"),
        DueDate            =("DueDate", "first"),
        ShipDate           =("ShipDate", "first"),
        ShipMethod         =("ShipMethodName", "first"),
        CarrierTracking    =("CarrierTrackingNumber", "first"),
        CardType           =("CardType", "first"),
        SubTotal           =("SubTotal", "first"),
        TaxAmt             =("TaxAmt", "first"),
        Freight            =("Freight", "first"),
        TotalDue           =("TotalDue", "first"),
        Products           =("ProductName",         lambda x: "; ".join(x.unique())),
        ProductCategories  =("ProductCategoryName",    lambda x: "; ".join(x.unique())),
        ProductSubcategories=("ProductSubcategoryName",lambda x: "; ".join(x.unique())),
        TotalLineItems     =("SalesOrderDetailID", "count"),
    ).reset_index()

    print("\nTotal unique orders to process: " + str(len(agg)) + "\n")

    random.seed(42)
    index_records = []
    for seq, (_, row) in enumerate(agg.iterrows(), start=1):
        rec = generate_contract(row, seq)
        index_records.append(rec)

    pd.DataFrame(index_records).to_csv(INDEX_CSV, index=False, encoding="utf-8-sig")
    print("\n" + "=" * 60)
    print("  Done! Generated " + str(len(index_records)) + " contracts.")
    print("  Output folder : " + OUT_DIR)
    print("  Index CSV     : " + INDEX_CSV)
    print("=" * 60)


if __name__ == "__main__":
    main()
