# http://flask.pocoo.org/docs/0.11/patterns/fileuploads/
import os
import shutil
import subprocess
import tempfile
import datetime
import uuid
from flask import Flask, request, redirect, url_for, render_template, flash
from werkzeug.utils import secure_filename

from simple_print_server.database import db_session
from simple_print_server.models import PrintedFile
from simple_print_server.page_range import parse_page_range, format_page_list, PageRangeError
from simple_print_server import app

import logging
logger = logging.getLogger(__name__)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def make_today_folder():
    today_str = datetime.datetime.today().strftime('%Y%m%d')
    full_today_path = os.path.join(app.config['BASE_UPLOAD_FOLDER'], today_str)

    if not os.path.exists(full_today_path):
        os.mkdir(full_today_path)
        app.config['TODAY_UPLOAD_FOLDER'] = full_today_path
        logger.info('Changed today\'s upload folder to {}'.format(full_today_path))
    elif not 'TODAY_UPLOAD_FOLDER' in app.config:
        app.config['TODAY_UPLOAD_FOLDER'] = full_today_path


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


def log_subprocess_output(pipe):
    for line in iter(pipe.readline, b''):
        logging.info('%r', line)


def get_pdf_page_count(pdf_path):
    """Return the number of pages in ``pdf_path`` via ``pdfinfo``.

    Raises ``RuntimeError`` if pdfinfo fails or its output is unparseable.
    """
    try:
        out = subprocess.check_output(
            ['pdfinfo', pdf_path],
            stderr=subprocess.STDOUT,
        ).decode('utf-8', errors='replace')
    except subprocess.CalledProcessError as e:
        raise RuntimeError("pdfinfo failed: {}".format(
            e.output.decode('utf-8', errors='replace').strip()))
    for line in out.splitlines():
        if line.startswith('Pages:'):
            try:
                return int(line.split(':', 1)[1].strip())
            except ValueError:
                break
    raise RuntimeError("pdfinfo did not report a Pages count")


def extract_pdf_pages(input_pdf, output_pdf, page_list):
    """Build ``output_pdf`` containing only the pages in ``page_list``
    (1-indexed, sorted unique) from ``input_pdf``.

    Splits ``page_list`` into maximal contiguous runs and renders each run
    via Ghostscript's ``pdfwrite`` device with ``-dFirstPage``/``-dLastPage``.
    Using gs (rather than ``pdfseparate``) is important: lots of real-world
    PDFs (Adobe InDesign exports, scanned forms) carry permissions metadata
    that ``pdfunite`` refuses to merge ("Unimplemented Feature: Could not
    merge encrypted files"), and gs's pdfwrite always emits a fresh,
    unencrypted PDF as a side effect.

    If there is more than one run the per-run PDFs are then concatenated
    with ``pdfunite``, which is happy with the gs-produced files because
    they are no longer flagged encrypted.
    """
    pages = sorted(set(page_list))
    if not pages:
        raise ValueError("page_list is empty")

    # Collapse to (lo, hi) contiguous runs.
    runs = []
    run_lo = pages[0]
    run_hi = pages[0]
    for p in pages[1:]:
        if p == run_hi + 1:
            run_hi = p
        else:
            runs.append((run_lo, run_hi))
            run_lo = p
            run_hi = p
    runs.append((run_lo, run_hi))

    work = tempfile.mkdtemp(prefix='kiosk-pages-')
    try:
        part_files = []
        for idx, (lo, hi) in enumerate(runs, start=1):
            part = os.path.join(work, 'part-{}.pdf'.format(idx))
            cmd = [
                'gs',
                '-sDEVICE=pdfwrite',
                '-dNOPAUSE', '-dBATCH', '-dQUIET', '-dSAFER',
                '-dFirstPage={}'.format(lo),
                '-dLastPage={}'.format(hi),
                '-sOutputFile={}'.format(part),
                input_pdf,
            ]
            subprocess.check_call(cmd, stderr=subprocess.STDOUT)
            if not os.path.exists(part) or os.path.getsize(part) == 0:
                raise RuntimeError(
                    'ghostscript produced no output for pages {}-{}'.format(lo, hi))
            part_files.append(part)

        if len(part_files) == 1:
            shutil.copyfile(part_files[0], output_pdf)
        else:
            subprocess.check_call(
                ['pdfunite'] + part_files + [output_pdf],
                stderr=subprocess.STDOUT,
            )
    finally:
        shutil.rmtree(work, ignore_errors=True)


def is_pdf(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'


@app.route('/', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part', 'danger')
        return redirect(request.url)

    file_to_upload = request.files['file']
    if file_to_upload.filename == '':
        flash('No selected file', 'danger')
        return redirect(request.url)

    if not allowed_file(file_to_upload.filename):
        flash('Bad filetype: {}'.format(file_to_upload.filename), 'danger')
        return redirect(request.url)

    # Save the upload under data/uploads/<today>/<uuid>.<ext>
    original_filename = file_to_upload.filename
    ext = os.path.splitext(original_filename)[1]
    stored_name = '{}{}'.format(str(uuid.uuid4()), ext)

    make_today_folder()
    fullpath = os.path.join(app.config['TODAY_UPLOAD_FOLDER'], stored_name)
    file_to_upload.save(fullpath)

    # Page range only applies to PDFs.
    pages_spec_raw = (request.form.get('pages') or '').strip()
    pages_to_print = None    # list[int] or None (all pages)
    pages_display = None     # str shown in flash + recent table
    print_path = fullpath    # what we hand off to lp-brother-dcp1510

    if pages_spec_raw and not is_pdf(original_filename):
        flash('Page ranges only apply to PDF files; ignoring "{}"'.format(pages_spec_raw),
              'warning')
        pages_spec_raw = ''

    if pages_spec_raw:
        try:
            total = get_pdf_page_count(fullpath)
        except RuntimeError as e:
            flash('Could not read PDF: {}'.format(e), 'danger')
            return redirect(request.url)

        try:
            pages_to_print = parse_page_range(pages_spec_raw, total)
        except PageRangeError as e:
            flash('Invalid page range "{}": {}'.format(pages_spec_raw, e), 'danger')
            return redirect(request.url)

        if pages_to_print is None or len(pages_to_print) == total:
            # User typed something that resolved to "all pages"; treat as no
            # filter so we don't pay the pdfseparate+pdfunite cost.
            pages_to_print = None
        else:
            filtered_path = os.path.join(
                app.config['TODAY_UPLOAD_FOLDER'],
                '{}-pages{}'.format(os.path.splitext(stored_name)[0], ext),
            )
            try:
                extract_pdf_pages(fullpath, filtered_path, pages_to_print)
            except (subprocess.CalledProcessError, RuntimeError) as e:
                flash('Failed to extract pages: {}'.format(e), 'danger')
                return redirect(request.url)
            print_path = filtered_path
            pages_display = format_page_list(pages_to_print)

    # Persist the print record.
    record = PrintedFile(original_filename, stored_name)
    record.pages = pages_display
    db_session.add(record)
    db_session.commit()

    # Hand off to the brother-safe-print router.
    process = subprocess.Popen(
        [app.config['PRINT_COMMAND'], print_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    with process.stdout:
        log_subprocess_output(process.stdout)
    exitcode = process.wait()

    if exitcode == 0:
        if pages_display:
            flash('Printing pages {} of "{}"'.format(pages_display, original_filename),
                  'success')
        else:
            flash('Printing "{}"'.format(original_filename), 'success')
        logger.info('Submitted print: original=%r stored=%r pages=%r',
                    original_filename, stored_name, pages_display)
    else:
        flash('Print command failed (exit {})'.format(exitcode), 'danger')

    return redirect(request.url)


@app.route('/', methods=['GET'])
def main_page():
    recent_files = list(PrintedFile.query.order_by(PrintedFile.id.desc()).limit(10))
    return render_template('index.html', recent=recent_files)
