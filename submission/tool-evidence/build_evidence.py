"""Package the three already sanitized evidence screenshots; needs ReportLab/Pillow."""
from pathlib import Path
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import HexColor
ROOT = Path(__file__).resolve().parents[2]
shots = Path(__file__).resolve().parent / 'screenshot'
redactions = {name: None for name in sorted(p.name for p in shots.glob('*.png'))}

out=ROOT/'submission/tool-evidence/CareSteps_WorkBuddy_Evidence.pdf'
c=canvas.Canvas(str(out),pagesize=(842,650))
c.setTitle('CareSteps - WorkBuddy conversation evidence')
c.setAuthor('CareSteps team')
c.setFillColor(HexColor('#134e5e'));c.setFont('Helvetica-Bold',24);c.drawString(42,590,'CareSteps | WorkBuddy development evidence')
c.setFillColor(HexColor('#1b2630'));c.setFont('Helvetica',12)
lines=[
 'Tencent Cloud AI Singapore Hackathon 2026 - Healthcare Track',
 'Recorded session: October 15, 2026. Packaged: October 16, 2026.',
 '',
 'Task 1: Implement the consolidated GET /api/stats endpoint and regression tests.',
 'Task 2: Write the Render / Railway single-instance deployment guide.',
 '',
 'The following three pages contain the existing conversation screenshots in order:',
 '1. Task request and source inspection in the WorkBuddy interface.',
 '2. Changed files, the deployment guide and validation work.',
 '3. Completion response, sample API result and the guide preview.',
 '',
 'Only private local-path prefixes and one account display name were redacted.',
 'Original images remain in the owner\'s local archive. No conversation was fabricated.',
 '',
 'These screenshots document the two completed WorkBuddy tasks listed above.',
 'See docs/development.md for the recorded workflow and verification process.',
 '',
 'Historical task validation: 5 targeted tests and 170 full-suite tests passed.',
 'Current release validation has 171 tests and 27 routing scenarios.',
 'Software checks do not establish clinical validation or accessibility conformance.',
]
y=548
for line in lines:
 c.drawString(42,y,line);y-=22
c.showPage()
for index,(name,_) in enumerate(redactions.items(),1):
 im=Image.open(shots/name)
 iw,ih=im.size
 pw=max(1000,iw);ph=ih+90
 c.setPageSize((pw,ph));c.setFillColor(HexColor('#134e5e'));c.setFont('Helvetica-Bold',18)
 c.drawString(24,ph-28,f'CareSteps | WorkBuddy conversation screenshot {index} of 3')
 c.setFont('Helvetica',11);c.setFillColor(HexColor('#1b2630'));c.drawString(24,ph-48,f'Original capture: {name} | Redactions: private path/account only')
 c.drawImage(ImageReader(im),(pw-iw)/2,15,width=iw,height=ih)
 c.showPage()
c.save()
print('EVIDENCE_PDF_BYTES',out.stat().st_size)
