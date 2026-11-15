#!/usr/bin/env python3
"""
Analizador de Stake — herramienta reutilizable.

Lee cualquier exportacion .xlsx de Stake (Investment Activity, Investment Income,
Portfolio Valuation) de cualquier cuenta y produce un informe unico.

Uso:
    python3 -I stake_report.py <carpeta o archivo> [...] [--md salida.md] [--json salida.json]

Reglas que respeta:
  - Nunca mezcla monedas. AUD y USD se informan por separado.
  - El coste medio INCLUYE comisiones y GST (es el numero que muestra Stake).
  - El P&L realizado usa coste medio movil, no FIFO, y lo dice en el informe.
  - No infiere motivos. Informa cifras; el porque lo pone Cesar.
  - Si un dato no esta en los archivos, escribe NO VERIFICADO. No lo rellena.
"""
import sys, os, glob, json, re
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xlsxread import sheets


# ---------- utilidades ----------

def num(x):
    if x is None:
        return 0.0
    s = str(x).strip().replace('$', '').replace(',', '').replace('%', '')
    if s in ('', '-'):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def clean(x):
    return str(x or '').strip()


def hdr_map(row):
    return {clean(c).lower(): i for i, c in enumerate(row) if clean(c)}


def get(row, hm, *names):
    for n in names:
        i = hm.get(n.lower())
        if i is not None and i < len(row):
            return row[i]
    return ''


def money(v, cur=''):
    s = f'{v:,.2f}'
    return f'{s} {cur}'.strip()


# ---------- lectura ----------

def read_file(path):
    """Devuelve {'path','report','name','period','generated','tables':{hoja:(hdr,rows)}}"""
    out = {'path': path, 'report': '', 'name': '', 'period': '', 'generated': '', 'tables': {}}
    for sheet, rows in sheets(path):
        flat = [clean(c) for r in rows for c in r if clean(c)]
        if sheet.lower() == 'summary':
            for t in flat:
                for key, fld in (('report type:', 'report'), ('name:', 'name'),
                                 ('statement date:', 'period'), ('date generated:', 'generated')):
                    if t.lower().startswith(key):
                        out[fld] = t.split(':', 1)[1].strip()
            continue
        if sheet.lower() == 'disclaimers':
            continue
        # primera fila con al menos 3 cabeceras no vacias
        hi = None
        for i, r in enumerate(rows):
            if sum(1 for c in r if clean(c)) >= 3:
                hi = i
                break
        if hi is None:
            continue
        hm = hdr_map(rows[hi])
        body = [r for r in rows[hi + 1:] if any(clean(c) for c in r)]
        if body:
            out['tables'][sheet] = (hm, body)
    return out


def collect(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            files += glob.glob(os.path.join(p, '**', '*.xlsx'), recursive=True)
        elif p.lower().endswith('.xlsx'):
            files.append(p)
    return sorted(set(files))


# ---------- parseo ----------

def parse_trades(f):
    out = []
    for sheet, (hm, rows) in f['tables'].items():
        if 'trade date' not in hm:
            continue
        mkt = 'Wall St' if 'wall' in sheet.lower() else ('Aus' if 'aus' in sheet.lower() else sheet)
        for r in rows:
            sym = clean(get(r, hm, 'Symbol'))
            if not sym:
                continue
            out.append({
                'date': clean(get(r, hm, 'Trade Date')),
                'settle': clean(get(r, hm, 'Settlement Date')),
                'mkt': mkt,
                'sym': sym,
                'name': clean(get(r, hm, 'Name')),
                'side': clean(get(r, hm, 'Side')).lower(),
                'id': clean(get(r, hm, 'Trade Identifier')),
                'units': num(get(r, hm, 'Units')),
                'price': num(get(r, hm, 'Avg. Price', 'Avg Price')),
                'value': num(get(r, hm, 'Value')),
                'fees': num(get(r, hm, 'Fees')),
                'gst': num(get(r, hm, 'GST')),
                'total': num(get(r, hm, 'Total Value')),
                'cur': clean(get(r, hm, 'Currency')) or ('USD' if mkt == 'Wall St' else 'AUD'),
            })
    return out


def parse_divs(f):
    out = []
    for sheet, (hm, rows) in f['tables'].items():
        if 'payment date' not in hm or 'trade date' in hm:
            continue
        mkt = 'Wall St' if 'wall' in sheet.lower() else ('Aus' if 'aus' in sheet.lower() else sheet)
        for r in rows:
            sym = clean(get(r, hm, 'Symbol'))
            if not sym:
                continue
            gross = num(get(r, hm, 'Total Amount'))
            wh = num(get(r, hm, 'Tax Withheld'))
            net = num(get(r, hm, 'Net Amount')) or (gross - wh)
            out.append({
                'date': clean(get(r, hm, 'Payment Date')),
                'mkt': mkt, 'sym': sym,
                'type': clean(get(r, hm, 'Type')),
                'gross': gross, 'withheld': wh, 'net': net,
                'franked': num(get(r, hm, 'Franked')),
                'credit': num(get(r, hm, 'Franking Credit')),
                'cur': clean(get(r, hm, 'Currency')) or ('USD' if mkt == 'Wall St' else 'AUD'),
            })
    return out


def parse_hold(f):
    out = []
    for sheet, (hm, rows) in f['tables'].items():
        if 'units' not in hm or 'trade date' in hm or 'payment date' in hm:
            continue
        if 'mkt. price' not in hm and 'mkt price' not in hm:
            continue
        mkt = 'Wall St' if 'wall' in sheet.lower() else ('Aus' if 'aus' in sheet.lower() else sheet)
        for r in rows:
            sym = clean(get(r, hm, 'Symbol'))
            if not sym:
                continue
            out.append({
                'mkt': mkt, 'sym': sym,
                'units': num(get(r, hm, 'Units')),
                'price': num(get(r, hm, 'Mkt. Price', 'Mkt Price')),
                'value': num(get(r, hm, 'Mkt. Value (US$)', 'Mkt. Value')),
                'value_aud': num(get(r, hm, 'Mkt. Value (A$)')),
                'weight': clean(get(r, hm, 'Weighting')),
                'asof': f['period'],
            })
    return out


# ---------- calculo ----------

def positions(trades):
    """Coste medio movil. Devuelve dict sym -> metricas."""
    by = defaultdict(list)
    for t in trades:
        by[t['sym']].append(t)
    out = {}
    for sym, ts in by.items():
        ts.sort(key=lambda x: (x['date'], x['id']))
        units = cost = 0.0
        bu = su = bc = sp = fees = 0.0
        realised = 0.0
        nb = ns = 0
        warn = []
        incompleto = False
        split = []
        for t in ts:
            # Stake escribe las ventas con unidades, valor y total en negativo.
            # Normalizamos: q = cantidad positiva; en compra el total es coste,
            # en venta el total negativo es el ingreso neto de comision.
            q = abs(t['units'])
            if t['side'].startswith('b'):
                units += q
                cost += t['total']          # incluye comision y GST
                bu += q; bc += t['total']; nb += 1
            else:
                net_in = -t['total']        # ingreso neto; negativo si la comision se lo come
                avg = cost / units if units > 1e-12 else 0.0
                sold = min(q, units) if units > 1e-12 else q
                if q - units > 1e-9:
                    warn.append(f"venta de {q:g} unidades con {units:g} en el libro")
                    incompleto = True
                if avg > 1e-9 and t['price'] > 1e-9:
                    r = t['price'] / avg
                    if r > 3 or r < 1 / 3:
                        split.append(f"vendido a {t['price']:,.2f} con coste medio {avg:,.2f} "
                                     f"({r:.1f}x) el {t['date']}")
                realised += net_in - avg * sold
                cost -= avg * sold
                units -= sold
                su += q; sp += net_in; ns += 1
            fees += t['fees'] + t['gst']
        # Cerrada: sin unidades, o con un residuo de valor despreciable (menos de 1 unidad
        # de moneda), que es lo que deja un plan de reinversion de fracciones.
        closed = abs(units) < 1e-6 or (ns > 0 and abs(cost) < 1.0)
        fiable = (ns > 0) and not incompleto and not split
        out[sym] = {
            'sym': sym, 'name': ts[0]['name'], 'mkt': ts[0]['mkt'], 'cur': ts[0]['cur'],
            'first': ts[0]['date'], 'last': ts[-1]['date'],
            'n_buy': nb, 'n_sell': ns, 'n': len(ts),
            'units_bought': bu, 'units_sold': su, 'units': 0.0 if closed else units,
            'cost_buys': bc, 'proceeds_sells': sp, 'fees': fees,
            'cost_open': 0.0 if closed else cost,
            'avg_cost': (cost / units) if units > 1e-12 else None,
            'realised': realised if ns else None,
            'fiable': fiable,
            'incompleto': incompleto,
            'split': split,
            'closed': closed and ns > 0,
            'warn': warn,
        }
    return out


def report(account, trades, divs, holds, files):
    L = []
    A = L.append
    A(f'## {account}')
    A('')
    periods = sorted({f['period'] for f in files if f['period']})
    A(f'**Archivos leidos:** {len(files)}')
    for f in files:
        A(f"- `{os.path.basename(f['path'])}` — {f['report'] or 'tipo NO VERIFICADO'} · {f['period'] or 'periodo NO VERIFICADO'}")
    A('')
    A(f"**Periodo cubierto por los datos:** {', '.join(periods) if periods else 'NO VERIFICADO'}")
    A('')

    if not trades:
        A('Sin operaciones en los archivos leidos.')
        A('')
    else:
        # --- 1. resumen por moneda
        A('### 1. Movimiento, por moneda')
        A('')
        A('| Moneda | Compras | Ventas | Operaciones | Comisiones+GST | Comisiones / compras |')
        A('|---|---:|---:|---:|---:|---:|')
        for cur in sorted({t['cur'] for t in trades}):
            ts = [t for t in trades if t['cur'] == cur]
            b = sum(t['total'] for t in ts if t['side'].startswith('b'))
            s = sum(-t['total'] for t in ts if not t['side'].startswith('b'))
            fe = sum(t['fees'] + t['gst'] for t in ts)
            pct = f'{fe / b * 100:.2f}%' if b else '—'
            A(f'| {cur} | {b:,.2f} | {s:,.2f} | {len(ts)} | {fe:,.2f} | {pct} |')
        A('')

        pos = positions(trades)

        # --- 2. posiciones abiertas
        openp = sorted([p for p in pos.values() if not p['closed'] and p['units'] > 1e-9],
                       key=lambda p: -p['cost_open'])
        A('### 2. Posiciones abiertas al cierre de los datos')
        A('')
        A('Coste medio movil, comisiones y GST incluidos. Es el numero comparable con «Average buy price» de Stake.')
        A('')
        A('| Simbolo | Mercado | Unidades | Coste total | Coste medio | Ops |')
        A('|---|---|---:|---:|---:|---:|')
        for p in openp:
            ac = f"{p['avg_cost']:,.4f} {p['cur']}" if p['avg_cost'] is not None else 'NO VERIFICADO'
            A(f"| {p['sym']} | {p['mkt']} | {p['units']:,.4f} | {money(p['cost_open'], p['cur'])} "
              f"| {ac} | {p['n']} |")
        A('')

        # --- 3. posiciones cerradas
        cl = sorted([p for p in pos.values() if p['closed']], key=lambda p: p['realised'] or 0)
        if cl:
            A('### 3. Posiciones cerradas por completo')
            A('')
            A('| Simbolo | Mercado | Compras | Ventas | Resultado | Comisiones+GST |')
            A('|---|---|---:|---:|---:|---:|')
            tot = defaultdict(float)
            fee_tot = defaultdict(float)
            cnt = defaultdict(int)
            neg = defaultdict(int)
            for p in cl:
                if p['fiable']:
                    res = f"{p['realised']:+,.2f} {p['cur']}"
                    tot[p['cur']] += p['realised']
                    fee_tot[p['cur']] += p['fees']
                    cnt[p['cur']] += 1
                    if p['realised'] < 0:
                        neg[p['cur']] += 1
                else:
                    res = 'NO VERIFICADO'
                A(f"| {p['sym']} | {p['mkt']} | {money(p['cost_buys'], '')} | {money(p['proceeds_sells'], '')} "
                  f"| {res} | {p['fees']:,.2f} |")
            A('')
            for cur in sorted(tot):
                A(f"**{cur}: {cnt[cur]} posiciones cerradas con dato fiable, {neg[cur]} en perdida. "
                  f"Resultado neto {tot[cur]:+,.2f} {cur}. "
                  f"Comisiones y GST de esas operaciones: {fee_tot[cur]:,.2f} {cur}.**")
            nf = [p['sym'] for p in cl if not p['fiable']]
            if nf:
                A('')
                A(f"Fuera del total por falta de datos: {', '.join(nf)}. El detalle esta en los avisos.")
            A('')
            A('El resultado es aritmetica, no un juicio sobre la decision. El motivo de cada venta lo pone Cesar.')
            A('')

        # --- 4. ventas parciales
        part = [p for p in pos.values() if p['n_sell'] and not p['closed']]
        if part:
            A('### 4. Posiciones con venta parcial')
            A('')
            A('| Simbolo | Unidades que quedan | Realizado hasta ahora | Coste medio de lo que queda |')
            A('|---|---:|---:|---:|')
            for p in sorted(part, key=lambda x: -abs(x['realised'] or 0)):
                ac = f"{p['avg_cost']:,.4f} {p['cur']}" if p['avg_cost'] is not None else 'NO VERIFICADO'
                res = f"{p['realised']:+,.2f} {p['cur']}" if p['fiable'] else 'NO VERIFICADO'
                A(f"| {p['sym']} | {p['units']:,.4f} | {res} | {ac} |")
            A('')

        # --- 5. avisos
        warns = [(p['sym'], w, 'hist') for p in pos.values() for w in p['warn']]
        warns += [(p['sym'], w, 'split') for p in pos.values() for w in p['split']]
        if warns:
            A('### Avisos de datos — leer antes de usar las cifras')
            A('')
            for s, w, k in warns:
                if k == 'hist':
                    A(f'- **{s}**: {w}. Las compras son de un ejercicio anterior al exportado, '
                      f'asi que el coste no esta en estos archivos y el resultado no se puede calcular.')
                else:
                    A(f'- **{s}**: {w}. Un salto asi suele ser un split inverso que la exportacion '
                      f'no aplica a las unidades. El resultado de ese simbolo queda sin verificar '
                      f'hasta comprobar el split.')
            A('')

        # --- 6. conciliacion con la valoracion
        if holds:
            A('### Conciliacion contra Portfolio Valuation')
            A('')
            A('| Simbolo | Unidades calculadas | Unidades en la valoracion | Diferencia |')
            A('|---|---:|---:|---:|')
            hm = {h['sym']: h for h in holds}
            for sym in sorted(set(list(hm) + [p['sym'] for p in openp])):
                calc = pos.get(sym, {}).get('units', 0.0)
                real = hm.get(sym, {}).get('units')
                if real is None:
                    A(f'| {sym} | {calc:,.4f} | no aparece | revisar |')
                else:
                    d = calc - real
                    flag = 'ok' if abs(d) < 1e-4 else ('ok (resto de fraccion)' if abs(d) < 0.01
                                                       else f'{d:+,.4f}')
                    A(f'| {sym} | {calc:,.4f} | {real:,.4f} | {flag} |')
            A('')
            A('Una diferencia significa que hay operaciones fuera del periodo exportado, o un plan de reinversion.')
            A('')

    # --- dividendos
    if divs:
        A('### Dividendos cobrados')
        A('')
        A('| Moneda | Bruto | Retenido | Neto | Pagos |')
        A('|---|---:|---:|---:|---:|')
        for cur in sorted({d['cur'] for d in divs}):
            ds = [d for d in divs if d['cur'] == cur]
            A(f"| {cur} | {sum(d['gross'] for d in ds):,.2f} | {sum(d['withheld'] for d in ds):,.2f} "
              f"| {sum(d['net'] for d in ds):,.2f} | {len(ds)} |")
        A('')
        fc = sum(d['credit'] for d in divs)
        if fc:
            A(f'Creditos de franqueo: {fc:,.2f} AUD.')
            A('')
        top = defaultdict(float)
        for d in divs:
            top[(d['sym'], d['cur'])] += d['net']
        A('Los diez que mas pagaron, neto:')
        A('')
        A('| Simbolo | Neto |')
        A('|---|---:|')
        for (s, c), v in sorted(top.items(), key=lambda kv: -kv[1])[:10]:
            A(f'| {s} | {v:,.2f} {c} |')
        A('')

    return '\n'.join(L)


def main(argv):
    md_out = json_out = None
    paths = []
    i = 0
    while i < len(argv):
        if argv[i] == '--md':
            md_out = argv[i + 1]; i += 2
        elif argv[i] == '--json':
            json_out = argv[i + 1]; i += 2
        else:
            paths.append(argv[i]); i += 1
    files = collect(paths)
    if not files:
        print('No encontre ningun .xlsx en:', paths)
        return 1

    parsed = [read_file(p) for p in files]
    accounts = defaultdict(list)
    for f in parsed:
        key = f['name'] or 'CUENTA NO VERIFICADA'
        accounts[key].append(f)

    blocks = ['# Informe de Stake', '',
              f'Generado por `stake_report.py` sobre {len(files)} archivo(s) exportado(s) de Stake.', '',
              'Metodo: coste medio movil con comisiones y GST incluidos. Las monedas no se mezclan nunca. '
              'Lo que no esta en los archivos aparece como NO VERIFICADO.', '']
    data = {}
    for acct, fs in sorted(accounts.items()):
        trades, divs, holds = [], [], []
        for f in fs:
            trades += parse_trades(f)
            divs += parse_divs(f)
            holds += parse_hold(f)
        blocks.append(report(acct, trades, divs, holds, fs))
        data[acct] = {'trades': trades, 'dividends': divs, 'holdings': holds,
                      'positions': positions(trades)}

    md = '\n'.join(blocks)
    if md_out:
        open(md_out, 'w').write(md)
        print('escrito', md_out)
    else:
        print(md)
    if json_out:
        json.dump(data, open(json_out, 'w'), indent=1, default=str)
        print('escrito', json_out)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
