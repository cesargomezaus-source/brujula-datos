# Analizador de Stake

Herramienta reutilizable. Lee cualquier exportación `.xlsx` de Stake y produce un
informe único, con las cifras de todas las cuentas separadas por cuenta y por moneda.

## Uso

    python3 -I stake/stake_report.py <carpeta con los .xlsx> --md informe.md --json datos.json

Acepta carpetas o archivos sueltos, y cualquier combinación de estos informes de Stake:

| Informe de Stake | Para qué se usa |
|---|---|
| Investment Activity | operaciones, coste medio, resultado realizado, comisiones |
| Investment Income | dividendos, retención, créditos de franqueo |
| Portfolio Valuation | conciliación: unidades calculadas contra unidades reales |

La cuenta se toma de la hoja «Summary» del propio archivo, no del nombre del fichero.

## Reglas que respeta

- **Nunca mezcla monedas.** AUD y USD se informan por separado, siempre.
- **El coste medio incluye comisión y GST.** Es el número comparable con
  «Average buy price» de Stake. Calcularlo desde «Return $» deja la comisión fuera
  y da un número bajo.
- **Signos de Stake.** Las ventas salen con unidades, valor y total en negativo;
  el script los normaliza. Sin esa corrección las ventas suman unidades a la posición.
- **Coste medio móvil, no FIFO.** Lo dice en el encabezado del informe.
- **Lo que no está en los archivos se escribe NO VERIFICADO.** No se rellena ni se estima.
- **No infiere motivos.** Informa el resultado; el porqué de cada venta lo pone el titular.

## Trampas que detecta y marca

- **Compras de un ejercicio anterior al exportado.** Si hay una venta sin unidades en el
  libro, el coste no está en los archivos: el resultado de ese símbolo queda
  NO VERIFICADO y fuera del total.
- **Split inverso.** Si el precio de venta se separa del coste medio más de 3x
  (o menos de 1/3), lo marca: la exportación no ajusta las unidades y el resultado
  sería falso.
- **Restos de fracciones.** Una posición con menos de una unidad de moneda de coste
  cuenta como cerrada, que es lo que deja un plan de reinversión.
- **Conciliación.** Compara las unidades que calcula contra las de Portfolio Valuation.
  Una diferencia significa operaciones fuera del periodo exportado.

## Privacidad

Las cifras de las cuentas **no entran en este repositorio**. El `.gitignore` bloquea
`*.xlsx`, `informe*.md` y `stake*.json` para que no puedan subirse por error.
Aquí vive el código; los informes se quedan donde se generan.
