# Brújula v4 — descarga precios diarios con volumen (Yahoo chart API) y fundamentales (quoteSummary).
# Si Yahoo limita las consultas, completa en este orden: fund.json de GitHub (otra red), core.json anterior, finnhub.io (clave en FINNHUB_KEY) y api.nasdaq.com.
# Modo GitHub: python3 -I build_data.py --fund data/fund.json
# Control de precios (GitHub): python3 -I build_data.py --check data/check.json
# Uso: python3 -I build_data.py CARPETA_SALIDA [core.json_anterior]   -> escribe CARPETA/core.json y CARPETA/t/<TICKER>.json
import json, sys, time, subprocess, urllib.parse, os, tempfile
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
NDX='AAPL ABNB ADBE ADI ADP ADSK AEP ALAB ALNY AMAT AMD AMGN AMZN APP ARM ASML AVGO AXON BKNG BKR CCEP CDNS CEG CMCSA COST CPRT CRWD CRWV CSCO CSX CTAS DASH DDOG DXCM EA EXC FANG FAST FER FTNT GEHC GILD GOOGL HON IDXX INTC INTU ISRG KDP KHC KLAC LIN LITE LRCX MAR MCHP MDLZ MELI META MNST MPWR MRVL MSFT MSTR MU NBIS NFLX NVDA NXPI ODFL ORLY PANW PAYX PCAR PDD PEP PLTR PYPL QCOM REGN RKLB ROP ROST SBUX SHOP SNDK SNPS STX TER TMUS TRI TSLA TTWO TXN VRTX WBD WDAY WDC WMT XEL'.split()
SPX='BRK-B JPM V MA UNH LLY XOM JNJ PG HD KO MRK ABBV CVX BAC ORCL CRM MCD DIS NKE IBM GE CAT GS MS T VZ PFE BA UBER VST TSM NOW RDDT DELL HPQ LMT NOC'.split()
ETF_US='SPY QQQ QQQM VT IWM RSP SCHD JEPI QYLD QQQI SPYI SMH SOXX GLD SLV TLT COPX CPER USO WEAT CORN XLE AINF.AS'.split()
COMM='FCX SCCO BHP RIO NEM GDX SIL'.split()  # materias primas: cobre, mineras de oro y plata
ASX='PMGOLD.AX HACK.AX FANG.AX SEMI.AX ETHI.AX QAU.AX IOZ.AX VAS.AX VGS.AX NDQ.AX A200.AX IVV.AX GDX.AX MNRS.AX BHP.AX CBA.AX CSL.AX WES.AX MQG.AX FMG.AX'.split()
REIT='VICI O ADC CPT BN OWL'.split()  # inmobiliario (REITs) y gestoras de activos alternativos
INTL='NVO NU BABA BB'.split()  # grandes extranjeras que cotizan en EE.UU.
OTRAS='AMC CHPT'.split()  # otras de EE.UU. que sigue la familia
LEV='TQQQ QLD SSO UPRO GGUS.AX LNAS.AX GNDQ.AX GHHF.AX G200.AX'.split()  # apalancados: solo para estudiar el riesgo, no son parte del método
CRYPTO=['BTC-USD','ETH-USD']
MAG=['AAPL','MSFT','NVDA','AMZN','GOOGL','META','TSLA','AVGO']
NAMES={'QQQM':'Nasdaq-100 (Invesco, versión barata de QQQ)','TQQQ':'Nasdaq-100 x3 diario (ProShares)','QLD':'Nasdaq-100 x2 diario (ProShares)','SSO':'S&P 500 x2 diario (ProShares)','UPRO':'S&P 500 x3 diario (ProShares)','GGUS.AX':'S&P 500 apalancado 2–2,9x en A$ (Betashares GGUS)','LNAS.AX':'Nasdaq-100 apalancado 2–2,75x en A$ (Global X LNAS)','GNDQ.AX':'Nasdaq-100 con 30–40% de deuda en A$ (Betashares GNDQ)','GHHF.AX':'Mundo con 30–40% de deuda en A$ (Betashares GHHF)','G200.AX':'ASX 200 con 30–40% de deuda (Betashares G200)','BABA':'Alibaba (ADR, US$)','BB':'BlackBerry','AMC':'AMC Entertainment (cines)','CHPT':'ChargePoint (carga de autos eléctricos)','NVO':'Novo Nordisk (ADR, US$)','NU':'Nu Holdings (Nubank)','VICI':'VICI Properties (casinos, REIT)','O':'Realty Income (REIT)','ADC':'Agree Realty (REIT)','CPT':'Camden Property Trust (apartamentos, REIT)','BN':'Brookfield Corporation','OWL':'Blue Owl Capital','AINF.AS':'Infraestructura de IA (iShares, US$)','NOW':'ServiceNow','LMT':'Lockheed Martin (defensa)','NOC':'Northrop Grumman (defensa)','RDDT':'Reddit','DELL':'Dell Technologies','HPQ':'HP Inc.','GDX':'Mineras de oro (VanEck, US$)','SIL':'Mineras de plata (Global X, US$)','GDX.AX':'Mineras de oro en A$ (VanEck GDX)','MNRS.AX':'Mineras de oro cubiertas en A$ (Betashares)','COPX':'Mineras de cobre (Global X)','CPER':'Cobre (futuros, US$)','USO':'Petróleo (futuros, US$)','WEAT':'Trigo (futuros, US$)','CORN':'Maíz (futuros, US$)','XLE':'Energía EE.UU. (sector)','FCX':'Freeport-McMoRan (cobre)','SCCO':'Southern Copper','BHP':'BHP (en EE.UU., US$)','RIO':'Rio Tinto (en EE.UU., US$)','NEM':'Newmont (oro)','HACK.AX':'Ciberseguridad global (Betashares HACK)','FANG.AX':'Tecnológicas globales FANG+ (Global X)','SEMI.AX':'Semiconductores globales (Global X)','ETHI.AX':'Sostenibles globales (Betashares ETHI)','QAU.AX':'Oro cubierto en A$ (Betashares QAU)','SPY':'S&P 500','QQQ':'Nasdaq-100','PMGOLD.AX':'Oro Perth Mint (A$)','GLD':'Oro (US$)','SLV':'Plata (US$)','BTC-USD':'Bitcoin','ETH-USD':'Ethereum','VT':'Mundo (todas las bolsas)','IWM':'Empresas pequeñas EE.UU.','RSP':'S&P 500 peso igual','TLT':'Bonos EE.UU. 20+ años','IOZ.AX':'ASX 200 (iShares)','VAS.AX':'ASX 300 (Vanguard)','VGS.AX':'Mundo sin Australia (Vanguard)','NDQ.AX':'Nasdaq-100 en A$ (Betashares)','A200.AX':'ASX 200 (Betashares)','IVV.AX':'S&P 500 en A$ (iShares)','SMH':'Semiconductores (VanEck)','SOXX':'Semiconductores (iShares)','SCHD':'Dividendos EE.UU. (Schwab)','JEPI':'Ingresos con opciones (JPMorgan)','QYLD':'Nasdaq con opciones (Global X)','QQQI':'Nasdaq con opciones (NEOS)','SPYI':'S&P 500 con opciones (NEOS)','GOOGL':'Alphabet (Google)','META':'Meta (Facebook)','BRK-B':'Berkshire Hathaway'}
def grp(s):
    if s in ('SPY','QQQ'): return 'Índices'
    if s in LEV: return 'Apalancados (más riesgo)'
    if s in ('PMGOLD.AX','GLD','SLV'): return 'Oro y plata'
    if s in MAG: return 'Las 7 Magníficas + Broadcom'
    if s in CRYPTO: return 'Cripto'
    if s in REIT: return 'Inmobiliario y gestoras'
    if s in INTL: return 'Extranjeras en EE.UU.'
    if s in OTRAS: return 'Otras de EE.UU.'
    if s.endswith('.AX'): return 'Australia (ASX)'
    if s in COMM or s in ('COPX','CPER','USO','WEAT','CORN','XLE'): return 'Materias primas'
    if s in ETF_US: return 'Fondos cotizados (ETF)'
    if s in NDX: return 'Nasdaq-100'
    return 'Grandes del S&P 500'
UNIV=list(dict.fromkeys(['SPY','QQQ','PMGOLD.AX','GLD','SLV']+MAG+CRYPTO+ETF_US+ASX+NDX+SPX+COMM+REIT+INTL+OTRAS+LEV))
AUX=['AUDUSD=X','GC=F','SI=F','^VIX','TLT','IEF','HYG','RSP','XLK','XLF','XLE','XLV','XLY','XLP','XLI','XLB','XLU','XLC','XLRE','BIL','VEU','AGG']
UA='Mozilla/5.0'
def curl(url,ck=None):
    return subprocess.run(['curl','-sS','--max-time','60','-A',UA]+(['-b',ck] if ck else [])+[url],capture_output=True,text=True).stdout
def chart(sym):
    q={'interval':'1d','period1':int(datetime(2004,1,1,tzinfo=timezone.utc).timestamp()),'period2':int(time.time())}
    url=f'https://query2.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?'+urllib.parse.urlencode(q)
    for k in range(4):
        try:
            r=json.loads(curl(url))['chart']['result'][0]
            if r.get('timestamp'): return r
        except Exception: pass
        time.sleep(3+6*k)
    raise RuntimeError('sin datos '+sym)
def sig(x): return float(f'{x:.5g}')
def flt_pack(Td,C):
    # cierres compactos para el filtro: últimos 520 diarios, últimos 520 semanales (semana = floor((día+3)/7), como la página) y todos los mensuales
    T=[];s=0
    for d in Td: s+=d; T.append(s)
    W=[];WT=[];M=[];MT=[];kw=km=None
    for t,c in zip(T,C):
        w=(t+3)//7; dt=datetime(1970,1,1)+__import__('datetime').timedelta(days=t); m=dt.year*12+dt.month-1
        if w!=kw: kw=w; W.append(c); WT.append(t)
        else: W[-1]=c; WT[-1]=t
        if m!=km: km=m; M.append(c); MT.append(t)
        else: M[-1]=c; MT[-1]=t
    return {'d':C[-520:],'dt':T[-1],'w':W[-520:],'m':M,'n':len(C)}
def delta(a): return [a[0]]+[a[i]-a[i-1] for i in range(1,len(a))]
def series(sym):
    r=chart(sym); q=r['indicators']['quote'][0]; ac=r['indicators'].get('adjclose',[{}])[0].get('adjclose')
    tz=ZoneInfo(r['meta'].get('exchangeTimezoneName','UTC')); seen=set(); T=[];O=[];H=[];L=[];C=[];V=[];RAW=[]
    for i,ts in enumerate(r['timestamp']):
        o,h,l,c,v=q['open'][i],q['high'][i],q['low'][i],q['close'][i],q['volume'][i]
        if None in (o,h,l,c) or c<=0: continue
        d=(datetime.fromtimestamp(ts,tz).date()-datetime(1970,1,1).date()).days
        if d in seen: continue
        seen.add(d); f=(ac[i]/c) if ac and ac[i] else 1.0
        RAW.append([d,float(c)])
        T.append(d);O.append(sig(o*f));H.append(sig(h*f));L.append(sig(l*f));C.append(sig(c*f));V.append(int(v or 0)//100)
    m=r['meta']
    if m.get('instrumentType')=='ETF':  # corrige errores de escala de Yahoo (p. ej. IVV.AX): picos de un día y cambios de nivel sin ajustar
        i=1
        while i<len(C):
            q=C[i]/C[i-1]
            if q>2.2 or q<0.45:
                if i+1<len(C) and 0.45<C[i+1]/C[i-1]<2.2:
                    for A in (T,O,H,L,C,V): del A[i]
                    continue
                for k in range(i):
                    O[k]=sig(O[k]*q);H[k]=sig(H[k]*q);L[k]=sig(L[k]*q);C[k]=sig(C[k]*q)
            i+=1
    return {'t':delta(T),'o':O,'h':H,'l':L,'c':C,'v':V,'cur':m.get('currency') or '','long':m.get('longName') or m.get('shortName') or sym,'type':m.get('instrumentType',''),'raw':RAW[-10:]}
def news(syms):
    out={}
    for s in syms:
        try:
            r=json.loads(curl(f'https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(s)}&quotesCount=0&newsCount=6&enableFuzzyQuery=false'))
            items=[]
            for n in r.get('news',[])[:6]:
                if not n.get('title') or not n.get('link'): continue
                items.append({'t':n['title'],'p':n.get('publisher',''),'u':n['link'],'ts':int(n.get('providerPublishTime') or 0)})
            if items: out[s]=items
        except Exception as e: print('AVISO noticias',s,e)
        time.sleep(0.25)
    return out
FS_TYPES='annualNetIncome,annualOperatingCashFlow,annualTotalAssets,annualLongTermDebt,annualCurrentAssets,annualCurrentLiabilities,annualGrossProfit,annualTotalRevenue,annualOrdinarySharesNumber,annualRetainedEarnings,annualEBIT,annualTotalLiabilitiesNetMinorityInterest'
def statements(syms,prices):
    # Piotroski F-score (9 puntos) y Z de Altman con los estados financieros anuales de Yahoo (fundamentals-timeseries, sin crumb)
    out={};p1=int(time.time())-5*365*86400;p2=int(time.time())
    for s in syms:
        try:
            r=json.loads(curl(f'https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{urllib.parse.quote(s)}?type={FS_TYPES}&period1={p1}&period2={p2}'))['timeseries']['result']
            D={}
            for row in r:
                t=[k for k in row if k.startswith('annual')]
                if not t: continue
                D[t[0][6:]]={x['asOfDate']:x['reportedValue']['raw'] for x in row[t[0]] if x.get('reportedValue')}
            dates=sorted(set().union(*[set(v) for v in D.values()]))
            if len(dates)<2: continue
            y1,y0=dates[-1],dates[-2]
            g=lambda k,y:(D.get(k) or {}).get(y)
            NI,CFO,TA,TA0=g('NetIncome',y1),g('OperatingCashFlow',y1),g('TotalAssets',y1),g('TotalAssets',y0)
            if None in (NI,CFO,TA,TA0) or not TA or not TA0: continue
            NI0=g('NetIncome',y0);LTD,LTD0=g('LongTermDebt',y1) or 0,g('LongTermDebt',y0) or 0
            CA,CL,CA0,CL0=g('CurrentAssets',y1),g('CurrentLiabilities',y1),g('CurrentAssets',y0),g('CurrentLiabilities',y0)
            SH,SH0=g('OrdinarySharesNumber',y1),g('OrdinarySharesNumber',y0);GP,GP0=g('GrossProfit',y1),g('GrossProfit',y0);REV,REV0=g('TotalRevenue',y1),g('TotalRevenue',y0)
            f=[]
            f.append(['Gana dinero (ROA > 0)',NI>0])
            f.append(['Genera caja (flujo operativo > 0)',CFO>0])
            f.append(['Rentabilidad mejora (ROA sube)',NI0 is not None and NI/TA>NI0/TA0])
            f.append(['La caja supera al beneficio (sin maquillaje)',CFO>NI])
            f.append(['Menos deuda larga sobre activos',LTD/TA<LTD0/TA0])
            f.append(['Más liquidez (ratio corriente sube)',None not in (CA,CL,CA0,CL0) and CL and CL0 and CA/CL>CA0/CL0])
            f.append(['No emitió acciones nuevas',SH is not None and SH0 is not None and SH<=SH0*1.001])
            f.append(['Margen bruto mejora',None not in (GP,GP0,REV,REV0) and REV and REV0 and GP/REV>GP0/REV0])
            f.append(['Vende más por cada dólar de activos',REV is not None and REV0 is not None and REV/TA>REV0/TA0])
            score=sum(1 for _,ok in f if ok)
            z=None
            RE,EBIT,TL=g('RetainedEarnings',y1),g('EBIT',y1),g('TotalLiabilitiesNetMinorityInterest',y1)
            px=prices.get(s)
            if None not in (CA,CL,RE,EBIT,TL,REV,SH) and TL and px:
                z=1.2*(CA-CL)/TA+1.4*RE/TA+3.3*EBIT/TA+0.6*(px*SH)/TL+1.0*REV/TA
            out[s]={'y':y1[:4],'f':score,'fx':[[n,bool(ok)] for n,ok in f],'z':round(z,2) if z is not None else None,'cfo':CFO,'ni':NI,'ltd':LTD,'ta':TA}
        except Exception as e: print('AVISO estados',s,e)
        time.sleep(0.25)
    return out
PM_QUERIES=['fed rate cut','us recession','bitcoin price','s&p 500','tariffs','government shutdown','nvidia','gold price','china taiwan','oil price','gold reserve revaluation','gold-backed bonds']
def polymarket():
    out=[];seen=set()
    for q in PM_QUERIES:
        try:
            d=json.loads(curl(f'https://gamma-api.polymarket.com/public-search?q={urllib.parse.quote(q)}&limit_per_type=4'))
            for e in d.get('events',[]):
                if e.get('closed') or e.get('slug') in seen: continue
                ms=[]
                for m in e.get('markets',[]):
                    if m.get('closed'): continue
                    try: pr=json.loads(m.get('outcomePrices') or '[]')
                    except Exception: pr=[]
                    if len(pr)<1: continue
                    ms.append({'q':m.get('question') or m.get('groupItemTitle') or '','p':float(pr[0]),'end':(m.get('endDate') or '')[:10]})
                ms=[m for m in ms if m['q']]
                if not ms: continue
                ms.sort(key=lambda m:-m['p'])
                seen.add(e['slug'])
                out.append({'k':q,'t':e.get('title',''),'u':'https://polymarket.com/event/'+e['slug'],'v':float(e.get('volume') or 0),'end':(e.get('endDate') or '')[:10],'m':ms[:5]})
        except Exception as ex: print('AVISO polymarket',q,ex)
        time.sleep(0.3)
    out.sort(key=lambda e:-e['v'])
    return out[:24]
CRUMB=CK=None
def caps(syms):
    # capitalización de mercado (en la moneda de cotización) con /v7/finance/quote; necesita la cookie y el crumb de fundamentals()
    out={}
    if not CRUMB: return out
    for i in range(0,len(syms),40):
        try:
            q=','.join(syms[i:i+40])
            r=json.loads(curl(f'https://query1.finance.yahoo.com/v7/finance/quote?symbols={urllib.parse.quote(q)}&fields=marketCap,currency&crumb={urllib.parse.quote(CRUMB)}',CK))['quoteResponse']['result']
            for x in r:
                if x.get('marketCap'): out[x['symbol']]=[x['marketCap'],x.get('currency','')]
        except Exception as e: print('AVISO capitalizacion',e)
        time.sleep(1)
    return out
def fundamentals(syms):
    ck=os.path.join(tempfile.mkdtemp(),'ck.txt')
    subprocess.run(['curl','-sS','-c',ck,'-A',UA,'https://fc.yahoo.com','-o','/dev/null'],capture_output=True)
    crumb=''
    for k,ua in enumerate(['Mozilla/5.0','Mozilla/5.0 (X11; Linux x86_64)','Mozilla/5.0 (Macintosh)','Mozilla/5.0 (Windows NT 10.0)']):
        subprocess.run(['curl','-sS','-c',ck,'-A',ua,'https://fc.yahoo.com','-o','/dev/null'],capture_output=True)
        crumb=subprocess.run(['curl','-sS','--max-time','30','-A',ua,'-b',ck,f'https://query{1+k%2}.finance.yahoo.com/v1/test/getcrumb'],capture_output=True,text=True).stdout.strip()
        if crumb and len(crumb)<40 and ' ' not in crumb and '<' not in crumb: break
        print('AVISO crumb',repr(crumb[:40]),flush=True); crumb=''; time.sleep(30+20*k)
    if not crumb: print('AVISO sin crumb: fundamentales vacíos'); return {}
    global CRUMB,CK
    CRUMB,CK=crumb,ck
    mods='summaryDetail,defaultKeyStatistics,financialData,netSharePurchaseActivity,majorHoldersBreakdown,calendarEvents,recommendationTrend'
    out={}
    for s in syms:
        try:
            r=json.loads(curl(f'https://query2.finance.yahoo.com/v10/finance/quoteSummary/{urllib.parse.quote(s)}?modules={mods}&crumb={urllib.parse.quote(crumb)}',ck))['quoteSummary']['result'][0]
            def g(m,k):
                x=(r.get(m) or {}).get(k); return x.get('raw') if isinstance(x,dict) else None
            ed=((r.get('calendarEvents') or {}).get('earnings') or {}).get('earningsDate') or []
            out[s]={'pe':g('summaryDetail','trailingPE'),'fpe':g('summaryDetail','forwardPE'),'roe':g('financialData','returnOnEquity'),
             'margin':g('financialData','profitMargins'),'revg':g('financialData','revenueGrowth'),'epsg':g('financialData','earningsGrowth'),
             'de':g('financialData','debtToEquity'),'tgt':g('financialData','targetMeanPrice'),'price':g('financialData','currentPrice'),
             'rec':g('financialData','recommendationMean'),'nAn':g('financialData','numberOfAnalystOpinions'),
             'short':g('defaultKeyStatistics','shortPercentOfFloat'),'inst':g('majorHoldersBreakdown','institutionsPercentHeld'),
             'insNet':g('netSharePurchaseActivity','netPercentInsiderShares'),'peg':g('defaultKeyStatistics','pegRatio'),'earn':(ed[0] or {}).get('raw') if ed else None,
             'yield':g('summaryDetail','yield') or g('summaryDetail','dividendYield')}
            # recomendaciones de los analistas este mes: [compra fuerte, compra, mantener, venta, venta fuerte]
            tr=[x for x in ((r.get('recommendationTrend') or {}).get('trend') or []) if x.get('period')=='0m']
            if tr:
                rt=[int(tr[0].get(k) or 0) for k in ('strongBuy','buy','hold','sell','strongSell')]
                if sum(rt)>0: out[s]['rt']=rt
            out[s]={k:v for k,v in out[s].items() if v is not None}
        except Exception as e: print('AVISO fundamentales',s,e)
        time.sleep(0.4)
    return out
def nasdaq(syms,fund,cap):
    # segunda fuente, sin clave: api.nasdaq.com. Rellena lo que Yahoo no entregó (analistas, objetivo, capitalización). Solo EE.UU.
    def get(u):
        out=subprocess.run(['curl','-sS','--max-time','30','-A',UA,'-H','Accept: application/json',u],capture_output=True,text=True).stdout
        return json.loads(out).get('data') or {}
    n=0
    for s in syms:
        if s.endswith('.AX') or '-USD' in s: continue
        q=urllib.parse.quote(s.replace('-','.'))
        f=fund.setdefault(s,{})
        try:
            if 'rt' not in f or f.get('tgt') is None:
                c=(get(f'https://api.nasdaq.com/api/analyst/{q}/targetprice').get('consensusOverview') or {})
                b,h,se=int(c.get('buy') or 0),int(c.get('hold') or 0),int(c.get('sell') or 0)
                if b+h+se>0 and 'rt' not in f: f['rt']=[0,b,h,se,0]; f['rtsrc']='Nasdaq'; n+=1
                if f.get('tgt') is None and c.get('priceTarget'): f['tgt']=float(c['priceTarget'])
                time.sleep(0.3)
            if s not in cap:
                d=(get(f'https://api.nasdaq.com/api/quote/{q}/summary?assetclass=stocks').get('summaryData') or {})
                mc=((d.get('MarketCap') or {}).get('value') or '').replace(',','').replace('$','')
                if mc.replace('.','',1).isdigit() and float(mc)>0: cap[s]=[float(mc),'USD']
                time.sleep(0.3)
        except Exception as e: print('AVISO nasdaq',s,e)
        if not f: fund.pop(s,None)
    print('nasdaq: analistas',n,'· capitalizaciones',len(cap))
def finnhub(syms,fund,cap):
    # tercera fuente: finnhub.io con clave gratis en la variable FINNHUB_KEY (nunca escrita en este archivo). Solo rellena lo que falta.
    key=os.environ.get('FINNHUB_KEY','').strip()
    if not key: print('finnhub: sin clave, se omite'); return
    def get(path):
        u=f'https://finnhub.io/api/v1/{path}&token={urllib.parse.quote(key)}'
        return json.loads(subprocess.run(['curl','-sS','--max-time','30',u],capture_output=True,text=True).stdout or 'null')
    nr=nm=0
    for s in syms:
        if '-USD' in s or s.endswith('.AX'): continue  # el plan gratis de Finnhub no cubre la ASX
        f=fund.setdefault(s,{});q=urllib.parse.quote(s.replace('-','.'))
        try:
            if 'rt' not in f:
                r=get(f'stock/recommendation?symbol={q}')
                if isinstance(r,list) and r:
                    rt=[int(r[0].get(k) or 0) for k in ('strongBuy','buy','hold','sell','strongSell')]
                    if sum(rt)>0: f['rt']=rt; f['rtsrc']='Finnhub'; nr+=1
                time.sleep(1.1)
            if any(k not in f for k in ('pe','roe','margin')) or s not in cap:
                m=(get(f'stock/metric?symbol={q}&metric=all') or {}).get('metric') or {}
                pct=lambda k:(m[k]/100 if isinstance(m.get(k),(int,float)) else None)
                add={'pe':m.get('peTTM'),'roe':pct('roeTTM'),'margin':pct('netProfitMarginTTM'),'revg':pct('revenueGrowthQuarterlyYoy'),
                     'epsg':pct('epsGrowthQuarterlyYoy'),'yield':pct('dividendYieldIndicatedAnnual'),
                     'de':(m['totalDebt/totalEquityQuarterly']*100 if isinstance(m.get('totalDebt/totalEquityQuarterly'),(int,float)) else None)}
                k0=len(f)
                for k,v in add.items():
                    if v is not None and k not in f: f[k]=v
                if len(f)>k0: nm+=1
                if s not in cap and isinstance(m.get('marketCapitalization'),(int,float)) and m['marketCapitalization']>0:
                    cap[s]=[m['marketCapitalization']*1e6,'AUD' if s.endswith('.AX') else 'USD']
                time.sleep(1.1)
        except Exception as e: print('AVISO finnhub',s,e)
        if not f: fund.pop(s,None)
    print('finnhub: analistas',nr,'· fundamentales completados',nm)
GH_FUND='https://raw.githubusercontent.com/cesargomezaus-source/brujula-datos/main/data/fund.json'
def github_fund(fund,cap):
    # fundamentales que descarga GitHub cada día desde otros servidores (modo --fund). Se usan si tienen menos de 4 días.
    try:
        d=json.loads(subprocess.run(['curl','-sS','--max-time','60',GH_FUND],capture_output=True,text=True).stdout)
        age=(time.time()-d['asof'])/86400
        if age>4: print('github: fund.json viejo,',round(age,1),'días'); return
        n=0
        for k,v in (d.get('fund') or {}).items():
            f=fund.setdefault(k,{})
            for kk,vv in v.items():
                if kk not in f: f[kk]=vv
            n+=1
        for k,v in (d.get('cap') or {}).items(): cap.setdefault(k,v)
        print('github: fundamentales de',n,'activos, de hace',round(age,1),'días')
    except Exception as e: print('AVISO github fund',e)
GH_CHECK='https://raw.githubusercontent.com/cesargomezaus-source/brujula-datos/main/data/check.json'
def nq_sym(s):
    # solo acciones y ETF de EE.UU.; Nasdaq usa BRK.B en vez de BRK-B
    if '.' in s or '=' in s or '^' in s or s in CRYPTO: return None
    return s.replace('-','.')
def nasdaq_closes(s,etf):
    n=nq_sym(s)
    if not n: return []
    u=f"https://api.nasdaq.com/api/quote/{urllib.parse.quote(n)}/historical?assetclass={'etf' if etf else 'stocks'}&fromdate={(datetime.now(timezone.utc)-__import__('datetime').timedelta(days=20)).date()}&limit=15"
    try:
        r=((json.loads(curl(u)).get('data') or {}).get('tradesTable') or {}).get('rows') or []
        out=[]
        for x in r:
            mm,dd,yy=x['date'].split('/'); d=(datetime(int(yy),int(mm),int(dd)).date()-datetime(1970,1,1).date()).days
            out.append([d,float(x['close'].replace('$','').replace(',',''))])
        return out
    except Exception: return []
def check_prices(syms):
    # modo GitHub: últimos cierres SIN ajustar de Yahoo (desde la red de GitHub) y de Nasdaq (otra fuente)
    y={};n={}
    for s in syms:
        try:
            r=chart_short(s); q=r['indicators']['quote'][0]['close']
            tz=ZoneInfo(r['meta'].get('exchangeTimezoneName','UTC'))
            y[s]=[[(datetime.fromtimestamp(ts,tz).date()-datetime(1970,1,1).date()).days,float(c)] for ts,c in zip(r['timestamp'],q) if c]
            etf=r['meta'].get('instrumentType')=='ETF'
        except Exception as e: print('AVISO check',s,e); etf=False
        v=nasdaq_closes(s,etf)
        if v: n[s]=v
        time.sleep(0.3)
    return y,n
def chart_short(sym):
    url=f'https://query2.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range=1mo&interval=1d'
    for k in range(3):
        try:
            r=json.loads(curl(url))['chart']['result'][0]
            if r.get('timestamp'): return r
        except Exception: pass
        time.sleep(3+5*k)
    raise RuntimeError('sin datos '+sym)
def qc_prices(raw):
    # compara el último cierre local con GitHub-Yahoo y con Nasdaq en las mismas fechas; >1% = diferencia
    try:
        d=json.loads(subprocess.run(['curl','-sS','--max-time','60',GH_CHECK],capture_output=True,text=True).stdout)
    except Exception as e:
        print('QC precios: check.json no disponible',e); return {'ok':False}
    age=(time.time()-d.get('asof',0))/86400
    bad=[];nc=0
    for s,loc in raw.items():
        L=dict((a,b) for a,b in loc)
        for src in ('y','n'):
            R=dict((a,b) for a,b in (d.get(src) or {}).get(s,[]))
            com=sorted(set(L)&set(R))
            if not com: continue
            t=com[-1]; nc+=1
            if R[t]>0 and abs(L[t]/R[t]-1)>0.01:
                bad.append({'s':s,'d':t,'src':'GitHub-Yahoo' if src=='y' else 'Nasdaq','local':L[t],'otro':R[t]})
    print('QC precios:',nc,'comparaciones,',len(bad),'diferencias >1%, check.json de hace',round(age,1),'días')
    for b in bad[:20]: print('  QC diferencia',b['s'],b['src'],b['local'],'vs',b['otro'])
    return {'ok':True,'asof':d.get('asof'),'n':nc,'bad':bad}
if len(sys.argv)>2 and sys.argv[1]=='--check':
    y,n=check_prices(UNIV+[s for s in LEV if s not in UNIV])
    os.makedirs(os.path.dirname(sys.argv[2]) or '.',exist_ok=True)
    json.dump({'asof':int(time.time()),'y':y,'n':n},open(sys.argv[2],'w'),separators=(',',':'))
    print('OK check',len(y),'Yahoo',len(n),'Nasdaq'); sys.exit(0)
if len(sys.argv)>2 and sys.argv[1]=='--fund':
    # modo GitHub: solo fundamentales, capitalización y analistas -> un JSON pequeño
    ETF_AX={s for s in ASX if s not in ('BHP.AX','CBA.AX','CSL.AX','WES.AX','MQG.AX','FMG.AX')}
    st=[s for s in UNIV if s not in ETF_US and s not in CRYPTO and s not in ETF_AX and s not in LEV and s not in ('GLD','SLV','GDX','SIL','PMGOLD.AX','VT','IWM','RSP')]
    fd=fundamentals(st+['SPY','QQQ']);cp=caps(st)
    eq=[s for s in st if s not in ('SPY','QQQ')]
    finnhub(eq,fd,cp);nasdaq(eq,fd,cp)
    os.makedirs(os.path.dirname(sys.argv[2]) or '.',exist_ok=True)
    json.dump({'asof':int(time.time()),'fund':fd,'cap':cp},open(sys.argv[2],'w'),separators=(',',':'),ensure_ascii=False)
    print('OK fund',len(fd),'fundamentales',len(cp),'capitalizaciones',sum(1 for v in fd.values() if 'rt' in v),'con analistas'); sys.exit(0)
OUT=sys.argv[1]; os.makedirs(os.path.join(OUT,'t'),exist_ok=True)
core={'asof':int(time.time()),'list':[],'aux':{},'fund':{},'board':['SPY','QQQ','PMGOLD.AX']+MAG+['BTC-USD']}
FLT={};RAWC={}
for s in UNIV:
    try: x=series(s)
    except Exception as e: print('AVISO',s,e); continue
    if len(x['c'])<300: print('AVISO pocos datos',s); continue
    fn=s.replace('^','_').replace('=','_')+'.json'
    json.dump({k:x[k] for k in ('t','o','h','l','c','v')},open(os.path.join(OUT,'t',fn),'w'),separators=(',',':'))
    core['list'].append({'s':s,'n':NAMES.get(s,x['long']),'g':grp(s),'cur':x['cur'],'f':fn,'type':('ETF' if s in LEV else x['type'])})
    FLT[s]=flt_pack(x['t'],x['c']); RAWC[s]=x['raw']
    print(s,len(x['c']),flush=True)
for s in AUX:
    try: x=series(s)
    except Exception as e: print('AVISO aux',s,e); continue
    core['aux'][s]={'t':x['t'],'c':x['c'],'v':x['v']}
stocks=[e['s'] for e in core['list'] if e['type']=='EQUITY']+['SPY','QQQ']
core['fund']=fundamentals(stocks)
core['cap']=caps([e['s'] for e in core['list'] if e['type']=='EQUITY'])
print('capitalizaciones',len(core['cap']))
github_fund(core['fund'],core['cap'])  # solo rellena lo que Yahoo no entregó
if len(core['cap'])<100 and len(sys.argv)>2:
    try:
        for k,v in (json.load(open(sys.argv[2])).get('cap') or {}).items(): core['cap'].setdefault(k,v)
    except Exception as e: print('AVISO cap anterior',e)
if len(core['fund'])<100 and len(sys.argv)>2:
    try:
        prev=json.load(open(sys.argv[2]))
        for k,v in (prev.get('fund') or {}).items(): core['fund'].setdefault(k,v)
        for k,v in (prev.get('cap') or {}).items(): core['cap'].setdefault(k,v)
        print('fundamentales del core anterior, total',len(core['fund']))
    except Exception as e: print('AVISO core anterior',e)
finnhub([e['s'] for e in core['list'] if e['type']=='EQUITY'],core['fund'],core['cap'])
nasdaq([e['s'] for e in core['list'] if e['type']=='EQUITY'],core['fund'],core['cap'])
core['news']=news([e['s'] for e in core['list']])
print('noticias',len(core['news']))
prices={e['s']:(core['fund'].get(e['s'],{}).get('price')) for e in core['list']}
core['fs']=statements([e['s'] for e in core['list'] if e['type']=='EQUITY'],prices)
print('estados',len(core['fs']))
core['pm']=polymarket()
print('polymarket',len(core['pm']))
have={e['s'] for e in core['list']}
for s in ['SPY','QQQ','NVDA','BTC-USD','PMGOLD.AX']: assert s in have, s
assert len(core['list'])>=150, len(core['list'])
if len(core['fund'])<100: print('AVISO pocos fundamentales',len(core['fund']))
core['qc']=qc_prices(RAWC)
json.dump(core,open(os.path.join(OUT,'core.json'),'w'),separators=(',',':'),ensure_ascii=False)
json.dump(FLT,open(os.path.join(OUT,'flt.json'),'w'),separators=(',',':'))
print('OK',OUT,len(core['list']),'activos',len(core['fund']),'con fundamentales')
