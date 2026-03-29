"""
Kedi Labs Veterinary Test Requisition Generator
Flask webhook server for generating professional test requisitions in PDF format

Updated for Option B: Triggered by Airtable test activation (not Shopify order)
"""

import os
import json
import base64
import uuid
from datetime import datetime
from functools import wraps
from io import BytesIO

from flask import Flask, request, jsonify
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from flask_cors import CORS

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
WEBHOOK_SECRET = os.getenv('REQUISITION_WEBHOOK_SECRET', 'dev-secret-key')
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', '/tmp/requisitions')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── Test Name → Test Info Mapping ──
# Maps the test names from the Airtable activation form to lab-specific details.
# The keys here should match the "Test Name" multipleSelects values in Airtable.
TEST_NAME_MAP = {
    # IDEXX Tests
    'IDEXX COMP (Chemistry Panel)': {
        'lab': 'IDEXX',
        'testCodes': ['COMP'],
        'specimenType': 'Serum',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 1
    },
    'IDEXX CBC (Complete Blood Count)': {
        'lab': 'IDEXX',
        'testCodes': ['CBC'],
        'specimenType': 'EDTA Blood',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 1
    },
    'IDEXX Thyroid Panel (T4, Free T4, TSH)': {
        'lab': 'IDEXX',
        'testCodes': ['T4', 'FT4', 'TSH'],
        'specimenType': 'Serum',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 1
    },
    'IDEXX Urinalysis': {
        'lab': 'IDEXX',
        'testCodes': ['UA'],
        'specimenType': 'Urine (midstream)',
        'specimenVolume': '10 mL min',
        'turnaroundDays': 1
    },
    'IDEXX Lipid Panel': {
        'lab': 'IDEXX',
        'testCodes': ['CHOL', 'TRIG', 'HDL'],
        'specimenType': 'Serum',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 1
    },
    'IDEXX Electrolyte Panel': {
        'lab': 'IDEXX',
        'testCodes': ['NA', 'K', 'CL', 'CO2'],
        'specimenType': 'Serum',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 1
    },
    'IDEXX Liver Function Panel': {
        'lab': 'IDEXX',
        'testCodes': ['ALT', 'AST', 'ALKP', 'TBIL'],
        'specimenType': 'Serum',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 1
    },

    # Antech Tests
    'Antech Urinalysis with Culture': {
        'lab': 'Antech',
        'testCodes': ['UA', 'URINE-CULT'],
        'specimenType': 'Urine (sterile, midstream)',
        'specimenVolume': '10 mL min',
        'turnaroundDays': 2
    },
    'Antech Therapeutic Drug Monitoring': {
        'lab': 'Antech',
        'testCodes': ['TDM-PHENO', 'TDM-PHENOBARB'],
        'specimenType': 'Serum',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 2
    },
    'Antech Fungal Panel (Dermatophyte)': {
        'lab': 'Antech',
        'testCodes': ['DERMA-CULT'],
        'specimenType': 'Hair/Scale (sterile collection)',
        'specimenVolume': 'Direct collection',
        'turnaroundDays': 5
    },
    'Antech Ophthalmology Panel': {
        'lab': 'Antech',
        'testCodes': ['SCRAPE', 'STAIN'],
        'specimenType': 'Conjunctival scraping',
        'specimenVolume': 'Direct collection',
        'turnaroundDays': 2
    },
    'Antech Parasite Panel': {
        'lab': 'Antech',
        'testCodes': ['FECAL', 'PARASITE-ID'],
        'specimenType': 'Fecal (fresh)',
        'specimenVolume': '2-5g',
        'turnaroundDays': 1
    },

    # RealPCR Tests
    'RealPCR Feline Infectious Peritonitis (FIP)': {
        'lab': 'RealPCR',
        'testCodes': ['FIP-PCR'],
        'specimenType': 'Serum or Whole Blood',
        'specimenVolume': '0.5 mL',
        'turnaroundDays': 3
    },
    'RealPCR Canine Pancreatitis': {
        'lab': 'RealPCR',
        'testCodes': ['PANC-PCR'],
        'specimenType': 'Serum',
        'specimenVolume': '0.5 mL',
        'turnaroundDays': 3
    },
    'RealPCR Feline Leukemia (FeLV)': {
        'lab': 'RealPCR',
        'testCodes': ['FELV-PCR'],
        'specimenType': 'Whole Blood',
        'specimenVolume': '0.5 mL',
        'turnaroundDays': 2
    },
    'RealPCR Feline Immunodeficiency (FIV)': {
        'lab': 'RealPCR',
        'testCodes': ['FIV-PCR'],
        'specimenType': 'Whole Blood',
        'specimenVolume': '0.5 mL',
        'turnaroundDays': 2
    },
    'RealPCR Canine Parvovirus': {
        'lab': 'RealPCR',
        'testCodes': ['CPV-PCR'],
        'specimenType': 'Fecal',
        'specimenVolume': '1g',
        'turnaroundDays': 2
    },
    'RealPCR Lyme Disease (Borrelia burgdorferi)': {
        'lab': 'RealPCR',
        'testCodes': ['LYME-PCR'],
        'specimenType': 'Serum or Whole Blood',
        'specimenVolume': '0.5 mL',
        'turnaroundDays': 3
    }
}


def require_auth(f):
    """Decorator to verify webhook authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.replace('Bearer ', '')

        if token != WEBHOOK_SECRET:
            return jsonify({'error': 'Unauthorized'}), 401

        return f(*args, **kwargs)
    return decorated_function


def resolve_test_info(test_name, lab_vendor=None):
    """
    Resolve test info from test name (as selected in the Airtable activation form).
    Falls back to a generic entry if no exact match is found.
    """
    # Direct match
    if test_name in TEST_NAME_MAP:
        info = TEST_NAME_MAP[test_name].copy()
        info['name'] = test_name
        return info

    # Fuzzy match: check if the test_name is a substring of any key or vice versa
    test_lower = test_name.lower()
    for key, value in TEST_NAME_MAP.items():
        if test_lower in key.lower() or key.lower() in test_lower:
            info = value.copy()
            info['name'] = key
            return info

    # Fallback: build a generic entry using lab_vendor if provided
    lab = lab_vendor or 'Unknown'
    return {
        'name': test_name,
        'lab': lab,
        'testCodes': ['CUSTOM'],
        'specimenType': 'See kit instructions',
        'specimenVolume': 'See kit instructions',
        'turnaroundDays': 3
    }


def calculate_pet_age(birthday_str):
    """Calculate age string from a birthday date string (ISO format or common formats)"""
    if not birthday_str:
        return 'Not provided'
    try:
        # Try ISO format first (YYYY-MM-DD)
        bday = datetime.strptime(birthday_str[:10], '%Y-%m-%d')
        today = datetime.now()
        years = today.year - bday.year
        months = today.month - bday.month
        if months < 0:
            years -= 1
            months += 12
        if years > 0:
            return f"{years} year(s), {months} month(s)"
        else:
            return f"{months} month(s)"
    except (ValueError, TypeError):
        return birthday_str  # Return as-is if we can't parse


def generate_idexx_requisition(data, test_info):
    """Generate IDEXX-style professional requisition PDF"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch,
        leftMargin=0.75*inch,
        rightMargin=0.75*inch
    )

    story = []
    styles = getSampleStyleSheet()

    # Define custom styles
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Normal'],
        fontSize=18,
        textColor=colors.HexColor('#003366'),
        spaceAfter=6,
        fontName='Helvetica-Bold'
    )

    subheader_style = ParagraphStyle(
        'SubHeader',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#666666'),
        spaceAfter=4,
        fontName='Helvetica-Bold'
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=2
    )

    # Header
    story.append(Paragraph("IDEXX LABORATORIES", header_style))
    story.append(Paragraph("Laboratory Test Requisition Form", subheader_style))
    story.append(Spacer(1, 0.15*inch))

    # Client/Patient Information Table
    patient_info = (
        f"Patient Name: {data.get('petName', '')}\n"
        f"Species: {data.get('species', '')}\n"
        f"Breed: {data.get('breed', 'Not specified')}\n"
        f"Gender: {data.get('gender', 'Not specified')}\n"
        f"Age: {data.get('age', 'Not provided')}"
    )

    client_data = [
        ['CLIENT INFORMATION', 'PATIENT INFORMATION'],
        [
            f"Name: {data.get('customerFirstName', '')} {data.get('customerLastName', '')}\n"
            f"Phone: {data.get('customerPhone', 'N/A')}\n"
            f"Email: {data.get('customerEmail', '')}",
            patient_info
        ]
    ]

    if data.get('vetEmail'):
        client_data[1][0] += f"\nVeterinarian: {data['vetEmail']}"

    client_table = Table(client_data, colWidths=[3.25*inch, 3.25*inch])
    client_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E8F0F5')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#003366')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F8F8')])
    ]))
    story.append(client_table)
    story.append(Spacer(1, 0.2*inch))

    # Test Information
    story.append(Paragraph("TEST INFORMATION", subheader_style))
    test_data = [
        ['Test Code', ', '.join(test_info['testCodes'])],
        ['Test Name', test_info['name']],
        ['Specimen Type', test_info['specimenType']],
        ['Specimen Volume', test_info['specimenVolume']],
        ['Expected Turnaround', f"{test_info['turnaroundDays']} business day(s)"]
    ]

    test_table = Table(test_data, colWidths=[2*inch, 4.5*inch])
    test_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8F0F5')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#003366')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey)
    ]))
    story.append(test_table)
    story.append(Spacer(1, 0.2*inch))

    # Clinical Information
    story.append(Paragraph("CLINICAL INFORMATION", subheader_style))

    clinical_info = "Please include any relevant clinical signs or conditions:\n"
    if data.get('conditions'):
        clinical_info += f"Conditions: {data['conditions']}\n"
    if data.get('medications'):
        clinical_info += f"Current Medications: {data['medications']}\n"

    clinical_info += "\nAdditional Notes: ___________________________________________"

    story.append(Paragraph(clinical_info, normal_style))
    story.append(Spacer(1, 0.15*inch))

    # Specimen Handling Instructions
    story.append(Paragraph("SPECIMEN HANDLING & SHIPPING", subheader_style))

    shipping_info = (
        "INSTRUCTIONS: Place specimen in provided transport tube with ice pack. "
        "Ship using the shipping label included in your test kit. "
        "IDEXX provides pre-paid shipping labels for specimen delivery. "
        "Ensure delivery within 24 hours of collection."
    )

    story.append(Paragraph(shipping_info, normal_style))
    story.append(Spacer(1, 0.15*inch))

    # Footer
    req_id = data.get('requisitionId', 'N/A')
    activation_code = data.get('activationCode', '')
    footer_text = (
        f"Requisition Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}<br/>"
        f"Requisition ID: {req_id}<br/>"
    )
    if activation_code:
        footer_text += f"Activation Code: {activation_code}<br/>"
    footer_text += "<i>This is an automated requisition from Kedi Labs. Keep this form with your specimen.</i>"

    story.append(Paragraph(footer_text, ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER
    )))

    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_antech_requisition(data, test_info):
    """Generate Antech-style professional requisition PDF"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch,
        leftMargin=0.75*inch,
        rightMargin=0.75*inch
    )

    story = []
    styles = getSampleStyleSheet()

    # Define custom styles
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Normal'],
        fontSize=18,
        textColor=colors.HexColor('#8B0000'),
        spaceAfter=6,
        fontName='Helvetica-Bold'
    )

    subheader_style = ParagraphStyle(
        'SubHeader',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#666666'),
        spaceAfter=4,
        fontName='Helvetica-Bold'
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=2
    )

    # Header
    story.append(Paragraph("ANTECH DIAGNOSTICS", header_style))
    story.append(Paragraph("Laboratory Test Requisition Form", subheader_style))
    story.append(Spacer(1, 0.15*inch))

    # Client/Patient Information Table
    patient_info = (
        f"Animal Name: {data.get('petName', '')}\n"
        f"Species: {data.get('species', '')}\n"
        f"Breed: {data.get('breed', 'Not specified')}\n"
        f"Gender: {data.get('gender', 'Not specified')}\n"
        f"Age: {data.get('age', 'Not provided')}"
    )

    client_data = [
        ['OWNER INFORMATION', 'PATIENT INFORMATION'],
        [
            f"Name: {data.get('customerFirstName', '')} {data.get('customerLastName', '')}\n"
            f"Phone: {data.get('customerPhone', 'N/A')}\n"
            f"Email: {data.get('customerEmail', '')}",
            patient_info
        ]
    ]

    if data.get('vetEmail'):
        client_data[1][0] += f"\nVeterinarian: {data['vetEmail']}"

    client_table = Table(client_data, colWidths=[3.25*inch, 3.25*inch])
    client_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FFE6E6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#8B0000')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F8F8')])
    ]))
    story.append(client_table)
    story.append(Spacer(1, 0.2*inch))

    # Test Information
    story.append(Paragraph("TEST INFORMATION", subheader_style))
    test_data = [
        ['Test Code(s)', ', '.join(test_info['testCodes'])],
        ['Test Name', test_info['name']],
        ['Specimen Type', test_info['specimenType']],
        ['Specimen Volume Required', test_info['specimenVolume']],
        ['Expected TAT', f"{test_info['turnaroundDays']} business day(s)"]
    ]

    test_table = Table(test_data, colWidths=[2*inch, 4.5*inch])
    test_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#FFE6E6')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#8B0000')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey)
    ]))
    story.append(test_table)
    story.append(Spacer(1, 0.2*inch))

    # Clinical History
    story.append(Paragraph("CLINICAL HISTORY", subheader_style))

    clinical_info = "Clinical signs or reason for testing:\n"
    if data.get('conditions'):
        clinical_info += f"{data['conditions']}\n"
    else:
        clinical_info += "____________________________________________________________________________________________\n"

    if data.get('medications'):
        clinical_info += f"\nCurrent Medications:\n{data['medications']}\n"
    else:
        clinical_info += "\nCurrent Medications: _________________________________________________________________\n"

    story.append(Paragraph(clinical_info, normal_style))
    story.append(Spacer(1, 0.15*inch))

    # Shipping Instructions
    story.append(Paragraph("SHIPMENT INSTRUCTIONS", subheader_style))

    shipping_text = (
        "IMPORTANT: This specimen is being shipped via FedEx. A FedEx shipping label is included "
        "with your test kit, or will be emailed to you separately. "
        "Follow these steps:\n\n"
        "1. Collect specimen according to type specified above\n"
        "2. Place specimen in provided transport container\n"
        "3. Affix the FedEx label to the outside of the package\n"
        "4. Ship via FedEx Overnight (label is pre-paid)\n"
        "5. Keep tracking number for your records\n\n"
        "For specimen collection details, contact Antech Diagnostics at 1-800-826-2438"
    )

    story.append(Paragraph(shipping_text, normal_style))
    story.append(Spacer(1, 0.15*inch))

    # Footer
    req_id = data.get('requisitionId', 'N/A')
    activation_code = data.get('activationCode', '')
    footer_text = (
        f"Requisition Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}<br/>"
        f"Requisition ID: {req_id}<br/>"
    )
    if activation_code:
        footer_text += f"Activation Code: {activation_code}<br/>"
    footer_text += "<i>Provided by Kedi Labs | www.kedilabs.com</i>"

    story.append(Paragraph(footer_text, ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER
    )))

    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_realpcr_requisition(data, test_info):
    """Generate RealPCR-style professional requisition PDF"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch,
        leftMargin=0.75*inch,
        rightMargin=0.75*inch
    )

    story = []
    styles = getSampleStyleSheet()

    # Define custom styles
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Normal'],
        fontSize=18,
        textColor=colors.HexColor('#1F4788'),
        spaceAfter=6,
        fontName='Helvetica-Bold'
    )

    subheader_style = ParagraphStyle(
        'SubHeader',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#666666'),
        spaceAfter=4,
        fontName='Helvetica-Bold'
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=2
    )

    # Header
    story.append(Paragraph("REALPCR DIAGNOSTICS", header_style))
    story.append(Paragraph("PCR Testing Requisition Form", subheader_style))
    story.append(Spacer(1, 0.15*inch))

    # Client/Patient Information Table
    patient_info = (
        f"Patient Name: {data.get('petName', '')}\n"
        f"Species: {data.get('species', '')}\n"
        f"Breed: {data.get('breed', 'Not specified')}\n"
        f"Gender: {data.get('gender', 'Not specified')}\n"
        f"Age: {data.get('age', 'Not provided')}"
    )

    client_data = [
        ['OWNER INFORMATION', 'PATIENT INFORMATION'],
        [
            f"Name: {data.get('customerFirstName', '')} {data.get('customerLastName', '')}\n"
            f"Phone: {data.get('customerPhone', 'N/A')}\n"
            f"Email: {data.get('customerEmail', '')}",
            patient_info
        ]
    ]

    if data.get('vetEmail'):
        client_data[1][0] += f"\nVeterinarian: {data['vetEmail']}"

    client_table = Table(client_data, colWidths=[3.25*inch, 3.25*inch])
    client_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E6EAF2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1F4788')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F8F8')])
    ]))
    story.append(client_table)
    story.append(Spacer(1, 0.2*inch))

    # Test Information
    story.append(Paragraph("PCR TEST INFORMATION", subheader_style))
    test_data = [
        ['Test Code', ', '.join(test_info['testCodes'])],
        ['Test Name', test_info['name']],
        ['Specimen Type', test_info['specimenType']],
        ['Specimen Volume', test_info['specimenVolume']],
        ['Turnaround Time', f"{test_info['turnaroundDays']} business days"]
    ]

    test_table = Table(test_data, colWidths=[2*inch, 4.5*inch])
    test_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E6EAF2')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1F4788')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey)
    ]))
    story.append(test_table)
    story.append(Spacer(1, 0.2*inch))

    # Clinical Notes
    story.append(Paragraph("CLINICAL NOTES", subheader_style))

    clinical_text = "Clinical presentation and reason for PCR testing:\n"
    if data.get('conditions'):
        clinical_text += f"{data['conditions']}\n"
    else:
        clinical_text += "____________________________________________________________________________________________\n"

    story.append(Paragraph(clinical_text, normal_style))
    story.append(Spacer(1, 0.15*inch))

    # Specimen Collection Instructions
    story.append(Paragraph("SPECIMEN COLLECTION & SHIPPING", subheader_style))

    specimen_text = (
        f"Specimen Type Required: {test_info['specimenType']}\n"
        f"Volume Required: {test_info['specimenVolume']}\n\n"
        "IMPORTANT: Use only sterile collection supplies. Do not contaminate the specimen. "
        "Ship via FedEx Overnight with ice pack. Results will be emailed upon completion."
    )

    story.append(Paragraph(specimen_text, normal_style))
    story.append(Spacer(1, 0.15*inch))

    # Footer
    req_id = data.get('requisitionId', 'N/A')
    activation_code = data.get('activationCode', '')
    footer_text = (
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}<br/>"
        f"Requisition ID: {req_id}<br/>"
    )
    if activation_code:
        footer_text += f"Activation Code: {activation_code}<br/>"
    footer_text += "<i>RealPCR Diagnostics via Kedi Labs</i>"

    story.append(Paragraph(footer_text, ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER
    )))

    doc.build(story)
    buffer.seek(0)
    return buffer


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'service': 'requisition-generator',
        'version': '2.0-airtable',
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/generate-requisition', methods=['POST'])
@require_auth
def generate_requisition():
    """
    Main webhook endpoint to generate test requisitions.

    Option B flow: Triggered by Make.com when a new record appears in
    the Airtable "Customer Test Activations" table.

    Expected JSON payload (mapped from Airtable fields by Make.com):
    {
        "customerFirstName": "Jane",
        "customerLastName": "Smith",
        "customerEmail": "jane@example.com",
        "customerPhone": "555-1234",
        "petName": "Buddy",
        "species": "Canine",
        "breed": "Golden Retriever",
        "gender": "Male",
        "birthday": "2020-03-15",
        "testName": "IDEXX CBC (Complete Blood Count)",
        "labVendor": "IDEXX",
        "activationCode": "KL-ABC123",
        "vetEmail": "drjones@vetclinic.com",
        "airtableRecordId": "recXYZ123"
    }
    """
    try:
        data = request.get_json()

        # Validate required fields for Airtable activation flow
        required_fields = ['customerEmail', 'petName', 'species', 'testName']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Generate a requisition ID
        req_id = f"KL-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        data['requisitionId'] = req_id

        # Calculate age from birthday if provided
        if data.get('birthday') and not data.get('age'):
            data['age'] = calculate_pet_age(data['birthday'])
        elif not data.get('age'):
            data['age'] = 'Not provided'

        # Handle test name — could be a single string or comma-separated list
        test_name = data['testName']
        if isinstance(test_name, list):
            test_name = test_name[0]  # Use first test for primary requisition

        # Resolve test info from the test name
        lab_vendor = data.get('labVendor', '')
        if isinstance(lab_vendor, list):
            lab_vendor = lab_vendor[0] if lab_vendor else ''
        test_info = resolve_test_info(test_name, lab_vendor)

        # Determine lab and generate PDF
        lab = test_info['lab']

        if lab == 'IDEXX':
            pdf_buffer = generate_idexx_requisition(data, test_info)
            filename = f"IDEXX_Requisition_{req_id}.pdf"
        elif lab == 'Antech':
            pdf_buffer = generate_antech_requisition(data, test_info)
            filename = f"Antech_Requisition_{req_id}.pdf"
        else:  # RealPCR or other
            pdf_buffer = generate_realpcr_requisition(data, test_info)
            filename = f"RealPCR_Requisition_{req_id}.pdf"

        # Convert to base64 for Make.com to attach to email / Airtable
        pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode('utf-8')

        # Save PDF to file system (archival)
        pdf_path = os.path.join(UPLOAD_FOLDER, filename)
        with open(pdf_path, 'wb') as f:
            f.write(pdf_buffer.getvalue())

        # Build response — Make.com will use this to:
        # 1. Email the PDF to the pet owner
        # 2. Update the Airtable "ST - Lab Requisitions" table
        response = {
            'success': True,
            'requisitionId': req_id,
            'lab': lab,
            'testName': test_info['name'],
            'testCodes': test_info['testCodes'],
            'fileName': filename,
            'pdfBase64': pdf_base64,
            'petName': data.get('petName'),
            'ownerEmail': data.get('customerEmail'),
            'activationCode': data.get('activationCode', ''),
            'airtableRecordId': data.get('airtableRecordId', ''),
            'timestamp': datetime.now().isoformat()
        }

        # For Antech tests, note shipping label info
        if lab == 'Antech':
            response['shippingNote'] = (
                'Antech requisition generated. FedEx shipping label should be '
                'included in the test kit or emailed separately.'
            )

        return jsonify(response), 200

    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON in request body'}), 400
    except Exception as e:
        return jsonify({'error': str(e), 'type': type(e).__name__}), 500


@app.route('/available-tests', methods=['GET'])
def available_tests():
    """List all available test names and their lab info"""
    tests = []
    for name, info in TEST_NAME_MAP.items():
        tests.append({
            'testName': name,
            'lab': info['lab'],
            'testCodes': info['testCodes'],
            'specimenType': info['specimenType'],
            'turnaroundDays': info['turnaroundDays']
        })

    return jsonify({
        'count': len(tests),
        'tests': tests,
        'summary': {
            'idexx': len([t for t in tests if t['lab'] == 'IDEXX']),
            'antech': len([t for t in tests if t['lab'] == 'Antech']),
            'realpcr': len([t for t in tests if t['lab'] == 'RealPCR'])
        }
    }), 200


if __name__ == '__main__':
    # Development server
    app.run(host='0.0.0.0', port=5000, debug=True)
