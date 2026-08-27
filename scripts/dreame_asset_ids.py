"""Clone detection from DECLARED asset identity, not from drawing shape.

Chris's question: do the objects in the PDF have declared names? They do. Every placed
illustration is wrapped in marked content whose /Properties entry carries an XMP packet
with Adobe's asset identifiers:

    xmpMM:DocumentID          the SOURCE Illustrator document the graphic came from
    xmpMM:InstanceID          unique per placement - too unique to join on
    xmp:CreateDate / ModifyDate
    stDim:w / stDim:h         the asset's own dimensions in millimetres
    stEvt:instanceID / when   the edit history chain

This is a string join, not a shape comparison, and it is ~100x cheaper than the
geometry pass (0.1-0.4 s per document against 0.4-4.4 s).

⚠ DocumentID IS THE SOURCE FILE, NOT THE MODEL. A first probe found the Roller manual
sharing 30 DocumentIDs with the X40 while sharing only 4 with the Track - the opposite
of what model identity would predict. Dreame places graphics from shared library files,
so a raw DocumentID join measures library reuse.

WHICH IS WHY DOCUMENT FREQUENCY DECIDES IT, exactly as it did for the shape tier: an
identifier present in most manuals is library furniture, and an identifier present in
only two or three is a model-specific drawing. Those few documents are the clone
candidates, and reg codes tell us independently whether they are the same machine.
"""
import os
import re

RE_FIELD = re.compile(
    r'<(xmpMM:DocumentID|xmpMM:InstanceID|xmp:CreateDate|xmp:ModifyDate)>([^<]{1,120})<')
RE_DIM = re.compile(r'<stDim:(w|h)>([0-9.]+)<')


def doc_asset_ids(path, page_limit=None):
    """Declared asset identities placed in one document.

    Returns (docids, assets, n_blocks) where `assets` pairs a DocumentID with the
    asset's modify date and millimetre dimensions - a tighter key than the bare
    DocumentID, so two placements of DIFFERENT versions of one source file do not
    collapse together.
    """
    from pypdf import PdfReader
    reader = PdfReader(path)
    docids = set()
    assets = set()
    blocks = 0
    for i in range(len(reader.pages)):
        if page_limit and i >= page_limit:
            break
        try:
            res = reader.pages[i]['/Resources'].get_object()
        except Exception:
            continue
        props = res.get('/Properties')
        if props is None:
            continue
        try:
            props = props.get_object()
        except Exception:
            continue
        for k in props:
            try:
                o = props[k].get_object()
                md = o.get('/Metadata')
                if md is None:
                    continue
                txt = md.get_object().get_data().decode('utf-8', 'replace')
            except Exception:
                continue
            blocks += 1
            f = {}
            for tag, val in RE_FIELD.findall(txt):
                f.setdefault(tag, val.strip())
            dims = dict(RE_DIM.findall(txt))
            did = f.get('xmpMM:DocumentID')
            if not did:
                continue
            docids.add(did)
            assets.add((did,
                        f.get('xmp:ModifyDate', ''),
                        dims.get('w', ''), dims.get('h', '')))
    return docids, assets, blocks
