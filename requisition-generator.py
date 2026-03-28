"""
Kedi Labs Veterinary Test Requisition Generator
Flask webhook server for generating professional test requisitions in PDF format
"""

import os
import json
import base64
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

# SKU to Test Panel Mapping
SKU_TO_TEST_MAP = {
    # IDEXX Panels - Each with shipping variants
    '90379999-DROPOFF': {
        'name': 'IDEXX COMP (Chemistry Panel)',
        'lab': 'IDEXX',
        'testCodes': ['COMP'],
        'specimenType': 'Serum',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 1,
        'shipping': 'dropoff'
    },
    '90379999-UPS': {
        'name': 'IDEXX COMP (Chemistry Panel)',
        'lab': 'IDEXX',
        'testCodes': ['COMP'],
        'specimenType': 'Serum',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 2,
        'shipping': 'ups'
    },
    '90379999-FEDEX': {
        'name': 'IDEXX COMP (Chemistry Panel)',
        'lab': 'IDEXX',
        'testCodes': ['COMP'],
        'specimenType': 'Serum',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 1,
        'shipping': 'fedex'
    },
    '48689999-DROPOFF': {
        'name': 'IDEXX CBC (Complete Blood Count)',
        'lab': 'IDEXX',
        'testCodes': ['CBC'],
        'specimenType': 'EDTA Blood',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 1,
        'shipping': 'dropoff'
    },
    '48689999-UPS': {
        'name': 'IDEXX CBC (Complete Blood Count)',
        'lab': 'IDEXX',
        'testCodes': ['CBC'],
        'specimenType': 'EDTA Blood',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 2,
        'shipping': 'ups'
    },
    '48689999-FEDEX': {
        'name': 'IDEXX CBC (Complete Blood Count)',
        'lab': 'IDEXX',
        'testCodes': ['CBC'],
        'specimenType': 'EDTA Blood',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 1,
        'shipping': 'fedex'
    },
    '48719999-DROPOFF': {
        'name': 'IDEXX Thyroid Panel (T4, Free T4, TSH)',
        'lab': 'IDEXX',
        'testCodes': ['T4', 'FT4', 'TSH'],
        'specimenType': 'Serum',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 1,
        'shipping': 'dropoff'
    },
    '48719999-UPS': {
        'name': 'IDEXX Thyroid Panel (T4, Free T4, TSH)',
        'lab': 'IDEXX',
        'testCodes': ['T4', 'FT4', 'TSH'],
        'specimenType': 'Serum',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 2,
        'shipping': 'ups'
    },
    '48719999-FEDEX': {
        'name': 'IDEXX Thyroid Panel (T4, Free T4, TSH)',
        'lab': 'IDEXX',
        'testCodes': ['T4', 'FT4', 'TSH'],
        'specimenType': 'Serum',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 1,
        'shipping': 'fedex'
    },
    '45559999-DROPOFF': {
        'name': 'IDEXX Urinalysis',
        'lab': 'IDEXX',
        'testCodes': ['UA'],
        'specimenType': 'Urine (midstream)',
        'specimenVolume': '10 mL min',
        'turnaroundDays': 1,
        'shipping': 'dropoff'
    },
    '45559999-UPS': {
        'name': 'IDEXX Urinalysis',
        'lab': 'IDEXX',
        'testCodes': ['UA'],
        'specimenType': 'Urine (midstream)',
        'specimenVolume': '10 mL min',
        'turnaroundDays': 2,
        'shipping': 'ups'
    },
    '45559999-FEDEX': {
        'name': 'IDEXX Urinalysis',
        'lab': 'IDEXX',
        'testCodes': ['UA'],
        'specimenType': 'Urine (midstream)',
        'specimenVolume': '10 mL min',
        'turnaroundDays': 1,
        'shipping': 'fedex'
    },
    '37929999-DROPOFF': {
        'name': 'IDEXX Lipid Panel',
        'lab': 'IDEXX',
        'testCodes': ['CHOL', 'TRIG', 'HDL'],
        'specimenType': 'Serum',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 1,
        'shipping': 'dropoff'
    },
    '37929999-UPS': {
        'name': 'IDEXX Lipid Panel',
        'lab': 'IDEXX',
        'testCodes': ['CHOL', 'TRIG', 'HDL'],
        'specimenType': 'Serum',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 2,
        'shipping': 'ups'
    },
    '37929999-FEDEX': {
        'name': 'IDEXX Lipid Panel',
        'lab': 'IDEXX',
        'testCodes': ['CHOL', 'TRIG', 'HDL'],
        'specimenType': 'Serum',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 1,
        'shipping': 'fedex'
    },
    '45459999-DROPOFF': {
        'name': 'IDEXX Electrolyte Panel',
        'lab': 'IDEXX',
        'testCodes': ['NA', 'K', 'CL', 'CO2'],
        'specimenType': 'Serum',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 1,
        'shipping': 'dropoff'
    },
    '45459999-UPS': {
        'name': 'IDEXX Electrolyte Panel',
        'lab': 'IDEXX',
        'testCodes': ['NA', 'K', 'CL', 'CO2'],
        'specimenType': 'Serum',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 2,
        'shipping': 'ups'
    },
    '45459999-FEDEX': {
        'name': 'IDEXX Electrolyte Panel',
        'lab': 'IDEXX',
        'testCodes': ['NA', 'K', 'CL', 'CO2'],
        'specimenType': 'Serum',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 1,
        'shipping': 'fedex'
    },
    '24483999-DROPOFF': {
        'name': 'IDEXX Liver Function Panel',
        'lab': 'IDEXX',
        'testCodes': ['ALT', 'AST', 'ALKP', 'TBIL'],
        'specimenType': 'Serum',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 1,
        'shipping': 'dropoff'
    },
    '24483999-UPS': {
        'name': 'IDEXX Liver Function Panel',
        'lab': 'IDEXX',
        'testCodes': ['ALT', 'AST', 'ALKP', 'TBIL'],
        'specimenType': 'Serum',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 2,
        'shipping': 'ups'
    },
    '24483999-FEDEX': {
        'name': 'IDEXX Liver Function Panel',
        'lab': 'IDEXX',
        'testCodes': ['ALT', 'AST', 'ALKP', 'TBIL'],
        'specimenType': 'Serum',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 1,
        'shipping': 'fedex'
    },

    # Antech Panels
    'UTID002': {
        'name': 'Antech Urinalysis with Culture',
        'lab': 'Antech',
        'testCodes': ['UA', 'URINE-CULT'],
        'specimenType': 'Urine (sterile, midstream)',
        'specimenVolume': '10 mL min',
        'turnaroundDays': 2,
        'shipping': 'fedex'
    },
    'UTIC002': {
        'name': 'Antech Therapeutic Drug Monitoring',
        'lab': 'Antech',
        'testCodes': ['TDM-PHENO', 'TDM-PHENOBARB'],
        'specimenType': 'Serum',
        'specimenVolume': '0.5 mL min',
        'turnaroundDays': 2,
        'shipping': 'fedex'
    },
    'FP002': {
        'name': 'Antech Fungal Panel (Dermatophyte)',
        'lab': 'Antech',
        'testCodes': ['DERMA-CULT'],
        'specimenType': 'Hair/Scale (sterile collection)',
        'specimenVolume': 'Direct collection',
        'turnaroundDays': 5,
        'shipping': 'fedex'
    },
    'OPGIA002': {
        'name': 'Antech Ophthalmology Panel',
        'lab': 'Antech',
        'testCodes': ['SCRAPE', 'STAIN'],
        'specimenType': 'Conjunctival scraping',
        'specimenVolume': 'Direct collection',
        'turnaroundDays': 2,
        'shipping': 'fedex'
    },
    'PPPS-001': {
        'name': 'Antech Parasite Panel',
        'lab': 'Antech',
        'testCodes': ['FECAL', 'PARASITE-ID'],
        'specimenType': 'Fecal (fresh)',
        'specimenVolume': '2-5g',
        'turnaroundDays': 1,
        'shipping': 'fedex'
    },

    # RealPCR Panels
    '2524': {
        'name': 'RealPCR Feline Infectious Peritonitis (FIP)',
        'lab': 'RealPCR',
        'testCodes': ['FIP-PCR'],
        'specimenType': 'Serum or Whole Blood',
        'specimenVolume': '0.5 mL',
        'turnaroundDays': 3,
        'shipping': 'fedex'
    },
    '2625': {
        'name': 'RealPCR Canine Pancreatitis',
        'lab': 'RealPCR',
        'testCodes': ['PANC-PCR'],
        'specimenType': 'Serum',
        'specimenVolume': '0.5 mL',
        'turnaroundDays': 3,
        'shipping': 'fedex'
    },
    '2627': {
        'name': 'RealPCR Feline Leukemia (FeLV)',
        'lab': 'RealPCR',
        'testCodes': ['FELV-PCR'],
        'specimenType': 'Whole Blood',
        'specimenVolume': '0.5 mL',
        'turnaroundDays': 2,
        'shipping': 'fedex'
    },
    '2512': {
        'name': 'RealPCR Feline Immunodeficiency (FIV)',
        'lab': 'RealPCR',
        'testCodes': ['FIV-PCR'],
        'specimenType': 'Whole Blood',
        'specimenVolume': '0.5 mL',
        'turnaroundDays': 2,
        'shipping': 'fedex'
    },
    '26251': {
        'name': 'RealPCR Canine Parvovirus',
        'lab': 'RealPCR',
        'testCodes': ['CPV-PCR'],
        'specimenType': 'Fecal',
        'specimenVolume': '1g',
        'turnaroundDays': 2,
        'shipping': 'fedex'
    },
    '51991': {
        'name': 'RealPCR Lyme Disease (Borrelia burgdorferi)',
        'lab': 'RealPCR',
        'testCodes': ['LYME-PCR'],
        'specimenType': 'Serum or Whole Blood',
        'specimenVolume': '0.5 mL',
        'turnaroundDays': 3,
        'shipping': 'fedex'
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


def get_test_info(sku):
    """Retrieve test information by SKU, with fallback logic"""
    if sku in SKU_TO_TEST_MAP:
        return SKU_TO_TEST_MAP[sku]

    # Fallback: Try to extract base SKU without shipping suffix
    for key, value in SKU_TO_TEST_MAP.items():
        if key.startswith(sku):
            return value

    # Last resort: Create generic entry
    return {
        'name': 'Unknown Test',
        'lab': 'Unknown',
        'testCodes': ['CUSTOM'],
        'specimenType': 'Varies',
        'specimenVolume': 'See instructions',
        'turnaroundDays': 3,
        'shipping': 'standard'
    }


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
    client_data = [
        ['CLIENT INFORMATION', 'PATIENT INFORMATION'],
        [
            f"Name: {data['customerFirstName']} {data['customerLastName']}\n"
            f"Phone: {data['customerPhone']}\n"
            f"Email: {data['customerEmail']}",
            f"Patient Name: {data['petName']}\n"
            f"Species: {data['species']}\n"
            f"Breed: {data['breed']}\n"
            f"Age: {data['age']}\n"
            f"Weight: {data['weight']} {data.get('weightUnit', 'lbs')}"
        ]
    ]

    if data.get('microchipNumber'):
        client_data[1][1] += f"\nMicrochip #: {data['microchipNumber']}"

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

    if test_info['shipping'] == 'dropoff':
        shipping_info = (
            "INSTRUCTIONS: This specimen requires immediate testing. Please deliver specimen to "
            "an IDEXX drop-off location immediately or within 2 hours of collection. "
            "Keep specimen at room temperature during transport."
        )
    elif test_info['shipping'] == 'ups':
        shipping_info = (
            "INSTRUCTIONS: Place specimen in provided transport tube with cold pack. "
            "Ship via UPS Next Day Air with signature required. "
            "Ensure delivery within 24 hours of collection."
        )
    else:
        shipping_info = (
            "INSTRUCTIONS: Place specimen in provided transport tube with ice pack. "
            "Ship via FedEx Overnight for immediate processing. "
            "Ensure delivery within 24 hours of collection."
        )

    story.append(Paragraph(shipping_info, normal_style))
    story.append(Spacer(1, 0.15*inch))

    # Footer
    footer_text = (
        f"Requisition Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}<br/>"
        f"Order ID: {data['orderId']}<br/>"
        f"<i>This is an automated requisition from Kedi Labs. Keep this form with your specimen.</i>"
    )
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
    client_data = [
        ['OWNER INFORMATION', 'PATIENT INFORMATION'],
        [
            f"Name: {data['customerFirstName']} {data['customerLastName']}\n"
            f"Phone: {data['customerPhone']}\n"
            f"Email: {data['customerEmail']}",
            f"Animal Name: {data['petName']}\n"
            f"Species: {data['species']}\n"
            f"Breed: {data['breed']}\n"
            f"Age: {data['age']}\n"
            f"Weight: {data['weight']} {data.get('weightUnit', 'lbs')}"
        ]
    ]

    if data.get('microchipNumber'):
        client_data[1][1] += f"\nMicrochip: {data['microchipNumber']}"

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
        "IMPORTANT: This specimen is being shipped via FedEx. A FedEx shipping label is included with this requisition. "
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
    footer_text = (
        f"Requisition Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}<br/>"
        f"Order ID: {data['orderId']}<br/>"
        f"<i>Provided by Kedi Labs | www.kedilabs.com</i>"
    )
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
    client_data = [
        ['OWNER INFORMATION', 'PATIENT INFORMATION'],
        [
            f"Name: {data['customerFirstName']} {data['customerLastName']}\n"
            f"Phone: {data['customerPhone']}\n"
            f"Email: {data['customerEmail']}",
            f"Patient Name: {data['petName']}\n"
            f"Species: {data['species']}\n"
            f"Breed: {data['breed']}\n"
            f"Age: {data['age']}\n"
            f"Weight: {data['weight']} {data.get('weightUnit', 'lbs')}"
        ]
    ]

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
    footer_text = (
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}<br/>"
        f"Order #: {data['orderId']}<br/>"
        f"<i>RealPCR Diagnostics via Kedi Labs</i>"
    )
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
    return jsonify({'status': 'ok', 'service': 'requisition-generator'}), 200


@app.route('/generate-requisition', methods=['POST'])
@require_auth
def generate_requisition():
    """
    Main webhook endpoint to generate test requisitions
    Receives order data from Make.com and generates appropriate PDF
    """
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ['orderId', 'sku', 'customerEmail', 'petName', 'species']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Get test information
        test_info = get_test_info(data['sku'])

        # Determine lab type and generate appropriate requisition
        lab = test_info['lab']

        if lab == 'IDEXX':
            pdf_buffer = generate_idexx_requisition(data, test_info)
            filename = f"IDEXX_Requisition_{data['orderId']}.pdf"
        elif lab == 'Antech':
            pdf_buffer = generate_antech_requisition(data, test_info)
            filename = f"Antech_Requisition_{data['orderId']}.pdf"
        else:  # RealPCR or other
            pdf_buffer = generate_realpcr_requisition(data, test_info)
            filename = f"RealPCR_Requisition_{data['orderId']}.pdf"

        # Convert to base64
        pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode('utf-8')

        # Save PDF to file system (optional, for archival)
        pdf_path = os.path.join(UPLOAD_FOLDER, filename)
        with open(pdf_path, 'wb') as f:
            f.write(pdf_buffer.getvalue())

        # Build response
        response = {
            'success': True,
            'orderId': data['orderId'],
            'testType': lab,
            'fileName': filename,
            'pdfBase64': pdf_base64,
            'pdfUrl': None,  # Can add URL if hosting PDFs
            'timestamp': datetime.now().isoformat()
        }

        # For Antech tests, include FedEx label info
        if lab == 'Antech':
            response['fedexLabelUrl'] = None  # Would be populated with actual label service
            response['fedexLabelBase64'] = None
            response['message'] = 'Antech requisition generated. FedEx label should be generated separately.'

        return jsonify(response), 200

    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON in request body'}), 400
    except Exception as e:
        return jsonify({'error': str(e), 'type': type(e).__name__}), 500


@app.route('/test-sku/<sku>', methods=['GET'])
def test_sku(sku):
    """Endpoint to test SKU lookup (for debugging)"""
    test_info = get_test_info(sku)
    return jsonify({
        'sku': sku,
        'found': sku in SKU_TO_TEST_MAP or any(key.startswith(sku) for key in SKU_TO_TEST_MAP),
        'testInfo': test_info
    }), 200


@app.route('/available-skus', methods=['GET'])
def available_skus():
    """List all available SKUs and tests"""
    return jsonify({
        'count': len(SKU_TO_TEST_MAP),
        'skus': list(SKU_TO_TEST_MAP.keys()),
        'summary': {
            'idexx': len([k for k in SKU_TO_TEST_MAP.keys() if 'IDEXX' in SKU_TO_TEST_MAP[k]['lab']]),
            'antech': len([k for k in SKU_TO_TEST_MAP.keys() if 'Antech' in SKU_TO_TEST_MAP[k]['lab']]),
            'realpcr': len([k for k in SKU_TO_TEST_MAP.keys() if 'RealPCR' in SKU_TO_TEST_MAP[k]['lab']])
        }
    }), 200


if __name__ == '__main__':
    # Development server
    app.run(host='0.0.0.0', port=5000, debug=True)
