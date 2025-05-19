import os
import smtplib
import ssl
import pandas as pd
from email.message import EmailMessage
import pdfplumber
import warnings
warnings.filterwarnings("ignore")

# Učitaj podatke iz okruženja
sender_email = os.getenv("SENDER_EMAIL")
password = os.getenv("EMAIL_PASSWORD")
smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
smtp_port = int(os.getenv("SMTP_PORT", "465"))

# Učitaj Excel fajl sa korisnicima
df = pd.read_excel("BAZA E MAIL.xlsx")

# Pripremi mape
mapa_korisnika = dict(zip(df["Customer"].astype(str), df["Email"]))
mapa_linkova = {}
if "PaymentLink" in df.columns:
    mapa_linkova = dict(zip(df["Customer"].astype(str), df["PaymentLink"]))

folder = "uploads"
log_podaci = []

# Funkcija za Bill Number iz PDF-a
def izvuci_bill_number(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                words = page.extract_words()
                for i, word in enumerate(words):
                    if word['text'].lower() in ['račun', 'račun:'] and i+1 < len(words):
                        if words[i+1]['text'].lower().startswith('broj'):
                            if i+2 < len(words):
                                kandidat = words[i+2]['text'].replace(" ", "")
                                if kandidat.isdigit():
                                    return kandidat
        return None
    except Exception:
        return None

# Glavna petlja
for filename in os.listdir(folder):
    if filename.endswith(".pdf") and "faktura" in filename:
        parts = filename.replace(".pdf", "").split("-")
        customer_id = parts[-1]
        pdf_path = os.path.join(folder, filename)

        log_red = {
            "Customer ID": customer_id,
            "PDF fajl": filename,
            "Email": "",
            "Bill Number": "",
            "Status": "",
            "Poruka": ""
        }

        if customer_id not in mapa_korisnika:
            log_red["Status"] = "❌ Nije poslano"
            log_red["Poruka"] = "Email nije pronađen u bazi"
            log_podaci.append(log_red)
            print(f"[UPOZORENJE] Nema e-maila za kupca {customer_id}")
            continue

        receiver_email = mapa_korisnika[customer_id]
        log_red["Email"] = receiver_email

        bill_number = izvuci_bill_number(pdf_path)
        if not bill_number:
            log_red["Status"] = "❌ Nije poslano"
            log_red["Poruka"] = "Račun broj nije pronađen u PDF-u"
            log_podaci.append(log_red)
            print(f"[UPOZORENJE] Nema 'Račun broj' u fajlu {filename}")
            continue

        log_red["Bill Number"] = bill_number

        default_link = "https://securepay.telemach.ba/eeeb9783b183449bda942af78d1dc335"
        payment_link = mapa_linkova.get(customer_id, default_link)

        try:
            msg = EmailMessage()
            msg["From"] = sender_email
            msg["To"] = receiver_email
            msg["Subject"] = f"Faktura za kupca {customer_id}"
            msg.set_content("Ovaj e-mail ne podržava HTML prikaz.")

            msg.add_alternative(f"""<html><body>
<h2>TELEMACH račun</h2>
<p>Poštovani,</p>
<p>Vaš račun za mjesec <strong>april 2025.</strong> je u prilogu.</p>
<a href="{payment_link}" target="_blank">💳 Link za online plaćanje</a>
<p>Hvala što ste izabrali e-račun.</p>
<p><a href="https://www.research.net/r/eracun?so={bill_number}">Ispunite kratku anketu</a></p>
<p>Od sada Telemach račune možete plaćati online <strong>bez provizije</strong>.</p>
</body></html>""", subtype='html')

            with open(pdf_path, "rb") as f:
                file_data = f.read()
                msg.add_attachment(file_data, maintype="application", subtype="pdf", filename=filename)

            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
                server.login(sender_email, password)
                server.send_message(msg)

            log_red["Status"] = "✅ Poslano"
            print(f"[INFO] Poslana faktura za {customer_id} -> {receiver_email} | Bill: {bill_number}")

        except Exception as e:
            log_red["Status"] = "❌ Greška"
            log_red["Poruka"] = str(e)
            print(f"[GREŠKA] Problem pri slanju fajla {filename}: {e}")

        log_podaci.append(log_red)

# Snimi izvještaj
if log_podaci:
    df_log = pd.DataFrame(log_podaci)
    df_log.to_excel("log_izvjestaj.xlsx", index=False)
    print("[INFO] Log fajl sačuvan: log_izvjestaj.xlsx")
