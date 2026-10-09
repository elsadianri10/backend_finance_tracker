"""Printable, paginated export of the server-calculated group snapshot."""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, CondPageBreak


FONT_DIR = Path(reportlab.__file__).parent / 'fonts'
pdfmetrics.registerFont(TTFont('SplitRegular', str(FONT_DIR / 'Vera.ttf')))
pdfmetrics.registerFont(TTFont('SplitBold', str(FONT_DIR / 'VeraBd.ttf')))
pdfmetrics.registerFontFamily('SplitRegular', normal='SplitRegular', bold='SplitBold')


def money(value):
    return ('-' if value < 0 else '') + 'Rp ' + f'{abs(value):,}'.replace(',', '.')


def day(value):
    year, month, date = value.split('-')
    return f'{date}-{month}-{year}'


def export_pdf(group):
    output = BytesIO()
    width, height = A4
    content_width = width - 64
    body = ParagraphStyle('SplitBody', fontName='SplitRegular', fontSize=8, leading=11, textColor=colors.HexColor('#243247'), splitLongWords=True)
    column_heading = ParagraphStyle('SplitColumnHeading', parent=body, fontName='SplitBold')
    heading = ParagraphStyle('SplitHeading', parent=body, fontName='SplitBold', fontSize=12, leading=15, spaceBefore=7, spaceAfter=4)
    title = ParagraphStyle('SplitTitle', parent=heading, fontSize=20, leading=24)
    bill_heading = ParagraphStyle('SplitBillHeading', parent=heading, fontSize=10, leading=13)
    story = []

    def p(value, style=body):
        return Paragraph(escape(str(value)).replace('\n', '<br/>'), style)

    def table(headers, rows, proportions):
        data = [[p(h, column_heading) for h in headers]] + [[p(cell) for cell in row] for row in rows]
        result = LongTable(data, colWidths=[content_width * n / sum(proportions) for n in proportions], repeatRows=1, hAlign='LEFT')
        result.setStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EAF0FF')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F7F9FC')]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LINEBELOW', (0, 0), (-1, 0), .5, colors.HexColor('#CED7E6')),
        ])
        story.extend([result, Spacer(1, 6)])

    names = {person['Id']: person['Name'] for person in group['Participants']}
    def participant_key(part):
        return names[part['ParticipantId']].casefold()

    def recipient_key(ids):
        return (len(ids) == len(names), tuple(sorted(names[key].casefold() for key in ids)))

    result = group['Calculation']
    story.extend([p('Split Bill Calculator', title), p(group['Name'], heading),
                  p(f"Periode {day(group['StartDate'])} - {day(group['EndDate'])} | {len(names)} peserta | {len(group['Expenses'])} pengeluaran"),
                  Spacer(1, 4), p('Total pengeluaran: ' + money(result['Total']), heading)])
    story.extend([CondPageBreak(90), p('Ringkasan per Peserta', heading)])
    rows = []
    participants = sorted(result['Participants'], key=participant_key)
    for part in participants:
        balance = part['Balance']
        rows.append([names[part['ParticipantId']], money(part['Total']), money(part['Paid']), ('Menerima ' if balance > 0 else 'Membayar ') + money(abs(balance)) if balance else 'Seimbang'])
    table(['Peserta', 'Total Bagian', 'Dibayarkan', 'Saldo Akhir'], rows, [1.4, 1.2, 1.2, 1.7])
    story.append(p('Rincian konsumsi dan biaya:'))
    table(['Peserta', 'Subtotal', 'Service Charge', 'Pajak', 'Penyesuaian Struk'], [[names[r['ParticipantId']], money(r['Subtotal']), money(r['ServiceCharge']), money(r['Tax']), money(r.get('Adjustment', 0))] for r in participants], [1.5, 1.2, 1.2, 1.2, 1.2])
    story.extend([CondPageBreak(90), p('Saran Transfer', heading)])
    if result['Transfers']:
        table(['Dari', 'Kepada', 'Nominal'], [[names[t['FromParticipantId']], names[t['ToParticipantId']], money(t['Amount'])] for t in sorted(result['Transfers'], key=lambda row: (names[row['FromParticipantId']].casefold(), names[row['ToParticipantId']].casefold()))], [2, 2, 1])
    else:
        story.append(p('Tidak ada transfer yang diperlukan.' if group['Expenses'] else 'Belum ada pengeluaran.'))
    story.append(p('Saran transfer dihitung dari saldo gabungan; belum menandakan pembayaran sudah dilakukan.'))
    story.extend([CondPageBreak(165), Spacer(1, 14), p('Daftar Pengeluaran / Transaksi', heading)])
    if not group['Expenses']:
        story.append(p('Belum ada pengeluaran.'))
    calculations = {row['Id']: row for row in result['Expenses']}
    for index, expense in enumerate(sorted(group['Expenses'], key=lambda row: row['ExpenseDate']), 1):
        calc = calculations[expense['Id']]
        story.extend([CondPageBreak(110), p(f"{index}. {expense['Name']}", bill_heading), p(f"{day(expense['ExpenseDate'])} | Dibayar {names[expense['PaidBy']]} | Total {money(calc['Total'])}"), Spacer(1, 4)])
        rows = []
        for item in sorted(expense['Items'], key=lambda row: recipient_key({s['ParticipantId'] for s in row['Shares']})):
            shares = ', '.join(names[s['ParticipantId']] + (f" ({money(s['Amount'])})" if item['SplitMode'] == 'CUSTOM' else '') for s in sorted(item['Shares'], key=participant_key))
            if item['SplitMode'] == 'EQUAL' and len(item['Shares']) == len(names):
                shares = f'Semua peserta ({len(names)})'
            rows.append([item['Name'], money(item['Amount']), 'Rata' if item['SplitMode'] == 'EQUAL' else 'Nominal berbeda', shares])
        table(['Item / Menu', 'Harga Total', 'Pembagian', 'Untuk Peserta'], rows, [3, 1.3, 1.4, 3])
        story.append(p(f"Subtotal: {money(calc['Subtotal'])} | Service charge: {money(calc['ServiceCharge'])} | Pajak: {money(calc['Tax'])}"))
        modes = {'MIXED': 'Service charge rata ke semua peserta; pajak sesuai konsumsi + bagian service charge.', 'EQUAL': 'Biaya tambahan rata ke peserta dengan konsumsi.', 'PROPORTIONAL': 'Biaya tambahan sesuai porsi konsumsi.'}
        story.append(p(modes[expense['FeeAllocation']]))
        if expense.get('ReceiptTotal') is not None:
            story.append(p(f"Sebelum penyesuaian: {money(calc['BeforeAdjustment'])} | Penyesuaian struk: {money(calc['Adjustment'])} | Total akhir: {money(calc['Total'])}"))
        if expense.get('Notes'):
            story.append(p('Notes: ' + expense['Notes']))
        story.append(Spacer(1, 4))
        table(['Peserta', 'Konsumsi', 'Service Charge', 'Pajak', 'Penyesuaian', 'Total'], [[names[r['ParticipantId']], money(r['Subtotal']), money(r['ServiceCharge']), money(r['Tax']), money(r.get('Adjustment', 0)), money(r['Total'])] for r in sorted(calc['Participants'], key=participant_key)], [1.5, 1, 1, 1, 1, 1.2])

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('SplitRegular', 8)
        canvas.setFillColor(colors.HexColor('#64748B'))
        canvas.drawString(32, 19, 'Finance Tracker | Split Bill Calculator')
        canvas.drawRightString(width - 32, 19, f'Halaman {doc.page}')
        canvas.restoreState()

    SimpleDocTemplate(output, pagesize=(width, height), leftMargin=32, rightMargin=32, topMargin=28, bottomMargin=38, title=group['Name'], author='Finance Tracker').build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
