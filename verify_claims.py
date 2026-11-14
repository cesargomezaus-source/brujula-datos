# Verificador de afirmaciones de la Brújula.
# Recalcula cada afirmación guardada en claims.json contra los precios de Yahoo y escribe
# data/claims_check.json con el valor medido, el esperado y si sigue cumpliéndose.
#
# No usa inteligencia artificial: son aritmética y una fuente de precios. La IA es lo que
# inventa datos; esto es lo que los comprueba. check.json valida los PRECIOS contra una
# segunda fuente (Nasdaq); este archivo valida las CONCLUSIONES sacadas de esos precios.
#
# Privacidad: solo activos públicos. Las posiciones de Cesar nunca entran aquí.
#
# Uso: python3 -I verify_claims.py claims.json data/claims_check.json
import json, sys, time, subprocess, urllib.parse, os
from datetime import datetime, timezone, date, timedelta

UA = 'Mozilla/5.0'
EPOCH = date(1970, 1, 1)


def curl(url):
    return subprocess.run(['curl', '-sS', '--max-time', '60', '-A', UA, url],
                          capture_output=True, text=True).stdout


def chart(sym):
    q = {'interval': '1d',
         'period1': int(datetime(2000, 1, 1, tzinfo=timezone.utc).timestamp()),
         'period2': int(time.time())}
    url = f'https://query2.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?' + urllib.parse.urlencode(q)
    for k in range(4):
        try:
            r = json.loads(curl(url))['chart']['result'][0]
            if r.get('timestamp'):
                return r
        except Exception:
            pass
        time.sleep(3 + 6 * k)
    raise RuntimeError('sin datos ' + sym)


def series(sym):
    """Devuelve {dia: (cierre_ajustado, maximo_sin_ajustar, minimo_sin_ajustar, cierre_sin_ajustar)}"""
    r = chart(sym)
    q = r['indicators']['quote'][0]
    ac = r['indicators'].get('adjclose', [{}])[0].get('adjclose')
    out = {}
    for i, ts in enumerate(r['timestamp']):
        c = q['close'][i]
        h = q['high'][i]
        l = q['low'][i]
        if c is None or c <= 0:
            continue
        d = (datetime.fromtimestamp(ts, timezone.utc).date() - EPOCH).days
        f = (ac[i] / c) if ac and ac[i] else 1.0
        out[d] = (c * f, h, l, c)
    return out


CACHE = {}


def get(sym):
    if sym not in CACHE:
        CACHE[sym] = series(sym)
    return CACHE[sym]


def dnum(s):
    if s in ('hoy', 'today'):
        return (datetime.now(timezone.utc).date() - EPOCH).days
    y, m, d = (int(x) for x in s.split('-'))
    return (date(y, m, d) - EPOCH).days


def dstr(t):
    return (EPOCH + timedelta(days=t)).isoformat()


def at(S, target, idx=0):
    """Valor del día pedido o del último día hábil anterior."""
    best = None
    for d in sorted(S):
        if d <= target:
            best = d
        else:
            break
    if best is None:
        return None, None
    return S[best][idx], best


def pct(a, b):
    return b / a - 1.0


def anual(a, b, dias):
    yrs = dias / 365.25
    if yrs <= 0:
        return None
    return (b / a) ** (1 / yrs) - 1


def medir(c):
    """Devuelve (calculado, detalle) o (None, motivo)."""
    t = c['tipo']
    if t == 'ret':
        S = get(c['activo'])
        d0, d1 = dnum(c['desde']), dnum(c['hasta'])
        a, da = at(S, d0)
        b, db = at(S, d1)
        if a is None or b is None:
            return None, 'sin precios en la ventana'
        v = pct(a, b) if c.get('metrica', 'total') == 'total' else anual(a, b, db - da)
        return v, {'ventana': [dstr(da), dstr(db)], 'desde_precio': round(a, 4), 'hasta_precio': round(b, 4)}
    if t == 'ret_compare':
        d0, d1 = dnum(c['desde']), dnum(c['hasta'])
        vals = {}
        for k in ('a', 'b'):
            S = get(c[k])
            x, dx = at(S, d0)
            y, dy = at(S, d1)
            if x is None or y is None:
                return None, f'sin precios para {c[k]}'
            vals[k] = (pct(x, y), dstr(dx), dstr(dy))
        return vals['a'][0] - vals['b'][0], {
            c['a']: round(vals['a'][0], 4), c['b']: round(vals['b'][0], 4),
            'ventana': [vals['a'][1], vals['a'][2]]}
    if t == 'level':
        S = get(c['activo'])
        idx = {'max': 1, 'min': 2, 'cierre': 3}[c.get('campo', 'cierre')]
        v, d = at(S, dnum(c['fecha']), idx)
        if v is None:
            return None, 'sin precio en esa fecha'
        return v, {'dia': dstr(d)}
    return None, f'tipo desconocido: {t}'


def juzgar(c, v):
    """ok / falla, y el desvío."""
    if 'esperado' in c:
        tol = c.get('tol', 0.01)
        return ('ok' if abs(v - c['esperado']) <= tol else 'falla'), round(v - c['esperado'], 6)
    if 'min' in c:
        return ('ok' if v >= c['min'] else 'falla'), round(v - c['min'], 6)
    if 'max' in c:
        return ('ok' if v <= c['max'] else 'falla'), round(v - c['max'], 6)
    if c.get('espera') == 'a>b':
        m = c.get('margen_min', 0.0)
        return ('ok' if v > m else 'falla'), round(v - m, 6)
    if c.get('espera') == 'a<b':
        m = c.get('margen_min', 0.0)
        return ('ok' if v < -m else 'falla'), round(v + m, 6)
    return 'sin_criterio', None


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else 'claims.json'
    dst = sys.argv[2] if len(sys.argv) > 2 else 'data/claims_check.json'
    doc = json.load(open(src, encoding='utf-8'))
    res = []
    for c in doc.get('claims', []):
        try:
            v, det = medir(c)
        except Exception as e:
            v, det = None, f'{type(e).__name__}: {e}'
        if v is None:
            res.append({'id': c['id'], 'estado': 'sin_datos', 'motivo': det,
                        'afirmacion': c.get('afirmacion', ''), 'fuente': c.get('fuente', '')})
            print(f"SIN DATOS {c['id']}: {det}", flush=True)
            continue
        estado, desvio = juzgar(c, v)
        res.append({'id': c['id'], 'estado': estado, 'calculado': round(v, 6),
                    'esperado': c.get('esperado', c.get('min', c.get('max', c.get('espera')))),
                    'tol': c.get('tol'), 'desvio': desvio, 'detalle': det,
                    'afirmacion': c.get('afirmacion', ''), 'fuente': c.get('fuente', '')})
        print(f"{estado.upper():9s} {c['id']:34s} medido {v:+.4f}  desvio {desvio}", flush=True)
    ok = sum(1 for r in res if r['estado'] == 'ok')
    fail = sum(1 for r in res if r['estado'] == 'falla')
    nod = sum(1 for r in res if r['estado'] == 'sin_datos')
    out = {'asof': int(time.time()), 'fecha': datetime.now(timezone.utc).date().isoformat(),
           'resumen': {'total': len(res), 'ok': ok, 'falla': fail, 'sin_datos': nod},
           'fuente_precios': 'Yahoo Finance (cierres ajustados por dividendo); los precios los valida aparte check.json contra Nasdaq',
           'claims': res}
    os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
    json.dump(out, open(dst, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    print(f'\nOK {dst}: {ok} se cumplen, {fail} fallan, {nod} sin datos, de {len(res)}')
    if fail:
        print('AVISO: hay afirmaciones que ya no se cumplen. Revisar canales.json y el Centro de mando.')


if __name__ == '__main__':
    main()
