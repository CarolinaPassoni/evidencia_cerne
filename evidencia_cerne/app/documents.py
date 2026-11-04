from pathlib import Path
from io import BytesIO
from copy import deepcopy
from datetime import datetime
from xml.sax.saxutils import escape
from PIL import Image, ImageOps
from docx import Document
from docx.text.paragraph import Paragraph as DocxParagraph
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.section import WD_SECTION_START
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, KeepTogether, Table, TableStyle
from .database import DATA_DIR


def display_date(date):
    if not date: return 'Não informada'
    try: return datetime.strptime(date, '%Y-%m-%d').strftime('%d/%m/%Y')
    except ValueError: return date


def color_rgb(s):
    try:
        ss = s.lstrip('#')
        if len(ss)!=6: raise ValueError()
        return RGBColor.from_string(ss.upper())
    except ValueError: return RGBColor(18,94,120)


def text_or_missing(s): return (s or '').strip() or 'Não informado.'

"""Layout de evidência fiel à ordem/estilo do documento de referência fornecido."""


def _lines(value):
    import re
    # Indicadores/competências são cadastrados por linha, sem inventar dados.
    raw = str(value or '').strip()
    if not raw:
        return []
    parts = raw.splitlines() if '\n' in raw else raw.split(';')
    return [re.sub(r'^\s*(?:[•●*-]|\d+[.)])\s*', '', part.strip()) for part in parts if part.strip()]


def _participants(value):
    raw=str(value or '').strip()
    if not raw:
        return []
    return [v.strip() for v in raw.replace(';', '\n').splitlines() if v.strip()]


def _reference_title(activity):
    title=(activity.title or 'Atividade sem título').strip()
    date=display_date(activity.activity_date)
    # Evita duplicação se o título já inclui a data, como no modelo enviado.
    if activity.activity_date and date not in title:
        return f'{title} ({date})'
    return title


def _add_ref_label(doc, label):
    p=doc.add_paragraph()
    p.paragraph_format.space_before=Pt(13)
    p.paragraph_format.space_after=Pt(3)
    p.paragraph_format.keep_with_next=True
    r=p.add_run(label)
    r.bold=True
    return p


def _add_ref_body(doc, text):
    for para in str(text or '').strip().split('\n\n'):
        if not para.strip():
            continue
        p=doc.add_paragraph(para.strip())
        p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_after=Pt(7)


REFERENCE_DOCX = Path(__file__).resolve().parent / 'templates' / 'modelo_original_evidencias.docx'


def _from_model(doc, exemplar, content=None):
    """Copia um parágrafo do DOCX original, inclusive fonte, tabulações e parágrafo."""
    element=deepcopy(exemplar._p)
    body=doc.element.body
    section=body.sectPr
    if section is None:
        body.append(element)
    else:
        body.insert(body.index(section), element)
    paragraph=DocxParagraph(element,doc._body)
    if content is not None:
        original_runs=list(paragraph.runs)
        if original_runs:
            original_runs[0].text=str(content)
            for excess in original_runs[1:]:
                excess._element.getparent().remove(excess._element)
        else:
            paragraph.add_run(str(content))
    # A legenda deve acompanhar o primeiro conteúdo, mesmo na quebra de página.
    if exemplar.text.strip() in ('Descrição:', 'Registro 1', 'Registro 2', 'Registro 3', 'Participantes dessa ação:', 'Objetivo:', 'Resultados:', 'Indicadores alcançados:', 'Competências e habilidades:'):
        paragraph.paragraph_format.keep_with_next=True
        if exemplar.text.strip() == 'Competências e habilidades:':
            paragraph.paragraph_format.space_before=Pt(10)
    return paragraph


def _body_blocks(content):
    return [p.strip() for p in str(content or '').split('\n\n') if p.strip()]


def create_reference_docx(activity, template, out_path):
    """Gera Word A PARTIR do DOCX original enviado, sem reutilizar seus dados e fotos ilustrativos."""
    if not REFERENCE_DOCX.is_file():
        raise FileNotFoundError(f'O modelo original não foi encontrado: {REFERENCE_DOCX}')
    doc=Document(str(REFERENCE_DOCX))
    samples=list(doc.paragraphs)
    if len(samples)<39 or len(doc.inline_shapes)<3:
        raise ValueError('O modelo DOCX original está incompleto ou foi alterado.')
    body=doc.element.body
    for elem in list(body):
        if elem.tag != qn('w:sectPr'):
            body.remove(elem)

    _from_model(doc,samples[0],_reference_title(activity))
    _from_model(doc,samples[1], '')
    _from_model(doc,samples[2],'Descrição:')
    for block in _body_blocks(text_or_missing(activity.description)):
        _from_model(doc,samples[3],block)
    groups={g.position:g for g in activity.groups}
    for pos in (1,2,3):
        _from_model(doc,samples[4],'')
        _from_model(doc,samples[5 if pos==1 else (8 if pos==2 else 11)],f'Registro {pos}')
        group=groups.get(pos)
        photos=list(group.photos)[:1] if group else []
        picture_sample=samples[6 if pos==1 else (9 if pos==2 else 12)]
        if photos:
            for photo in photos:
                fp=DATA_DIR/'uploads'/photo.filename
                pp=_from_model(doc,picture_sample)
                pp.clear()  # tira completamente as fotografias ilustrativas do parágrafo
                if not fp.is_file():
                    pp.add_run('Fotografia indisponível.').italic=True
                    continue
                try:
                    with Image.open(fp) as orig:
                        img=ImageOps.exif_transpose(orig)
                        img.thumbnail((1800,1800))
                        width,height=img.size
                        data=BytesIO()
                        img.convert('RGB').save(data,format='JPEG',quality=87)
                        data.seek(0)
                    scale=min(4.63/max(width,1),3.10/max(height,1))
                    pp.add_run().add_picture(data,width=Inches(width*scale),height=Inches(height*scale))
                    if (photo.description or '').strip():
                        _from_model(doc, samples[3], 'Descrição da fotografia: '+photo.description.strip())
                    if (photo.people or '').strip():
                        _from_model(doc, samples[15], 'Participantes/componentes na foto: '+photo.people.strip())
                except Exception:
                    pp.add_run('Fotografia indisponível.').italic=True
        else:
            pp=_from_model(doc,samples[3],'Nenhuma fotografia anexada.')
            if pp.runs: pp.runs[0].italic=True
        if group and group.description:
            pp=_from_model(doc,samples[3], 'Descrição do registro: '+group.description.strip())
        if group and group.people:
            _from_model(doc,samples[15], 'Participantes/componentes: '+group.people.strip())
    _from_model(doc,samples[13],'')
    _from_model(doc,samples[14],'Participantes dessa ação:')
    for person in _participants(activity.participants) or ['Não informado.']:
        _from_model(doc,samples[15],person)
    _from_model(doc,samples[18],'')
    _from_model(doc,samples[19],'Objetivo:')
    for block in _body_blocks(text_or_missing(activity.objective)):
        _from_model(doc,samples[20],block)
    _from_model(doc,samples[21],'Resultados:')
    for block in _body_blocks(text_or_missing(activity.results)):
        _from_model(doc,samples[22],block)
    _from_model(doc,samples[24],'Indicadores alcançados:')
    for item in _lines(getattr(activity,'indicators','')) or ['Não informados.']:
        _from_model(doc,samples[25],item)
    _from_model(doc,samples[30],'Competências e habilidades:')
    for item in _lines(getattr(activity,'competencies','')) or ['Não informadas.']:
        _from_model(doc,samples[31],item)

    # Elimina do arquivo resultante relações com as 3 imagens ilustrativas originais.
    used={blip.get(qn('r:embed')) for blip in doc.element.body.xpath('.//a:blip')}
    for rid,rel in list(doc.part.rels.items()):
        if rel.reltype.endswith('/image') and rid not in used:
            del doc.part.rels[rid]

    doc.core_properties.title=activity.title
    doc.core_properties.subject='Evidência institucional a partir do modelo DOCX original'
    doc.save(out_path)

def create_reference_pdf(activity, template, out_path):
    from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
    from reportlab.platypus import PageBreak
    styles=getSampleStyleSheet()
    heading=ParagraphStyle('RefHeading',parent=styles['Normal'],fontName='Helvetica-Bold',fontSize=10.5,leading=14,spaceBefore=13,spaceAfter=5,keepWithNext=True)
    body=ParagraphStyle('RefBody',parent=styles['Normal'],fontName='Helvetica',fontSize=10,leading=14,alignment=TA_JUSTIFY,spaceAfter=7)
    plain=ParagraphStyle('RefPlain',parent=body,alignment=TA_LEFT,spaceAfter=2)
    title=ParagraphStyle('RefTitle',parent=heading,spaceBefore=0,spaceAfter=13)
    bullet=ParagraphStyle('RefBullet',parent=plain,leftIndent=13*mm,firstLineIndent=-6*mm,spaceAfter=2)
    story=[Paragraph(escape(_reference_title(activity)),title)]
    story.append(Paragraph('Descrição:',heading))
    story.append(Paragraph(escape(text_or_missing(activity.description)).replace('\n','<br/>'),body))
    groups={g.position:g for g in activity.groups}
    for pos in (1,2,3):
        group=groups.get(pos)
        story.append(Paragraph(f'Registro {pos}',heading))
        photos=list(group.photos)[:1] if group else []
        if photos:
            for photo in photos:
                path=DATA_DIR/'uploads'/photo.filename
                if not path.is_file():
                    story.append(Paragraph('Fotografia indisponível.',plain))
                    continue
                try:
                    with Image.open(path) as orig:
                        w,h=ImageOps.exif_transpose(orig).size
                    scale=min((118*mm)/w,(79*mm)/h)
                    story.append(RLImage(str(path),width=w*scale,height=h*scale,hAlign='LEFT'))
                    if (photo.description or '').strip():
                        story.append(Paragraph('<b>Descrição da fotografia:</b> '+escape(photo.description),plain))
                    if (photo.people or '').strip():
                        story.append(Paragraph('<b>Participantes/componentes na foto:</b> '+escape(photo.people),plain))
                    story.append(Spacer(1,5*mm))
                except Exception:
                    story.append(Paragraph('Fotografia indisponível.',plain))
        elif not group or (not group.description and not group.people):
            story.append(Paragraph('Nenhuma fotografia anexada.',plain))
        if group and group.description:
            story.append(Paragraph('<b>Descrição do registro:</b> '+escape(group.description).replace('\n','<br/>'),body))
        if group and group.people:
            story.append(Paragraph('<b>Participantes/componentes:</b> '+escape(group.people).replace('\n','<br/>'),body))
    story.append(Paragraph('Participantes dessa ação:',heading))
    people=_participants(activity.participants)
    for person in (people or ['Não informado.']):
        story.append(Paragraph(escape(person),plain))
    for name,content in [('Objetivo:',activity.objective),('Resultados:',activity.results)]:
        story.append(Paragraph(name,heading))
        for part in text_or_missing(content).split('\n\n'):
            story.append(Paragraph(escape(part).replace('\n','<br/>'),body))
    for name,items,empty in [('Indicadores alcançados:',_lines(getattr(activity,'indicators','')),'Não informados.'),
                             ('Competências e habilidades:',_lines(getattr(activity,'competencies','')),'Não informadas.')]:
        story.append(Paragraph(name,heading))
        for item in items:
            story.append(Paragraph('&#8226; &nbsp;'+escape(item),bullet))
        if not items:
            story.append(Paragraph(empty,plain))
    pdf=SimpleDocTemplate(str(out_path),pagesize=A4,leftMargin=24*mm,rightMargin=24*mm,topMargin=22*mm,bottomMargin=17*mm,
                          title=activity.title,author='Evidência+')
    pdf.build(story)


def create_docx(activity, template, out_path):
    if getattr(template, "layout", "institutional") == "reference":
        return create_reference_docx(activity, template, out_path)
    doc=Document(); section=doc.sections[0]
    section.top_margin=Inches(.62); section.bottom_margin=Inches(.58)
    section.left_margin=Inches(.84); section.right_margin=Inches(.84)
    styles=doc.styles
    styles['Normal'].font.name='Arial'; styles['Normal'].font.size=Pt(10)
    styles['Normal'].paragraph_format.space_after=Pt(5)
    for name in ['Heading 1','Heading 2']:
        styles[name].font.name='Arial'; styles[name].font.bold=True; styles[name].font.color.rgb=color_rgb(template.color)
        styles[name].paragraph_format.space_before=Pt(8 if name=='Heading 1' else 5)
        styles[name].paragraph_format.space_after=Pt(3)
        styles[name].paragraph_format.keep_with_next=True
        styles[name].font.size=Pt(12 if name=='Heading 1' else 11)
    head=section.header.paragraphs[0]; head.text=template.institution or 'EVIDÊNCIAS INSTITUCIONAIS'
    head.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    head.runs[0].font.size=Pt(8); head.runs[0].font.bold=True; head.runs[0].font.color.rgb=color_rgb(template.color)
    f=section.footer.paragraphs[0]; f.text=template.footer or 'Documento de evidência institucional'
    f.alignment=WD_ALIGN_PARAGRAPH.CENTER
    f.runs[0].font.size=Pt(8); f.runs[0].font.color.rgb=RGBColor(110,121,136)
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    r=p.add_run(template.subtitle or 'RELATÓRIO DE EVIDÊNCIA'); r.bold=True; r.font.size=Pt(16); r.font.color.rgb=color_rgb(template.color)
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    r=p.add_run(activity.title or 'Atividade sem título'); r.font.size=Pt(12); r.bold=True
    doc.add_heading('1. IDENTIFICAÇÃO DA ATIVIDADE', level=1)
    for label, val in [('Título',activity.title),('Data',display_date(activity.activity_date)),('Local',activity.location),('Participantes',activity.participants),('Projeto',activity.project.name if activity.project else '')]:
        pp=doc.add_paragraph(); pp.add_run(label+': ').bold=True; pp.add_run(val or 'Não informado')
    doc.add_heading('2. DESCRIÇÃO DA ATIVIDADE', level=1)
    doc.add_paragraph(text_or_missing(activity.description))
    doc.add_heading('3. OBJETIVO', level=1)
    doc.add_paragraph(text_or_missing(activity.objective))
    doc.add_heading('4. REGISTROS FOTOGRÁFICOS', level=1)
    populated=[g for g in activity.groups if g.photos or g.description or g.title or g.people]
    if not populated: doc.add_paragraph('Não foram cadastrados registros fotográficos.')
    for g in populated:
        doc.add_heading(f'Registro {g.position} | {g.title or "Registro fotográfico"}', level=2)
        photos=list(g.photos)[:1]
        if photos:
            for start in range(0,len(photos),2):
                row_photos=photos[start:start+2]
                table=doc.add_table(rows=1, cols=2); table.alignment=WD_TABLE_ALIGNMENT.CENTER
                for i,pic in enumerate(row_photos):
                    cell=table.rows[0].cells[i]; cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
                    cell.text=''
                    pp=cell.paragraphs[0]; pp.alignment=WD_ALIGN_PARAGRAPH.CENTER
                    fp=DATA_DIR/'uploads'/pic.filename
                    if fp.exists():
                        try:
                            with Image.open(fp) as im:
                                im=ImageOps.exif_transpose(im); im.thumbnail((1300,1000))
                                buf=BytesIO(); im.convert('RGB').save(buf,format='JPEG',quality=88); buf.seek(0)
                            pp.add_run().add_picture(buf,width=Inches(2.55))
                            if pic.description:
                                cap=cell.add_paragraph('Descrição: '+pic.description)
                                cap.style=doc.styles['Normal']
                            if pic.people:
                                cell.add_paragraph('Participantes/componentes: '+pic.people)
                        except Exception: pp.add_run('[Imagem indisponível]')
        pp=doc.add_paragraph(); pp.add_run('Descrição: ').bold=True; pp.add_run(text_or_missing(g.description))
        if g.people:
            pp=doc.add_paragraph(); pp.add_run('Participantes/componentes: ').bold=True; pp.add_run(g.people)
    doc.add_heading('5. RESULTADOS ALCANÇADOS', level=1)
    doc.add_paragraph(text_or_missing(activity.results))
    doc.add_heading('6. CONSIDERAÇÕES FINAIS', level=1)
    doc.add_paragraph(text_or_missing(activity.conclusions))
    doc.core_properties.title=activity.title
    doc.core_properties.subject='Registro de evidência institucional'
    doc.save(out_path)


def pdf_styles(hex_color):
    styles=getSampleStyleSheet()
    try: primary=colors.HexColor(hex_color)
    except Exception: primary=colors.HexColor('#125e78')
    styles.add(ParagraphStyle(name='EvtTitle',parent=styles['Title'],textColor=primary,fontName='Helvetica-Bold',fontSize=14,leading=18,spaceAfter=12))
    styles.add(ParagraphStyle(name='EvtHeading',parent=styles['Heading2'],textColor=primary,fontSize=11,leading=14,spaceBefore=15,spaceAfter=7))
    styles.add(ParagraphStyle(name='EvtBody',parent=styles['BodyText'],fontSize=9.4,leading=14,spaceAfter=9))
    styles.add(ParagraphStyle(name='EvtSub',parent=styles['Heading3'],textColor=primary,fontSize=10,leading=13,spaceBefore=9,spaceAfter=6))
    return styles


def create_pdf(activity, template, out_path):
    if getattr(template, "layout", "institutional") == "reference":
        return create_reference_pdf(activity, template, out_path)
    styles=pdf_styles(template.color)
    s=[]; p=lambda x: Paragraph(escape(str(x or '')),styles['EvtBody'])
    s.append(Paragraph(escape(template.subtitle or 'RELATÓRIO DE EVIDÊNCIA'),styles['EvtTitle']))
    s.append(Paragraph(escape(activity.title or 'Atividade sem título'),styles['EvtSub']))
    s.append(Paragraph('1. IDENTIFICAÇÃO DA ATIVIDADE', styles['EvtHeading']))
    for label,val in [('Título',activity.title),('Data',display_date(activity.activity_date)),('Local',activity.location),('Participantes',activity.participants),('Projeto',activity.project.name if activity.project else '')]:
        s.append(Paragraph(f'<b>{escape(label)}:</b> {escape(val or "Não informado")}',styles['EvtBody']))
    for idx,title,txt in [(2,'DESCRIÇÃO DA ATIVIDADE',activity.description),(3,'OBJETIVO',activity.objective)]:
        s.append(Paragraph(f'{idx}. {title}',styles['EvtHeading'])); s.append(p(text_or_missing(txt)))
    s.append(Paragraph('4. REGISTROS FOTOGRÁFICOS',styles['EvtHeading']))
    populated=[g for g in activity.groups if g.photos or g.description or g.title or g.people]
    if not populated: s.append(p('Não foram cadastrados registros fotográficos.'))
    for g in populated:
        s.append(Paragraph(f'Registro {g.position} | {escape(g.title or "Registro fotográfico")}',styles['EvtSub']))
        for start in range(0,min(len(g.photos),1),2):
            cells=[]
            for photo in g.photos[start:start+1]:
                fp=DATA_DIR/'uploads'/photo.filename
                if fp.exists():
                    try:
                        with Image.open(fp) as im:
                            w,h=im.size
                        scale=min(79*mm/w,58*mm/h)
                        cells.append(RLImage(str(fp),width=w*scale,height=h*scale))
                    except Exception: cells.append(p('[Imagem indisponível]'))
            if cells:
                while len(cells)<2: cells.append('')
                table=Table([cells],colWidths=[86*mm]*2,hAlign='CENTER')
                table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(0,0),(-1,-1),'CENTER'),('BOTTOMPADDING',(0,0),(-1,-1),10)]))
                s.append(table)
        s.append(Paragraph('<b>Descrição:</b> '+escape(text_or_missing(g.description)),styles['EvtBody']))
        if g.people: s.append(Paragraph('<b>Participantes/componentes:</b> '+escape(g.people),styles['EvtBody']))
    for idx,title,txt in [(5,'RESULTADOS ALCANÇADOS',activity.results),(6,'CONSIDERAÇÕES FINAIS',activity.conclusions)]:
        s.append(Paragraph(f'{idx}. {title}',styles['EvtHeading'])); s.append(p(text_or_missing(txt)))
    def decorate(c,d):
        c.saveState()
        c.setFont('Helvetica',8); c.setFillColor(colors.HexColor('#64748b'))
        c.drawString(19*mm,285*mm, (template.institution or 'Evidências institucionais')[:105])
        c.drawCentredString(105*mm,13*mm, (template.footer or 'Documento institucional')[:110])
        c.drawRightString(194*mm,13*mm,str(d.page))
        c.restoreState()
    pdf=SimpleDocTemplate(str(out_path),pagesize=A4,leftMargin=19*mm,rightMargin=19*mm,topMargin=24*mm,bottomMargin=20*mm)
    pdf.build(s,onFirstPage=decorate,onLaterPages=decorate)
