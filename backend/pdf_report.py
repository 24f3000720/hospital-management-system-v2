from pathlib import Path
from textwrap import wrap


PAGE_WIDTH = 612
PAGE_HEIGHT = 792
LEFT_MARGIN = 50
TOP_START = 760
LINE_HEIGHT = 16
LINES_PER_PAGE = 42


def _escape_pdf_text(value):
    text = (value or '').replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    return text.encode('latin-1', 'replace').decode('latin-1')


def _wrap_lines(lines, width=88):
    wrapped_lines = []

    for line in lines:
        clean_line = str(line or '')
        if not clean_line:
            wrapped_lines.append('')
            continue

        wrapped_lines.extend(wrap(clean_line, width=width) or [''])

    return wrapped_lines


def _build_page_stream(title, page_lines):
    commands = [
        'BT',
        f'/F1 18 Tf',
        f'{LEFT_MARGIN} {TOP_START} Td',
        f'({_escape_pdf_text(title)}) Tj',
        '/F1 11 Tf',
    ]

    current_y = TOP_START - 32
    for line in page_lines:
        commands.append(f'1 0 0 1 {LEFT_MARGIN} {current_y} Tm')
        commands.append(f'({_escape_pdf_text(line)}) Tj')
        current_y -= LINE_HEIGHT

    commands.append('ET')
    return '\n'.join(commands).encode('latin-1')


def write_simple_pdf(file_path, title, lines):
    wrapped_lines = _wrap_lines(lines)
    pages = [
        wrapped_lines[index:index + LINES_PER_PAGE]
        for index in range(0, max(len(wrapped_lines), 1), LINES_PER_PAGE)
    ] or [[]]

    objects = {
        1: b'<< /Type /Catalog /Pages 2 0 R >>',
        3: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    }

    page_numbers = []
    next_object = 4

    for page_lines in pages:
        page_number = next_object
        content_number = next_object + 1
        next_object += 2

        stream_bytes = _build_page_stream(title, page_lines)
        objects[page_number] = (
            f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] '
            f'/Resources << /Font << /F1 3 0 R >> >> /Contents {content_number} 0 R >>'
        ).encode('latin-1')
        objects[content_number] = (
            f'<< /Length {len(stream_bytes)} >>\nstream\n'.encode('latin-1')
            + stream_bytes
            + b'\nendstream'
        )
        page_numbers.append(page_number)

    kids = ' '.join(f'{page_number} 0 R' for page_number in page_numbers)
    objects[2] = f'<< /Type /Pages /Count {len(page_numbers)} /Kids [{kids}] >>'.encode('latin-1')

    pdf_bytes = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n'
    offsets = [0]

    max_object = max(objects)
    for object_number in range(1, max_object + 1):
        offsets.append(len(pdf_bytes))
        pdf_bytes += f'{object_number} 0 obj\n'.encode('latin-1')
        pdf_bytes += objects[object_number]
        pdf_bytes += b'\nendobj\n'

    xref_offset = len(pdf_bytes)
    pdf_bytes += f'xref\n0 {max_object + 1}\n'.encode('latin-1')
    pdf_bytes += b'0000000000 65535 f \n'

    for object_number in range(1, max_object + 1):
        pdf_bytes += f'{offsets[object_number]:010d} 00000 n \n'.encode('latin-1')

    pdf_bytes += (
        f'trailer\n<< /Size {max_object + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF'.encode('latin-1')
    )

    Path(file_path).write_bytes(pdf_bytes)
