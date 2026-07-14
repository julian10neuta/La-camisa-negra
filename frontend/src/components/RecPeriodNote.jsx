// src/components/RecPeriodNote.jsx
// ----------------------------------------------------------------------------
// La línea que le dice al usuario qué período de recomendaciones está viendo y
// cuándo se renueva: "Tu selección semanal · se renueva en 3 días".
//
// Es un componente compartido (Dashboard y Home lo usan) para que el texto y la
// forma de contar los días vivan en un solo sitio.
//
// La fecha de renovación la calcula el BACKEND y viene en la respuesta
// (`next_refresh`). Aquí no se recalcula: cuándo caduca una lista es una regla
// del motor, y duplicarla en el cliente significaría tener que acordarse de
// cambiarla en dos sitios.
// ----------------------------------------------------------------------------

const LABEL = {
  weekly: "semanal",
  monthly: "mensual",
};

// El backend serializa con `datetime.utcnow().isoformat()`, que NO lleva marca de
// zona horaria ("2026-07-14T10:00:00"). JavaScript interpreta una fecha así como
// hora LOCAL, no UTC: en Colombia (UTC-5) saldrían 5 horas de desfase, de sobra
// para equivocar la cuenta de días. Le añadimos la "Z" para que se lea como UTC,
// que es lo que realmente es.
function parseUtc(iso) {
  if (!iso) return null;
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(iso);
  const date = new Date(hasZone ? iso : `${iso}Z`);
  return isNaN(date.getTime()) ? null : date;
}

// Días de CALENDARIO que faltan, no bloques de 24 horas. La diferencia importa:
// contando bloques, algo que vence dentro de 2 horas da "1 día" y se anunciaría
// como "mañana", cuando en realidad es hoy. "Hoy" y "mañana" son casillas del
// calendario, así que se comparan los dos días a partir de su medianoche local.
function calendarDaysUntil(date) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(date);
  target.setHours(0, 0, 0, 0);
  return Math.round((target.getTime() - today.getTime()) / 86_400_000);
}

function refreshText(nextRefresh) {
  const date = parseUtc(nextRefresh);
  if (!date) return null;

  // Ya venció. Ojo: NO se renueva sola. Abrir la app dispararía una ráfaga de
  // 30-50 llamadas a Spotify, y eso ya nos costó dos baneos, así que ahora
  // regenerar es un acto explícito del usuario (el botón "Actualizar").
  if (date.getTime() <= Date.now()) return "toca actualizarla";

  const days = calendarDaysUntil(date);
  if (days <= 0) return "se renueva hoy";
  if (days === 1) return "se renueva mañana";
  return `se renueva en ${days} días`;
}

export default function RecPeriodNote({ period, nextRefresh, className = "" }) {
  const label = LABEL[period];
  if (!label) return null;

  const when = refreshText(nextRefresh);
  return (
    <span className={"rec-period " + className}>
      Tu selección {label}
      {when && <span className="rec-period__when"> · {when}</span>}
    </span>
  );
}
