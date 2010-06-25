#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: ukanga

import os
import copy

from rapidsms.webui.utils import render_to_response
from django.utils.translation import gettext_lazy as _
from django.template import Template, Context
from django.http import HttpResponse

try:
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import letter, landscape, A4
    from reportlab.platypus import Paragraph, SimpleDocTemplate, PageBreak
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
except ImportError:
    pass

from childcount.models import Clinic
from childcount.models.ccreports import TheCHWReport
from childcount.models.ccreports import ThePatient, OperationalReport
from childcount.utils import RotatedParagraph

from libreport.pdfreport import PDFReport, p
from libreport.csvreport import CSVReport

from locations.models import Location

styles = getSampleStyleSheet()

styleN = styles['Normal']
styleH = styles['Heading1']
styleH3 = styles['Heading3']


def all_patient_list_pdf(request, rfilter=u'all', rformat="html"):
    report_title = ThePatient._meta.verbose_name
    rows = []
    if rfilter == 'underfive':
        reports = ThePatient.under_five()
    else:
        reports = ThePatient.objects.all().order_by('chw', 'household')

    columns, sub_columns = ThePatient.patients_summary_list()

    if rformat == 'pdf':
        for report in reports:
            rows.append([data for data in columns])
        rpt = PDFReport()
        rpt.setTitle(report_title)
        rpt.setFilename('_'.join(report_title.split()) + '.pdf')
        rpt.setTableData(reports, columns, _("All Patients"))
        return rpt.render()
    else:
        i = 0
        for report in reports:
            i += 1
            row = {}
            row["cells"] = [{'value': \
                             Template(col['bit']).render(Context({'object': \
                                                report}))} for col in columns]
            if i == 100:
                row['complete'] = True
                rows.append(row)
                break
            rows.append(row)

        aocolumns_js = "{ \"sType\": \"html\" },"
        for col in columns[1:] + (sub_columns if sub_columns != None else []):
            if not 'colspan' in col:
                aocolumns_js += "{ \"asSorting\": [ \"desc\", \"asc\" ], " \
                                "\"bSearchable\": true },"
        aocolumns_js = aocolumns_js[:-1]

        aggregate = False
        context_dict = {'get_vars': request.META['QUERY_STRING'],
                        'columns': columns, 'sub_columns': sub_columns,
                        'rows': rows, 'report_title': report_title,
                        'aggregate': aggregate, 'aocolumns_js': aocolumns_js}

        if request.method == 'GET' and 'excel' in request.GET:
            '''response = HttpResponse(mimetype="application/vnd.ms-excel")
            filename = "%s %s.xls" % \
                       (report_title, datetime.now().strftime("%d%m%Y"))
            response['Content-Disposition'] = "attachment; " \
                                              "filename=\"%s\"" % filename
            from findug.utils import create_excel
            response.write(create_excel(context_dict))
            return response'''
            return render_to_response(request, 'childcount/patient.html', \
                                        context_dict)
        else:
            return render_to_response(request, 'childcount/patient.html', \
                                        context_dict)


def all_patient_list_per_chw_pdf(request):
    report_title = ThePatient._meta.verbose_name

    rpt = PDFReport()
    rpt.setTitle(report_title)
    rpt.setFilename('_'.join(report_title.split()) + '.pdf')
    rpt.setRowsPerPage(42)

    columns, sub_columns = ThePatient.patients_summary_list()

    chws = TheCHWReport.objects.all()
    for chw in chws:
        rows = []
        reports = ThePatient.objects.filter(chw=chw).order_by('household')
        summary = u"Number of Children: %(num)s" % {'num': reports.count()}
        for report in reports:
            rows.append([data for data in columns])

        sub_title = u"%s %s" % (chw, summary)
        #rpt.setElements([p(summary)])
        rpt.setTableData(reports, columns, chw, hasCounter=True)
        rpt.setPageBreak()

    return rpt.render()


def under_five(request):
    report_title = ThePatient._meta.verbose_name

    rpt = PDFReport()
    rpt.setTitle(report_title)
    rpt.setFilename('_'.join(report_title.split()) + '.pdf')
    rpt.setRowsPerPage(42)

    columns, sub_columns = ThePatient.patients_summary_list()

    chws = TheCHWReport.objects.all()
    for chw in chws:
        rows = []
        reports = ThePatient.under_five(chw)
        summary = u"Number of Children: %(num)s" % {'num': reports.count()}
        for report in reports:
            rows.append([data for data in columns])

        sub_title = u"%s %s" % (chw, summary)
        #rpt.setElements([p(summary)])
        rpt.setTableData(reports, columns, chw, hasCounter=True)
        rpt.setPageBreak()

    return rpt.render()


def chw(request, rformat='html'):
    '''Community Health Worker page '''
    report_title = TheCHWReport._meta.verbose_name
    rows = []

    reports = TheCHWReport.objects.filter(role__code='chw')
    columns, sub_columns = TheCHWReport.summary()
    if rformat.lower() == 'pdf':
        rpt = PDFReport()
        rpt.setTitle(report_title)
        rpt.setFilename('_'.join(report_title.split()) + '.pdf')

        for report in reports:
            rows.append([data for data in columns])

        rpt.setTableData(reports, columns, report_title)
        rpt.setPageBreak()

        return rpt.render()
    else:
        i = 0
        for report in reports:
            i += 1
            row = {}
            row["cells"] = [{'value': \
                             Template(col['bit']).render(Context({'object': \
                                                report}))} for col in columns]
            if i == 100:
                row['complete'] = True
                rows.append(row)
                break
            rows.append(row)

        aocolumns_js = "{ \"sType\": \"html\" },"
        for col in columns[1:] + (sub_columns if sub_columns != None else []):
            if not 'colspan' in col:
                aocolumns_js += "{ \"asSorting\": [ \"desc\", \"asc\" ], " \
                                "\"bSearchable\": true },"
        aocolumns_js = aocolumns_js[:-1]

        aggregate = False
        context_dict = {'get_vars': request.META['QUERY_STRING'],
                        'columns': columns, 'sub_columns': sub_columns,
                        'rows': rows, 'report_title': report_title,
                        'aggregate': aggregate, 'aocolumns_js': aocolumns_js}

        if request.method == 'GET' and 'excel' in request.GET:
            '''response = HttpResponse(mimetype="application/vnd.ms-excel")
            filename = "%s %s.xls" % \
                       (report_title, datetime.now().strftime("%d%m%Y"))
            response['Content-Disposition'] = "attachment; " \
                                              "filename=\"%s\"" % filename
            from findug.utils import create_excel
            response.write(create_excel(context_dict))
            return response'''
            return render_to_response(request, 'childcount/chw.html', \
                                        context_dict)
        else:
            return render_to_response(request, 'childcount/chw.html', \
                                            context_dict)


def operationalreport(request, rformat):
    filename = 'operationalreport.pdf'
    story = []
    
    for location in Clinic.objects.all():
        if not TheCHWReport.objects.filter(location=location).count():
            continue
        tb = operationalreportable(location, TheCHWReport.objects.\
            filter(location=location))
        story.append(tb)
        story.append(PageBreak())

    doc = SimpleDocTemplate(filename, pagesize = landscape(A4), \
                            topMargin=(0 * inch), \
                            bottomMargin=(0 * inch))
    doc.build(story)
    response = HttpResponse(mimetype='application/pdf')
    response['Cache-Control'] = ""
    response['Content-Disposition'] = "attachment; filename=%s" % filename
    response.write(open(filename).read())
    os.remove(filename)
    return response


def operationalreportable(title, indata=None):
    styleH3.fontName = 'Times-Bold'
    styleH3.alignment = TA_CENTER
    styleN2 = copy.copy(styleN)
    styleN2.alignment = TA_CENTER
    styleN3 = copy.copy(styleN)
    styleN3.alignment = TA_RIGHT

    opr = OperationalReport()
    cols = opr.get_columns()

    hdata = [Paragraph('%s' % title, styleH3)]
    hdata.extend((len(cols) - 1) * [''])
    data = [hdata, ['', Paragraph('Household', styleH3), '', '', \
            Paragraph('Newborn', styleH3), '', '', \
            Paragraph('Under-5\'s', styleH3), '', \
            '', '', '', '', Paragraph('Pregnant', styleH3), '', '', \
            Paragraph('Follow-up', styleH3), '', \
            Paragraph('SMS', styleH3), ''], \
            ['', Paragraph('A1', styleH3), Paragraph('A2', styleH3), \
            Paragraph('A3', styleH3), Paragraph('B1', styleH3), \
            Paragraph('B2', styleH3), Paragraph('B3', styleH3), \
            Paragraph('C1', styleH3), Paragraph('C2', styleH3), \
            Paragraph('C3', styleH3), Paragraph('C4',  styleH3), \
            Paragraph('C5', styleH3), Paragraph('C6', styleH3), \
            Paragraph('D1', styleH3), Paragraph('D2', styleH3), \
            Paragraph('D3', styleH3), Paragraph('E1', styleH3), \
            Paragraph('E2', styleH3), Paragraph('F1', styleH3), \
            Paragraph('F2', styleH3)]]

    #styleN.borderWidth = 0
    #styleN.borderColor = colors.red 
    thirdrow = [Paragraph(cols[0]['name'], styleH3)]
    thirdrow.extend([RotatedParagraph(Paragraph(col['name'], styleN), 2.3 * inch, \
                                    0.25 * inch) for col in cols[1:]])
    data.append(thirdrow)

    fourthrow = [Paragraph('Target:', styleH3)]
    fourthrow.extend([Paragraph(item, styleN) for item in ['-', '-', '100', \
                        '-', '100', '100', '-', '-', '-', '-', '100', '-', \
                        '-', '-', '100', '100', '&lt;=2', '0', '-']])
    data.append(fourthrow)
    
    fifthrow = [Paragraph('<u>List of CHWs</u>', styleH3)]
    fifthrow.extend([Paragraph(item, styleN) for item in [''] * 19])
    data.append(fifthrow)

    rowHeights = [None, None, None, 2.3 * inch, 0.25 * inch, 0.25 * inch]
    colWidths = [1.5 * inch]
    colWidths.extend((len(cols) - 1) * [0.5 * inch])
    
    if indata:
        for row in indata:
            ctx = Context({"object": row})
            values = [Paragraph(Template(cols[0]["bit"]).render(ctx), \
                                styleN)]
            values.extend([Paragraph(Template(col["bit"]).render(ctx), \
                                styleN3) for col in cols[1:]])
            data.append(values)
        rowHeights.extend(len(indata) * [0.25 * inch])
    tb = Table(data, colWidths=colWidths, rowHeights=rowHeights, repeatRows=6)
    tb.setStyle(TableStyle([('SPAN', (0, 0), (19, 0)),
                            ('INNERGRID', (0, 0), (-1, -1), 0.1, \
                            colors.lightgrey),\
                            ('BOX', (0, 0), (-1, -1), 0.1, \
                            colors.lightgrey), \
                            ('BOX', (1, 1), (3, -1), 5, \
                            colors.lightgrey),\
                            ('SPAN', (1, 1), (3, 1)), \
                            ('SPAN', (4, 1), (6, 1)), \
                            ('BOX', (7, 1), (12, -1), 5, \
                            colors.lightgrey),\
                            ('SPAN', (7, 1), (12, 1)), \
                            ('SPAN', (13, 1), (15, 1)), \
                            ('BOX', (16, 1), (17, -1), 5, \
                            colors.lightgrey),\
                            ('SPAN', (16, 1), (17, 1)), \
                            ('SPAN', (-2, 1), (-1, 1)), \
                ]))
    return tb


def registerlist(request, rformat):
    filename = 'registerlist.pdf'
    story = []
    
    for location in Clinic.objects.all():
        chws = TheCHWReport.objects.filter(location=location)
        if not chws.count():
            continue
        for chw in chws:
            households = chw.households()
            if not households:
                continue
            patients = []
            boxes = []
            for household in households:
                trow = len(patients)
                patients.append(household)
                hs = ThePatient.objects.filter(household=household)\
                                .exclude(health_id=household.health_id)\
                                .order_by('household')
                patients.extend(hs)
                patients.append(ThePatient())
                brow = len(patients) - 1
                boxes.append({"top": trow, "bottom": brow})
            tb = thepatientregister(_(u"CHW: %s: %s") % (location, chw), \
                                    patients, boxes)
            story.append(tb)
            story.append(PageBreak())
        story.append(PageBreak())
    from libreport.pdfreport import MultiColDocTemplate
    from reportlab.platypus import NextPageTemplate
    story.insert(0, PageBreak())
    story.insert(0, NextPageTemplate("laterPages"))
    doc = MultiColDocTemplate(filename, 2, pagesize = landscape(A4), \
                            topMargin=(0.5 * inch), showBoundary=0)
    doc.build(story)
    response = HttpResponse(mimetype='application/pdf')
    response['Cache-Control'] = ""
    response['Content-Disposition'] = "attachment; filename=%s" % filename
    
    response.write(open(filename).read())
    os.remove(filename)
    return response


def thepatientregister(title, indata=None, boxes=None):
    styleH3.fontName = 'Times-Bold'
    styleH3.alignment = TA_CENTER
    styleH5 = copy.copy(styleH3)
    styleH5.fontSize = 8
    styleN.fontSize = 8
    styleN.spaceAfter = 0
    styleN.spaceBefore = 0
    styleN2 = copy.copy(styleN)
    styleN2.alignment = TA_CENTER
    styleN3 = copy.copy(styleN)
    styleN3.alignment = TA_RIGHT

    rpt = ThePatient()
    cols = rpt.patient_register_columns()

    hdata = [Paragraph('%s' % title, styleH3)]
    hdata.extend((len(cols) - 1) * [''])
    data = [hdata]

    #styleN.borderWidth = 0
    #styleN.borderColor = colors.red 
    firstrow = [Paragraph(cols[0]['name'], styleH5)]
    firstrow.extend([Paragraph(col['name'], styleH5) for col in cols[1:]])
    data.append(firstrow)

    rowHeights = [None, 0.2 * inch]
    colWidths = [0.5 * inch, 1.5 * inch]
    colWidths.extend((len(cols) - 2) * [0.5 * inch])

    ts = [('SPAN', (0, 0), (len(cols) - 1, 0)),
                            ('LINEABOVE', (0, 1), (len(cols) - 1, 1), 1, \
                            colors.black),
                            ('LINEBELOW', (0, 1), (len(cols) - 1, 1), 1, \
                            colors.black),
                            ('INNERGRID', (0, 0), (-1, -1), 0.1, \
                            colors.lightgrey),\
                            ('BOX', (0, 0), (-1, -1), 0.1, \
                            colors.lightgrey)]
    if indata:
        for row in indata:
            ctx = Context({"object": row})
            values = [Paragraph(Template(cols[0]["bit"]).render(ctx), \
                                styleN)]
            values.extend([Paragraph(Template(cols[1]["bit"]).render(ctx), \
                                styleN)])
            values.extend([Paragraph(Template(col["bit"]).render(ctx), \
                                styleN2) for col in cols[2:]])
            data.append(values)
        rowHeights.extend(len(indata) * [0.2 * inch])

        tscount = 0
        for box in boxes:
            if tscount % 2:
                ts.append((('BOX', (0, box['top'] + 2), \
                        (-1, box['bottom'] + 2), 0.5, colors.black)))
            else:
                 ts.append((('BOX', (0, box['top'] + 2), \
                        (-1, box['bottom'] + 2), 0.5, colors.black)))
            ts.append((('BACKGROUND', (0, box['top'] + 2), \
                        (1, box['top'] + 2), colors.lightgrey)))
            tscount += 1
    tb = Table(data, colWidths=colWidths, rowHeights=rowHeights, repeatRows=2)
    tb.setStyle(TableStyle(ts))
    return tb

