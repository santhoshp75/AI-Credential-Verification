from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_file
)

import sqlite3
import uuid
import hashlib
import os
import re
import qrcode
import pytesseract

from PIL import Image, ImageEnhance, ImageFilter
from werkzeug.utils import secure_filename
from datetime import datetime
from io import BytesIO


# =========================================================
# APP CONFIG
# =========================================================

app = Flask(__name__)

app.secret_key = "AI_DIGITAL_CREDENTIAL_SECRET_2026"

BASE_DIR = app.root_path

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "uploads"
)

QR_FOLDER = os.path.join(
    BASE_DIR,
    "static",
    "qr_codes"
)

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

os.makedirs(
    QR_FOLDER,
    exist_ok=True
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# =========================================================
# TESSERACT CONFIG
# =========================================================

if os.name == "nt":

    TESSERACT_PATH = os.environ.get(
        "TESSERACT_CMD",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )

else:

    TESSERACT_PATH = os.environ.get(
        "TESSERACT_CMD",
        "tesseract"
    )

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


# =========================================================
# ALLOWED FILE TYPES
# =========================================================

ALLOWED_EXTENSIONS = {
    "pdf",
    "png",
    "jpg",
    "jpeg"
}


def allowed_file(filename):

    return (
        "." in filename
        and
        filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# =========================================================
# DATABASE
# =========================================================

DB_PATH = os.path.join(
    BASE_DIR,
    "database.db"
)


def get_db():

    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    return conn


# =========================================================
# ADD COLUMN IF MISSING
# =========================================================

def add_column_if_missing(
    conn,
    table,
    column,
    definition
):

    columns = {
        row["name"]
        for row in conn.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    }

    if column not in columns:

        conn.execute(
            f"""
            ALTER TABLE {table}
            ADD COLUMN {column} {definition}
            """
        )


# =========================================================
# CREATE DATABASE
# =========================================================

def create_database():

    conn = get_db()

    # =====================================================
    # USERS TABLE
    # =====================================================

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            email TEXT UNIQUE NOT NULL,

            password TEXT NOT NULL,

            credential_id TEXT UNIQUE NOT NULL,

            certificate_type TEXT NOT NULL,

            certificate_title TEXT NOT NULL,

            organization TEXT NOT NULL,

            issue_date TEXT NOT NULL

        )
        """
    )

    add_column_if_missing(
        conn,
        "users",
        "certificate_file",
        "TEXT"
    )

    add_column_if_missing(
        conn,
        "users",
        "validation_code",
        "TEXT"
    )


    # =====================================================
    # ADMINS TABLE
    # =====================================================

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admins (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            username TEXT UNIQUE NOT NULL,

            password TEXT NOT NULL

        )
        """
    )


    # =====================================================
    # DEFAULT ADMIN
    # =====================================================

    admin = conn.execute(
        """
        SELECT *
        FROM admins
        WHERE username = ?
        """,
        ("admin",)
    ).fetchone()


    if admin is None:

        conn.execute(
            """
            INSERT INTO admins
            (
                username,
                password
            )
            VALUES (?, ?)
            """,
            (
                "admin",
                "admin123"
            )
        )


    # =====================================================
    # CERTIFICATE UPLOADS
    # =====================================================

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS certificate_uploads (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            credential_id TEXT,

            filename TEXT NOT NULL,

            file_path TEXT NOT NULL,

            uploaded_at TEXT NOT NULL

        )
        """
    )


    # =====================================================
    # VERIFICATION HISTORY
    # =====================================================

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS verification_history (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            certificate_id INTEGER,

            validation_code TEXT,

            status TEXT NOT NULL,

            method TEXT NOT NULL DEFAULT 'SYSTEM',

            verified_at TEXT NOT NULL,

            credential_id TEXT,

            verification_method TEXT

        )
        """
    )

    add_column_if_missing(
        conn,
        "verification_history",
        "certificate_id",
        "INTEGER"
    )

    add_column_if_missing(
        conn,
        "verification_history",
        "validation_code",
        "TEXT"
    )

    add_column_if_missing(
        conn,
        "verification_history",
        "credential_id",
        "TEXT"
    )

    add_column_if_missing(
        conn,
        "verification_history",
        "verification_method",
        "TEXT"
    )


    conn.commit()

    conn.close()


# =========================================================
# CREATE DATABASE ON START
# =========================================================

create_database()


# =========================================================
# GENERATE QR CODE
# =========================================================

def generate_qr(credential_id):

    verification_url = (
        "https://ai-credential-verification.onrender.com/"
        f"verify/{credential_id}"
    )

    qr = qrcode.make(
        verification_url
    )

    qr_path = os.path.join(
        QR_FOLDER,
        f"{credential_id}.png"
    )

    qr.save(qr_path)

    return qr_path


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# REGISTER
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "GET":

        return render_template(
            "register.html"
        )


    name = request.form.get(
        "name",
        ""
    ).strip()

    email = request.form.get(
        "email",
        ""
    ).strip()

    password = request.form.get(
        "password",
        ""
    )


    if not name or not email or not password:

        return render_template(
            "register.html",
            error="Please fill all required fields."
        )


    credential_id = (
        "CRED-2026-"
        +
        uuid.uuid4().hex[:8].upper()
    )


    conn = get_db()


    try:

        conn.execute(
            """
            INSERT INTO users
            (
                name,
                email,
                password,
                credential_id,
                certificate_type,
                certificate_title,
                organization,
                issue_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                email,
                password,
                credential_id,
                "Certificate",
                "Digital Credential",
                "Not Specified",
                datetime.now().strftime(
                    "%Y-%m-%d"
                )
            )
        )

        conn.commit()

        conn.close()

        return redirect(
            url_for("home")
        )


    except sqlite3.IntegrityError:

        conn.close()

        return render_template(
            "register.html",
            error="Email already registered."
        )


    except Exception as e:

        conn.close()

        print(
            "REGISTER ERROR:",
            e
        )

        return render_template(
            "register.html",
            error="Unable to create account."
        )


# =========================================================
# STUDENT LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["POST"]
)
def login():

    email = request.form.get(
        "email",
        ""
    ).strip()

    password = request.form.get(
        "password",
        ""
    )


    conn = get_db()


    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE email = ?
        AND password = ?
        """,
        (
            email,
            password
        )
    ).fetchone()


    conn.close()


    if user:

        session["student_id"] = user["id"]

        session["student_name"] = user["name"]

        session["student_email"] = user["email"]

        return redirect(
            url_for("dashboard")
        )


    return """
    <h2>Invalid Email or Password</h2>
    <a href="/">Back</a>
    """


# =========================================================
# STUDENT DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "student_id" not in session:

        return redirect(
            url_for("home")
        )


    conn = get_db()


    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (
            session["student_id"],
        )
    ).fetchone()


    if not user:

        conn.close()

        return redirect(
            url_for("home")
        )


    history = conn.execute(
        """
        SELECT *
        FROM verification_history
        WHERE credential_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (
            user["credential_id"],
        )
    ).fetchone()


    upload_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM certificate_uploads
        WHERE credential_id = ?
        """,
        (
            user["credential_id"],
        )
    ).fetchone()[0]


    conn.close()


    return render_template(
        "dashboard.html",
        user=dict(user),
        history=dict(history)
        if history
        else None,
        upload_count=upload_count
    )


# =========================================================
# STUDENT CERTIFICATE
# =========================================================

@app.route("/certificate")
def certificate():

    if "student_id" not in session:

        return redirect(
            url_for("home")
        )


    conn = get_db()


    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (
            session["student_id"],
        )
    ).fetchone()


    conn.close()


    if not user:

        return redirect(
            url_for("home")
        )


    qr_path = generate_qr(
        user["credential_id"]
    )


    return render_template(
        "certificate.html",
        user=dict(user),
        qr_code=f"{user['credential_id']}.png",
        qr_path=qr_path
    )


# =========================================================
# DOWNLOAD GENERATED CERTIFICATE
# =========================================================

@app.route("/download-certificate")
def download_certificate():

    if "student_id" not in session:

        return redirect(
            url_for("home")
        )


    conn = get_db()


    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (
            session["student_id"],
        )
    ).fetchone()


    conn.close()


    if not user:

        return redirect(
            url_for("home")
        )


    try:

        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm

    except ImportError:

        return """
        <h2>ReportLab is missing.</h2>
        <p>Run: pip install reportlab</p>
        """


    pdf = BytesIO()


    document = canvas.Canvas(
        pdf,
        pagesize=A4
    )


    width, height = A4


    # =====================================================
    # TITLE
    # =====================================================

    document.setFont(
        "Helvetica-Bold",
        24
    )

    document.drawCentredString(
        width / 2,
        height - 45 * mm,
        "AI DIGITAL CREDENTIAL"
    )


    document.setFont(
        "Helvetica-Bold",
        20
    )

    document.drawCentredString(
        width / 2,
        height - 60 * mm,
        "CERTIFICATE"
    )


    document.setFont(
        "Helvetica",
        12
    )

    document.drawCentredString(
        width / 2,
        height - 82 * mm,
        "This certificate is proudly presented to"
    )


    document.setFont(
        "Helvetica-Bold",
        22
    )

    document.drawCentredString(
        width / 2,
        height - 98 * mm,
        user["name"]
    )


    # =====================================================
    # DETAILS
    # =====================================================

    y = height - 125 * mm


    details = [

        (
            "Certificate Type",
            user["certificate_type"]
        ),

        (
            "Certificate Title",
            user["certificate_title"]
        ),

        (
            "Issuing Organization",
            user["organization"]
        ),

        (
            "Issue Date",
            user["issue_date"]
        ),

        (
            "Credential ID",
            user["credential_id"]
        )

    ]


    for label, value in details:

        document.setFont(
            "Helvetica-Bold",
            11
        )

        document.drawString(
            40 * mm,
            y,
            label + ":"
        )

        document.setFont(
            "Helvetica",
            11
        )

        document.drawString(
            90 * mm,
            y,
            str(value)
        )

        y -= 13 * mm


    # =====================================================
    # QR CODE
    # =====================================================

    qr_path = generate_qr(
        user["credential_id"]
    )


    if os.path.exists(qr_path):

        document.drawImage(
            qr_path,
            width - 65 * mm,
            35 * mm,
            width=40 * mm,
            height=40 * mm
        )


    # =====================================================
    # FOOTER
    # =====================================================

    document.setFont(
        "Helvetica-Bold",
        14
    )

    document.drawCentredString(
        width / 2,
        45 * mm,
        "AUTHENTIC DIGITAL CREDENTIAL"
    )


    document.setFont(
        "Helvetica",
        9
    )

    document.drawCentredString(
        width / 2,
        30 * mm,
        "AI Digital Credential Verification System"
    )


    document.save()


    pdf.seek(0)


    return send_file(
        pdf,
        as_attachment=True,
        download_name=(
            user["credential_id"]
            +
            ".pdf"
        ),
        mimetype="application/pdf"
    )


# =========================================================
# DOWNLOAD ORIGINAL CERTIFICATE
# =========================================================

@app.route(
    "/download-original/<credential_id>"
)
def download_original(credential_id):

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )


    conn = get_db()


    upload = conn.execute(
        """
        SELECT *
        FROM certificate_uploads
        WHERE credential_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (
            credential_id,
        )
    ).fetchone()


    conn.close()


    if not upload:

        return (
            "Original certificate has not been uploaded.",
            404
        )


    file_path = upload["file_path"]


    if not os.path.isabs(file_path):

        file_path = os.path.join(
            BASE_DIR,
            file_path
        )


    if not os.path.exists(file_path):

        return (
            "Original certificate file not found.",
            404
        )


    return send_file(
        file_path,
        as_attachment=True,
        download_name=upload["filename"]
    )


# =========================================================
# VIEW ORIGINAL CERTIFICATE
# =========================================================

@app.route(
    "/view-original/<credential_id>"
)
def view_original(credential_id):

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )


    conn = get_db()


    upload = conn.execute(
        """
        SELECT *
        FROM certificate_uploads
        WHERE credential_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (
            credential_id,
        )
    ).fetchone()


    conn.close()


    if not upload:

        return (
            "Original certificate has not been uploaded.",
            404
        )


    file_path = upload["file_path"]


    if not os.path.isabs(file_path):

        file_path = os.path.join(
            BASE_DIR,
            file_path
        )


    if not os.path.exists(file_path):

        return (
            "Original certificate file not found.",
            404
        )


    return send_file(
        file_path,
        as_attachment=False
    )


# =========================================================
# QR VERIFICATION
# =========================================================

@app.route(
    "/verify/<credential_id>"
)
def verify(credential_id):

    conn = get_db()


    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE credential_id = ?
        """,
        (
            credential_id,
        )
    ).fetchone()


    status = (
        "VERIFIED"
        if user
        else
        "INVALID"
    )


    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    conn.execute(
        """
        INSERT INTO verification_history
        (
            credential_id,
            status,
            method,
            verification_method,
            verified_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            credential_id,
            status,
            "QR",
            "QR",
            now
        )
    )


    conn.commit()

    conn.close()


    return render_template(
        "verify.html",
        user=dict(user)
        if user
        else None,
        verified=bool(user),
        credential_id=credential_id
    )


# =========================================================
# CLEAN OCR TEXT
# =========================================================

def clean_ocr_text(text):

    if not text:

        return ""

    text = text.replace(
        "\r",
        "\n"
    )

    return text.strip()


# =========================================================
# EXTRACT VALIDATION CODE
# =========================================================

def extract_validation_code(text):

    if not text:

        return None


    cleaned = text.replace(
        "\r",
        " "
    )

    cleaned = cleaned.replace(
        "\n",
        " "
    )

    cleaned = cleaned.replace(
        "|",
        " "
    )

    cleaned = cleaned.replace(
        '"',
        " "
    )

    cleaned = cleaned.replace(
        "'",
        " "
    )


    # =====================================================
    # DIRECT 32 CHARACTER HEX CODE
    # =====================================================

    match = re.search(
        r"(?<![A-Fa-f0-9])"
        r"[A-Fa-f0-9]{32}"
        r"(?![A-Fa-f0-9])",
        cleaned
    )


    if match:

        return match.group(0).lower()


    # =====================================================
    # SEARCH AFTER VALIDATION CODE
    # =====================================================

    validation_match = re.search(
        r"VALIDATION\s*CODE"
        r"\s*[:\-]?\s*"
        r"([A-Za-z0-9\s\.,:;|\-]{5,150})",
        cleaned,
        re.IGNORECASE
    )


    if validation_match:

        area = validation_match.group(1)


        direct = re.search(
            r"(?<![A-Fa-f0-9])"
            r"[A-Fa-f0-9]{32}"
            r"(?![A-Fa-f0-9])",
            area
        )


        if direct:

            return direct.group(0).lower()


        candidate = re.sub(
            r"[^A-Fa-f0-9]",
            "",
            area
        )


        if len(candidate) >= 32:

            for i in range(
                0,
                len(candidate) - 31
            ):

                possible = candidate[
                    i:i + 32
                ]


                if re.fullmatch(
                    r"[A-Fa-f0-9]{32}",
                    possible
                ):

                    return possible.lower()


    # =====================================================
    # OCR SPLIT HEX CODE
    # =====================================================

    tokens = re.findall(
        r"[A-Fa-f0-9]{2,8}",
        cleaned
    )


    for start in range(
        len(tokens)
    ):

        combined = ""


        for end in range(
            start,
            min(
                start + 12,
                len(tokens)
            )
        ):

            combined += tokens[end]


            if len(combined) == 32:

                if re.fullmatch(
                    r"[A-Fa-f0-9]{32}",
                    combined
                ):

                    return combined.lower()


            if len(combined) > 32:

                break


    # =====================================================
    # LONG HEX STRINGS
    # =====================================================

    matches = re.findall(
        r"[A-Fa-f0-9]{28,40}",
        cleaned
    )


    for candidate in matches:

        if len(candidate) == 32:

            return candidate.lower()


    # =====================================================
    # HEX GROUPS WITH SPACES
    # =====================================================

    possible_groups = re.findall(
        r"(?:[A-Fa-f0-9]{2,8}\s+){3,20}"
        r"[A-Fa-f0-9]{2,8}",
        cleaned
    )


    for candidate in possible_groups:

        joined = re.sub(
            r"[^A-Fa-f0-9]",
            "",
            candidate
        )


        if len(joined) == 32:

            return joined.lower()


    return None


# =========================================================
# EXTRACT CREDENTIAL ID
# =========================================================

def extract_credential_id(text):

    if not text:

        return None


    patterns = [

        r"\bCRED[-\s]?\d{4}[-\s]?[A-Z0-9]{4,20}\b",

        r"\bCREDENTIAL\s*ID"
        r"\s*[:\-]?\s*"
        r"(CRED[-\s]?\d{4}[-\s]?[A-Z0-9]{4,20})",

        r"\bCREDENTIAL"
        r"\s*[:\-]?\s*"
        r"(CRED[-\s]?\d{4}[-\s]?[A-Z0-9]{4,20})"

    ]


    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )


        if match:

            value = (
                match.group(1)
                if match.lastindex
                else match.group(0)
            )


            value = value.upper()


            value = re.sub(
                r"\s+",
                "",
                value
            )


            return value


    return None


# =========================================================
# IMAGE OCR
# =========================================================

def perform_image_ocr(filepath):

    try:

        if os.name == "nt":

            if not os.path.exists(
                TESSERACT_PATH
            ):

                return (
                    "OCR ERROR: Tesseract not found at: "
                    +
                    TESSERACT_PATH
                )


        pytesseract.pytesseract.tesseract_cmd = (
            TESSERACT_PATH
        )


        image = Image.open(
            filepath
        ).convert("RGB")


        # =================================================
        # OCR ATTEMPT 1
        # =================================================

        result1 = pytesseract.image_to_string(
            image,
            config="--psm 6"
        )


        # =================================================
        # OCR ATTEMPT 2
        # =================================================

        enhanced = ImageEnhance.Contrast(
            image
        ).enhance(2.0)


        enhanced = enhanced.filter(
            ImageFilter.SHARPEN
        )


        result2 = pytesseract.image_to_string(
            enhanced,
            config="--psm 6"
        )


        # =================================================
        # OCR ATTEMPT 3
        # =================================================

        width, height = image.size


        resized = image.resize(
            (
                width * 2,
                height * 2
            )
        )


        result3 = pytesseract.image_to_string(
            resized,
            config="--psm 6"
        )


        # =================================================
        # OCR ATTEMPT 4
        # =================================================

        gray = image.convert(
            "L"
        )


        gray = ImageEnhance.Contrast(
            gray
        ).enhance(2.5)


        result4 = pytesseract.image_to_string(
            gray,
            config="--psm 6"
        )


        results = [
            result1,
            result2,
            result3,
            result4
        ]


        results = [
            result
            for result in results
            if result and result.strip()
        ]


        if not results:

            return ""


        return max(
            results,
            key=len
        )


    except Exception as e:

        return (
            "OCR ERROR: "
            +
            str(e)
        )


# =========================================================
# PDF OCR
# =========================================================

def perform_pdf_ocr(filepath):

    extracted_text = ""


    try:

        import fitz


        # =================================================
        # NORMAL PDF TEXT EXTRACTION
        # =================================================

        pdf_document = fitz.open(
            filepath
        )


        for page in pdf_document:

            page_text = page.get_text()


            if page_text:

                extracted_text += (
                    page_text
                    +
                    "\n"
                )


        pdf_document.close()


        if extracted_text.strip():

            return extracted_text


        # =================================================
        # SCANNED PDF OCR
        # =================================================

        pdf_document = fitz.open(
            filepath
        )


        ocr_results = []


        for page in pdf_document:

            pix = page.get_pixmap(
                matrix=fitz.Matrix(
                    2.5,
                    2.5
                )
            )


            image = Image.frombytes(
                "RGB",
                [
                    pix.width,
                    pix.height
                ],
                pix.samples
            )


            result1 = pytesseract.image_to_string(
                image,
                config="--psm 6"
            )


            enhanced = ImageEnhance.Contrast(
                image
            ).enhance(2.0)


            enhanced = enhanced.filter(
                ImageFilter.SHARPEN
            )


            result2 = pytesseract.image_to_string(
                enhanced,
                config="--psm 6"
            )


            page_result = max(
                [
                    result1,
                    result2
                ],
                key=len
            )


            if page_result:

                ocr_results.append(
                    page_result
                )


        pdf_document.close()


        return "\n".join(
            ocr_results
        )


    except Exception as e:

        return (
            "PDF OCR ERROR: "
            +
            str(e)
        )


# =========================================================
# AI CERTIFICATE VERIFICATION
# =========================================================

@app.route(
    "/ai-verify",
    methods=["GET", "POST"]
)
def ai_verify():

    if request.method == "GET":

        return render_template(
            "ai_verify.html"
        )


    # =====================================================
    # FILE CHECK
    # =====================================================

    if "certificate" not in request.files:

        return "Certificate file not selected."


    file = request.files["certificate"]


    if file.filename == "":

        return "Please select a certificate."


    # =====================================================
    # SECURE FILENAME
    # =====================================================

    filename = secure_filename(
        file.filename
    )


    # =====================================================
    # FILE TYPE CHECK
    # =====================================================

    if not allowed_file(filename):

        return render_template(
            "ai_result.html",
            extracted_text="",
            credential_id="NOT DETECTED",
            validation_code=None,
            error=(
                "Only PDF, PNG, JPG and JPEG files are allowed."
            )
        )


    # =====================================================
    # UNIQUE FILE NAME
    # =====================================================

    unique_name = (
        datetime.now().strftime(
            "%Y%m%d%H%M%S"
        )
        +
        "_"
        +
        uuid.uuid4().hex[:8]
        +
        "_"
        +
        filename
    )


    filepath = os.path.join(
        UPLOAD_FOLDER,
        unique_name
    )


    # =====================================================
    # SAVE FILE
    # =====================================================

    file.save(
        filepath
    )


    # =====================================================
    # EXTENSION
    # =====================================================

    extension = filename.rsplit(
        ".",
        1
    )[-1].lower()


    extracted_text = ""


    # =====================================================
    # IMAGE OCR
    # =====================================================

    if extension in [
        "png",
        "jpg",
        "jpeg"
    ]:

        extracted_text = perform_image_ocr(
            filepath
        )


    # =====================================================
    # PDF OCR
    # =====================================================

    elif extension == "pdf":

        extracted_text = perform_pdf_ocr(
            filepath
        )


    # =====================================================
    # CLEAN OCR
    # =====================================================

    extracted_text = clean_ocr_text(
        extracted_text
    )


    # =====================================================
    # PRINT OCR RESULT
    # =====================================================

    print()

    print(
        "========== OCR RESULT =========="
    )

    print(
        extracted_text
    )

    print(
        "================================"
    )

    print()


    # =====================================================
    # EXTRACT VALUES
    # =====================================================

    credential_id = extract_credential_id(
        extracted_text
    )


    validation_code = extract_validation_code(
        extracted_text
    )


    if credential_id:

        credential_id = (
            credential_id
            .strip()
            .upper()
        )


    if validation_code:

        validation_code = (
            validation_code
            .strip()
            .lower()
        )


    # =====================================================
    # DATABASE
    # =====================================================

    conn = get_db()


    user = None


    # =====================================================
    # SEARCH CREDENTIAL ID
    # =====================================================

    if credential_id:

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE UPPER(
                TRIM(credential_id)
            ) = ?
            """,
            (
                credential_id,
            )
        ).fetchone()


    # =====================================================
    # SEARCH VALIDATION CODE
    # =====================================================

    if validation_code and not user:

        try:

            user = conn.execute(
                """
                SELECT *
                FROM users
                WHERE LOWER(
                    TRIM(validation_code)
                )
                =
                LOWER(
                    TRIM(?)
                )
                """,
                (
                    validation_code,
                )
            ).fetchone()


        except sqlite3.OperationalError as e:

            print(
                "Validation code search error:",
                e
            )

            user = None


    # =====================================================
    # VERIFIED
    # =====================================================

    if user:

        actual_credential_id = (
            user["credential_id"]
        )


        db_validation_code = (
            user["validation_code"]
        )


        display_validation_code = (
            validation_code
            or
            db_validation_code
        )


        relative_path = os.path.join(
            "uploads",
            unique_name
        )


        # =================================================
        # SAVE UPLOAD
        # =================================================

        try:

            conn.execute(
                """
                INSERT INTO certificate_uploads
                (
                    credential_id,
                    filename,
                    file_path,
                    uploaded_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    actual_credential_id,
                    filename,
                    relative_path,
                    datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                )
            )


        except sqlite3.OperationalError as e:

            print(
                "certificate_uploads error:",
                e
            )


        # =================================================
        # UPDATE USER CERTIFICATE FILE
        # =================================================

        try:

            conn.execute(
                """
                UPDATE users
                SET certificate_file = ?
                WHERE credential_id = ?
                """,
                (
                    relative_path,
                    actual_credential_id
                )
            )


        except sqlite3.OperationalError as e:

            print(
                "certificate_file update error:",
                e
            )


        # =================================================
        # VERIFICATION HISTORY
        # =================================================

        now = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )


        try:

            conn.execute(
                """
                INSERT INTO verification_history
                (
                    credential_id,
                    validation_code,
                    status,
                    method,
                    verification_method,
                    verified_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    actual_credential_id,
                    display_validation_code,
                    "VERIFIED",
                    "AI + OCR",
                    "AI + OCR",
                    now
                )
            )


        except sqlite3.OperationalError as e:

            print(
                "verification history error:",
                e
            )


        conn.commit()


        # =================================================
        # CERTIFICATE DATA
        # =================================================

        certificate = {

            "student_name":
                user["name"],

            "validation_code":
                display_validation_code,

            "credential_id":
                actual_credential_id,

            "certificate_type":
                user["certificate_type"],

            "certificate_title":
                user["certificate_title"],

            "organization":
                user["organization"],

            "completion_date":
                user["issue_date"]

        }


        conn.close()


        return render_template(
            "ai_verified.html",
            user=dict(user),
            certificate=certificate,
            extracted_text=extracted_text,
            credential_id=actual_credential_id,
            validation_code=display_validation_code
        )


    # =====================================================
    # INVALID
    # =====================================================

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    try:

        conn.execute(
            """
            INSERT INTO verification_history
            (
                credential_id,
                validation_code,
                status,
                method,
                verification_method,
                verified_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                credential_id,
                validation_code,
                "INVALID",
                "AI + OCR",
                "AI + OCR",
                now
            )
        )


        conn.commit()


    except sqlite3.OperationalError as e:

        print(
            "Invalid history error:",
            e
        )


    conn.close()


    detected_value = (
        credential_id
        or
        validation_code
        or
        "NOT DETECTED"
    )


    return render_template(
        "ai_result.html",
        extracted_text=extracted_text,
        credential_id=detected_value,
        validation_code=validation_code
    )


# =========================================================
# STUDENT VERIFICATION HISTORY
# =========================================================

@app.route(
    "/verification-history"
)
def verification_history():

    if "student_id" not in session:

        return redirect(
            url_for("home")
        )


    conn = get_db()


    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (
            session["student_id"],
        )
    ).fetchone()


    if not user:

        conn.close()

        return redirect(
            url_for("home")
        )


    history = conn.execute(
        """
        SELECT *
        FROM verification_history
        WHERE credential_id = ?
        ORDER BY id DESC
        """,
        (
            user["credential_id"],
        )
    ).fetchall()


    conn.close()


    return render_template(
        "verification_history.html",
        user=dict(user),
        history=[
            dict(row)
            for row in history
        ]
    )


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route(
    "/admin-login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()


        password = request.form.get(
            "password",
            ""
        )


        conn = get_db()


        admin = conn.execute(
            """
            SELECT *
            FROM admins
            WHERE username = ?
            """,
            (
                username,
            )
        ).fetchone()


        password_hash = hashlib.sha256(
            (password or "").encode()
        ).hexdigest()


        valid_admin = bool(
            admin
            and
            (
                admin["password"] == password
                or
                admin["password"] == password_hash
            )
        )


        conn.close()


        if valid_admin:

            session["admin_id"] = admin["id"]

            session["admin_username"] = (
                admin["username"]
            )


            return redirect(
                url_for(
                    "admin_dashboard"
                )
            )


        return render_template(
            "admin_login.html",
            error=(
                "Invalid admin username "
                "or password."
            )
        )


    return render_template(
        "admin_login.html"
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route(
    "/admin-dashboard"
)
def admin_dashboard():

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )


    conn = get_db()


    total_users = conn.execute(
        """
        SELECT COUNT(*)
        FROM users
        """
    ).fetchone()[0]


    total_credentials = conn.execute(
        """
        SELECT COUNT(*)
        FROM users
        WHERE credential_id IS NOT NULL
        """
    ).fetchone()[0]


    total_verified = conn.execute(
        """
        SELECT COUNT(*)
        FROM verification_history
        WHERE status = 'VERIFIED'
        """
    ).fetchone()[0]


    total_invalid = conn.execute(
        """
        SELECT COUNT(*)
        FROM verification_history
        WHERE status = 'INVALID'
        """
    ).fetchone()[0]


    total_uploaded = conn.execute(
        """
        SELECT COUNT(*)
        FROM certificate_uploads
        """
    ).fetchone()[0]


    conn.close()


    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_credentials=total_credentials,
        total_verified=total_verified,
        total_invalid=total_invalid,
        total_uploaded=total_uploaded
    )


# =========================================================
# ADMIN CREDENTIALS
# =========================================================

@app.route(
    "/admin-credentials"
)
def admin_credentials():

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )


    conn = get_db()


    users = conn.execute(
        """
        SELECT *
        FROM users
        ORDER BY id DESC
        """
    ).fetchall()


    conn.close()


    return render_template(
        "admin_credentials.html",
        users=[
            dict(row)
            for row in users
        ]
    )


# =========================================================
# ADMIN CERTIFICATES
# =========================================================

@app.route(
    "/admin-certificates"
)
def admin_certificates():

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )


    conn = get_db()


    certificates = conn.execute(
        """
        SELECT *
        FROM users
        ORDER BY id DESC
        """
    ).fetchall()


    conn.close()


    return render_template(
        "admin_certificates.html",
        certificates=[
            dict(row)
            for row in certificates
        ]
    )


# =========================================================
# ADMIN ALL UPLOADS
# =========================================================

@app.route(
    "/admin-uploads"
)
def admin_uploads():

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )


    conn = get_db()


    uploads = conn.execute(
        """
        SELECT
            certificate_uploads.*,
            users.name,
            users.email
        FROM certificate_uploads
        LEFT JOIN users
        ON certificate_uploads.credential_id
        =
        users.credential_id
        ORDER BY certificate_uploads.id DESC
        """
    ).fetchall()


    conn.close()


    return render_template(
        "admin_uploads.html",
        uploads=[
            dict(row)
            for row in uploads
        ]
    )


# =========================================================
# ADMIN HISTORY
# =========================================================

@app.route(
    "/admin-history"
)
def admin_history():

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )


    conn = get_db()


    history = conn.execute(
        """
        SELECT *
        FROM verification_history
        ORDER BY id DESC
        """
    ).fetchall()


    conn.close()


    return render_template(
        "admin_history.html",
        history=[
            dict(row)
            for row in history
        ]
    )


# =========================================================
# ADMIN REGISTER ORIGINAL CERTIFICATE
# =========================================================

@app.route(
    "/admin-register-certificate",
    methods=["GET", "POST"]
)
def admin_register_certificate():

    # =====================================================
    # ADMIN LOGIN CHECK
    # =====================================================

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )


    conn = get_db()


    # =====================================================
    # GET STUDENTS
    # =====================================================

    users = conn.execute(
        """
        SELECT *
        FROM users
        ORDER BY name ASC
        """
    ).fetchall()


    # =====================================================
    # GET REQUEST
    # =====================================================

    if request.method == "GET":

        conn.close()


        return render_template(
            "admin_register_certificate.html",
            users=[
                dict(row)
                for row in users
            ],
            extracted_text="",
            detected_validation_code="",
            detected_credential_id=""
        )


    # =====================================================
    # STUDENT ID
    # =====================================================

    student_id = request.form.get(
        "student_id",
        ""
    ).strip()


    # =====================================================
    # CERTIFICATE FILE
    # =====================================================

    file = request.files.get(
        "certificate"
    )


    # =====================================================
    # STUDENT ID REQUIRED
    # =====================================================

    if not student_id:

        conn.close()


        return render_template(
            "admin_register_certificate.html",
            users=[
                dict(row)
                for row in users
            ],
            error="Please select a Student ID.",
            extracted_text="",
            detected_validation_code="",
            detected_credential_id=""
        )


    # =====================================================
    # FILE REQUIRED
    # =====================================================

    if not file or file.filename == "":

        conn.close()


        return render_template(
            "admin_register_certificate.html",
            users=[
                dict(row)
                for row in users
            ],
            error="Please select the original certificate.",
            extracted_text="",
            detected_validation_code="",
            detected_credential_id=""
        )


    # =====================================================
    # SECURE FILENAME
    # =====================================================

    filename = secure_filename(
        file.filename
    )


    # =====================================================
    # FILE TYPE CHECK
    # =====================================================

    if not allowed_file(filename):

        conn.close()


        return render_template(
            "admin_register_certificate.html",
            users=[
                dict(row)
                for row in users
            ],
            error=(
                "Only PDF, JPG, JPEG and PNG "
                "files are allowed."
            ),
            extracted_text="",
            detected_validation_code="",
            detected_credential_id=""
        )


    # =====================================================
    # FIND STUDENT
    # =====================================================

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (
            student_id,
        )
    ).fetchone()


    if not user:

        conn.close()


        return render_template(
            "admin_register_certificate.html",
            users=[
                dict(row)
                for row in users
            ],
            error="Student not found.",
            extracted_text="",
            detected_validation_code="",
            detected_credential_id=""
        )


    # =====================================================
    # UNIQUE FILE NAME
    # =====================================================

    unique_name = (
        "ORIGINAL_"
        +
        datetime.now().strftime(
            "%Y%m%d%H%M%S"
        )
        +
        "_"
        +
        uuid.uuid4().hex[:8]
        +
        "_"
        +
        filename
    )


    # =====================================================
    # FILE PATH
    # =====================================================

    filepath = os.path.join(
        UPLOAD_FOLDER,
        unique_name
    )


    # =====================================================
    # SAVE FILE
    # =====================================================

    file.save(
        filepath
    )


    # =====================================================
    # DETERMINE EXTENSION
    # =====================================================

    extension = filename.rsplit(
        ".",
        1
    )[-1].lower()


    # =====================================================
    # OCR
    # =====================================================

    extracted_text = ""


    if extension in [
        "png",
        "jpg",
        "jpeg"
    ]:

        extracted_text = perform_image_ocr(
            filepath
        )


    elif extension == "pdf":

        extracted_text = perform_pdf_ocr(
            filepath
        )


    # =====================================================
    # CLEAN OCR TEXT
    # =====================================================

    extracted_text = clean_ocr_text(
        extracted_text
    )


    # =====================================================
    # EXTRACT VALIDATION CODE
    # =====================================================

    validation_code = extract_validation_code(
        extracted_text
    )


    # =====================================================
    # EXTRACT CREDENTIAL ID
    # =====================================================

    detected_credential_id = extract_credential_id(
        extracted_text
    )


    # =====================================================
    # NORMALIZE
    # =====================================================

    if validation_code:

        validation_code = (
            validation_code
            .strip()
            .lower()
        )


    if detected_credential_id:

        detected_credential_id = (
            detected_credential_id
            .strip()
            .upper()
        )


    # =====================================================
    # PRINT OCR RESULT
    # =====================================================

    print()

    print(
        "=========================================="
    )

    print(
        "        ADMIN CERTIFICATE OCR"
    )

    print(
        "=========================================="
    )

    print(
        "Student Name :",
        user["name"]
    )

    print(
        "Student ID   :",
        user["id"]
    )

    print()

    print(
        "EXTRACTED OCR TEXT:"
    )

    print(
        extracted_text
    )

    print()

    print(
        "Detected Credential ID :",
        detected_credential_id
    )

    print(
        "Detected Validation Code :",
        validation_code
    )

    print(
        "Registered Credential ID :",
        user["credential_id"]
    )

    print(
        "=========================================="
    )

    print()


    # =====================================================
    # OCR ERROR CHECK
    # =====================================================

    if (
        extracted_text.startswith(
            "OCR ERROR:"
        )
        or
        extracted_text.startswith(
            "PDF OCR ERROR:"
        )
    ):

        conn.close()


        return render_template(
            "admin_register_certificate.html",
            users=[
                dict(row)
                for row in users
            ],
            error=extracted_text,
            extracted_text=extracted_text,
            detected_validation_code=(
                validation_code or ""
            ),
            detected_credential_id=(
                detected_credential_id or ""
            )
        )


    # =====================================================
    # VALIDATION CODE REQUIRED
    # =====================================================

    if not validation_code:

        conn.close()


        return render_template(
            "admin_register_certificate.html",
            users=[
                dict(row)
                for row in users
            ],
            error=(
                "OCR completed, but the 32-character "
                "Validation Code was not detected."
            ),
            extracted_text=extracted_text,
            detected_validation_code="NOT DETECTED",
            detected_credential_id=(
                detected_credential_id
                or
                "NOT DETECTED"
            )
        )


    # =====================================================
    # VALIDATION CODE LENGTH CHECK
    # =====================================================

    if len(validation_code) != 32:

        conn.close()


        return render_template(
            "admin_register_certificate.html",
            users=[
                dict(row)
                for row in users
            ],
            error=(
                "OCR detected a Validation Code, "
                "but it is not exactly 32 characters."
            ),
            extracted_text=extracted_text,
            detected_validation_code=validation_code,
            detected_credential_id=(
                detected_credential_id
                or
                "NOT DETECTED"
            )
        )


    # =====================================================
    # CREDENTIAL ID MATCH CHECK
    # =====================================================

    if detected_credential_id:

        if detected_credential_id != (
            user["credential_id"].upper()
        ):

            conn.close()


            return render_template(
                "admin_register_certificate.html",
                users=[
                    dict(row)
                    for row in users
                ],
                error=(
                    "Credential ID detected from OCR "
                    "does not match the selected student's "
                    "Credential ID."
                ),
                extracted_text=extracted_text,
                detected_validation_code=validation_code,
                detected_credential_id=(
                    detected_credential_id
                )
            )


    # =====================================================
    # SAVE VALIDATION CODE
    # =====================================================

    conn.execute(
        """
        UPDATE users
        SET validation_code = ?
        WHERE id = ?
        """,
        (
            validation_code,
            student_id
        )
    )


    # =====================================================
    # RELATIVE FILE PATH
    # =====================================================

    relative_path = os.path.join(
        "uploads",
        unique_name
    )


    # =====================================================
    # SAVE CERTIFICATE UPLOAD
    # =====================================================

    conn.execute(
        """
        INSERT INTO certificate_uploads
        (
            credential_id,
            filename,
            file_path,
            uploaded_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            user["credential_id"],
            filename,
            relative_path,
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )
    )


    # =====================================================
    # UPDATE USER CERTIFICATE FILE
    # =====================================================

    conn.execute(
        """
        UPDATE users
        SET certificate_file = ?
        WHERE id = ?
        """,
        (
            relative_path,
            student_id
        )
    )


    # =====================================================
    # COMMIT
    # =====================================================

    conn.commit()


    # =====================================================
    # READ SAVED DATA
    # =====================================================

    saved_user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (
            student_id,
        )
    ).fetchone()


    saved_validation_code = (
        saved_user["validation_code"]
    )


    # =====================================================
    # DATABASE DEBUG
    # =====================================================

    print()

    print(
        "========== DATABASE SAVE =========="
    )

    print(
        "Student :",
        saved_user["name"]
    )

    print(
        "Credential ID :",
        saved_user["credential_id"]
    )

    print(
        "Validation Code Saved :",
        saved_validation_code
    )

    print(
        "Certificate File :",
        saved_user["certificate_file"]
    )

    print(
        "==================================="
    )

    print()


    conn.close()


    # =====================================================
    # REFRESH USERS
    # =====================================================

    conn2 = get_db()


    updated_users = conn2.execute(
        """
        SELECT *
        FROM users
        ORDER BY name ASC
        """
    ).fetchall()


    conn2.close()


    # =====================================================
    # SUCCESS
    # =====================================================

    return render_template(
        "admin_register_certificate.html",
        users=[
            dict(row)
            for row in updated_users
        ],
        success=(
            "Original certificate registered successfully."
        ),
        extracted_text=extracted_text,
        detected_validation_code=(
            saved_validation_code
        ),
        detected_credential_id=(
            detected_credential_id
            or
            user["credential_id"]
        )
    )


# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.route(
    "/admin-logout"
)
def admin_logout():

    session.pop(
        "admin_id",
        None
    )

    session.pop(
        "admin_username",
        None
    )


    return redirect(
        url_for("admin_login")
    )


# =========================================================
# STUDENT LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()


    return redirect(
        url_for("home")
    )


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":

    create_database()


    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )


    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )