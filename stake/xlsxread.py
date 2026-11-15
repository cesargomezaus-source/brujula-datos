"""Lector minimo de .xlsx sin dependencias (openpyxl falla con los archivos de Stake:
'could not read stylesheet'). Devuelve cada hoja como lista de filas de texto."""
import zipfile, re
from xml.etree import ElementTree as ET

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
RNS = '{http://schemas.openxmlformats.org/package/2006/relationships}'


def col_to_idx(ref):
    m = re.match(r'([A-Z]+)', ref or '')
    if not m:
        return 0
    n = 0
    for ch in m.group(1):
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _shared(z):
    try:
        root = ET.fromstring(z.read('xl/sharedStrings.xml'))
    except KeyError:
        return []
    out = []
    for si in root.findall(NS + 'si'):
        out.append(''.join(t.text or '' for t in si.iter(NS + 't')))
    return out


def sheets(path):
    """[(nombre_hoja, [[celda, ...], ...]), ...]"""
    z = zipfile.ZipFile(path)
    ss = _shared(z)
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    relmap = {r.get('Id'): r.get('Target') for r in rels.findall(RNS + 'Relationship')}
    out = []
    for sh in wb.find(NS + 'sheets').findall(NS + 'sheet'):
        rid = sh.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        tgt = relmap.get(rid, '').lstrip('/')
        if not tgt.startswith('xl/'):
            tgt = 'xl/' + tgt
        try:
            data = z.read(tgt)
        except KeyError:
            continue
        root = ET.fromstring(data)
        rows = []
        for row in root.iter(NS + 'row'):
            cells = []
            for c in row.findall(NS + 'c'):
                i = col_to_idx(c.get('r'))
                while len(cells) <= i:
                    cells.append('')
                t = c.get('t')
                if t == 'inlineStr':
                    v = ''.join(x.text or '' for x in c.iter(NS + 't'))
                else:
                    ve = c.find(NS + 'v')
                    v = ve.text if ve is not None and ve.text is not None else ''
                    if t == 's' and v != '':
                        try:
                            v = ss[int(v)]
                        except (ValueError, IndexError):
                            pass
                cells.append(v)
            rows.append(cells)
        out.append((sh.get('name'), rows))
    return out
