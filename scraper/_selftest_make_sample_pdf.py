# -*- coding: utf-8 -*-
"""
SADECE TEST içindir - gerçek Hacettepe verisi DEĞİLDİR.
build.py / parse_pdf.py kodunun gerçekten çalıştığını sandbox içinde
kanıtlamak için gerçekçi yapıda örnek bir ders programı PDF'i üretir.
"""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

styles = getSampleStyleSheet()
doc = SimpleDocTemplate("sample_input/ORNEK-Ders-Programi.pdf", pagesize=A4)

elements = [Paragraph("ÖRNEK BÖLÜM 2026-2027 Güz Dönemi Ders Programı (TEST VERİSİ)", styles["Title"]),
            Spacer(1, 12), Paragraph("1. Sınıf", styles["Heading2"]), Spacer(1, 6)]

data1 = [
    ["Ders Kodu", "Ders Adı", "Gün", "Saat", "Derslik", "Öğretim Üyesi", "Kontenjan"],
    ["ORN 101", "Örnek Dersi I", "Pazartesi", "09:00-10:50", "A1", "Prof. Dr. A. Yılmaz", "60"],
    ["ORN 103", "Örnek Dersi II", "Çarşamba", "13:00-14:50", "B2", "Doç. Dr. B. Kaya", "45"],
]
t1 = Table(data1, repeatRows=1)
t1.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                         ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey)]))
elements += [t1, Spacer(1, 18), Paragraph("2. Sınıf", styles["Heading2"]), Spacer(1, 6)]

data2 = [
    ["Ders Kodu", "Ders Adı", "Gün", "Saat", "Derslik", "Öğretim Üyesi", "Kontenjan"],
    ["ORN 201", "İleri Örnek Dersi", "Salı", "10:00-11:50", "C3", "Dr. Öğr. Üyesi C. Demir", "30"],
]
t2 = Table(data2, repeatRows=1)
t2.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                         ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey)]))
elements += [t2]

doc.build(elements)
print("örnek pdf oluşturuldu")
