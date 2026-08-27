"""Verify the declared asset identity against the actual drawing.

THE CLAIM UNDER TEST. Clone detection currently rests on xmpMM:DocumentID: two
documents placing the same source Illustrator file share the identifier, so shared
rare identifiers imply shared model-specific artwork. That gave a 31-37x lift over
base rate. But the identifier is a TAG, and a tag can be reused across edits - if
Dreame revises a drawing and keeps the DocumentID, two documents could share the ID
while carrying visibly different art, and the lift would be softer than reported.

THE TEST. Each placed asset's geometry is exactly delimited in the content stream by
its `/MCn BDC ... EMC` span - 97.1% of path operators on a sample page attribute to
one. So for every DocumentID shared between two documents, pull the geometry out of
both spans and compare. Identical geometry confirms the tag; differing geometry means
the tag is a lineage marker, not an asset fingerprint.

COORDINATES ARE TAKEN RAW, deliberately. The operands inside a span are in the asset's
own local space; the placement transform sits outside it. Not applying any CTM is what
makes the same asset match when it is placed at a different position or scale in the
two documents. Applying one would guarantee a mismatch and prove nothing.

⚠ BDC IS NOT WHITESPACE-DELIMITED. It arrives glued to its operand as
`<</MCID 0>>BDC`, so a token-based scan finds 9 of 187 on a page and silently reports
no spans at all. Locate BDC/EMC by BYTE OFFSET.
"""
import collections
import hashlib
import re

RE_MARK = re.compile(rb'BDC|EMC')
RE_NAME = re.compile(rb'/([A-Za-z0-9]+)')
# path construction operators, not glued to neighbouring letters
RE_PATHOP = re.compile(rb'(?<![A-Za-z0-9])(m|l|c|v|y|re|h)(?![A-Za-z0-9])')
RE_NUM = re.compile(rb'-?\d*\.?\d+')
RE_XMP = re.compile(r'<(xmpMM:DocumentID|xmp:ModifyDate)>([^<]{1,120})<')


def mc_to_docid(page):
    """Map the page's /MCn property names to their declared DocumentID."""
    out = {}
    try:
        props = page['/Resources'].get_object().get('/Properties')
        props = props.get_object() if props is not None else None
    except Exception:
        return out
    if not props:
        return out
    for k in props:
        try:
            md = props[k].get_object().get('/Metadata')
            if md is None:
                continue
            txt = md.get_object().get_data().decode('utf-8', 'replace')
        except Exception:
            continue
        f = {}
        for tag, val in RE_XMP.findall(txt):
            f.setdefault(tag, val.strip())
        did = f.get('xmpMM:DocumentID')
        if did:
            out[str(k).lstrip('/')] = (did, f.get('xmp:ModifyDate', ''))
    return out


def asset_spans(data: bytes):
    """(property_name, start, end) for each outermost /MCn asset span."""
    events = []
    for m in RE_MARK.finditer(data):
        op = m.group(0)
        name = None
        if op == b'BDC':
            pre = data[max(0, m.start() - 60):m.start()]
            names = RE_NAME.findall(pre)
            if names:
                name = names[-1].decode('latin-1', 'replace')
        events.append((m.start(), m.end(), op, name))

    spans = []
    stack = []
    cur = None
    for start, end, op, name in events:
        if op == b'BDC':
            stack.append(name)
            # /MCn carries the XMP; /MCID and /Layout are text-structure marks
            if cur is None and name and name.startswith('MC') and not name.startswith('MCID'):
                cur = (name, end)
        else:
            if stack:
                popped = stack.pop()
                if cur and popped == cur[0]:
                    spans.append((cur[0], cur[1], start))
                    cur = None
    return spans


def span_geometry_hash(data: bytes, start: int, end: int):
    """Hash the path geometry inside one asset span, TRANSLATION-NORMALISED.

    ⚠ RAW OPERANDS DO NOT MATCH ACROSS PLACEMENTS, and the first version of this
    function assumed they would. Measured: one asset placed 12 times in a single
    manual gave 937 path operators EVERY time - identical structure - but seven
    different raw hashes, because the placement offset is baked into the flattened
    coordinates. Judging identity on raw operands reports 57 of 58 assets as
    "different geometry" when they are the same drawing moved.

    So the coordinates are shifted so the asset's own minimum x/y sits at the origin
    before hashing. Scale is deliberately NOT normalised: a drawing placed at two
    different sizes is still worth distinguishing, and the op count is reported
    alongside for the caller to judge.
    """
    chunk = data[start:end]
    ops = []
    pos = 0
    for m in RE_PATHOP.finditer(chunk):
        operands = RE_NUM.findall(chunk[pos:m.start()])
        pos = m.end()
        op = m.group(1).decode()
        try:
            nums = [float(x) for x in operands[-6:]]
        except ValueError:
            nums = []
        ops.append((op, nums))
    pts = [(v[i], v[i + 1]) for _, v in ops for i in range(0, len(v) - 1, 2)]
    if not pts:
        return None, 0
    minx = min(p[0] for p in pts)
    miny = min(p[1] for p in pts)
    parts = []
    for op, v in ops:
        if v:
            coords = []
            for i in range(0, len(v) - 1, 2):
                coords.append(f'{round(v[i] - minx, 1)}')
                coords.append(f'{round(v[i + 1] - miny, 1)}')
            parts.append(op + ':' + ','.join(coords))
        else:
            parts.append(op)
    ser = '|'.join(parts)
    return hashlib.sha256(ser.encode()).hexdigest()[:24], len(parts)


def doc_asset_geometry(path, page_limit=None):
    """DocumentID -> {geometry hashes seen for it} across one document."""
    from pypdf import PdfReader
    from dreame_diagram_fingerprint import contents
    reader = PdfReader(path)
    out = collections.defaultdict(set)
    sizes = {}
    for i in range(len(reader.pages)):
        if page_limit and i >= page_limit:
            break
        page = reader.pages[i]
        mapping = mc_to_docid(page)
        if not mapping:
            continue
        data = contents(page)
        if not data:
            continue
        for name, s, e in asset_spans(data):
            info = mapping.get(name)
            if not info:
                continue
            h, n = span_geometry_hash(data, s, e)
            if h:
                out[info[0]].add(h)
                sizes[info[0]] = max(sizes.get(info[0], 0), n)
    return out, sizes
