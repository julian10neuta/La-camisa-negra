// src/pages/Chat.jsx
// ----------------------------------------------------------------------------
// Pantalla de Chat IA: preguntar sobre una canción.
//
// Detrás está el rag_service, que NO deja al modelo responder de memoria: busca
// el artículo de Wikipedia de la canción y le prohíbe usar cualquier otra cosa.
// Por eso cada respuesta trae su fuente enlazada, y por eso a veces contesta
// "el artículo no dice nada sobre eso" — eso no es un fallo, es el diseño.
//
// Se llega aquí de dos formas y las dos acaban en este mismo componente:
//   - desde el menú, sin canción -> se preselecciona la que está sonando, y si
//     no hay nada sonando, se elige una con el buscador de aquí;
//   - desde el botón 💬 de Búsqueda -> con ?track=... y la canción ya puesta.
// ----------------------------------------------------------------------------

import { useEffect, useRef, useState } from "react";
import { useLocation, useSearchParams } from "react-router-dom";

import { askAboutSong, searchSongs } from "../api";
import Layout from "../components/Layout";
import { usePlayer } from "../player/PlayerContext";

// Se muestran cuando el chat está vacío: dan una idea de qué se le puede
// preguntar, que si no la pantalla en blanco no sugiere nada.
const SUGERENCIAS = [
  "¿De qué trata esta canción?",
  "¿Cuándo y cómo se grabó?",
  "¿Qué historia hay detrás?",
  "¿Quién la escribió?",
];

export default function Chat() {
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const { current } = usePlayer();

  const trackParam = params.get("track");

  // La canción sobre la que se pregunta. Puede venir de tres sitios, en orden:
  //  1. el estado de navegación (el botón de Búsqueda nos pasa la metadata,
  //     así evitamos una petición solo para saber el título);
  //  2. lo que esté sonando;
  //  3. el buscador de esta misma pantalla.
  const [song, setSong] = useState(() => location.state?.song || null);

  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const endRef = useRef(null);

  // Si llegamos con ?track= pero sin metadata (por ejemplo, alguien pegó la URL
  // o recargó la página), al menos sabemos el id: mostramos eso hasta que la
  // primera respuesta del backend nos devuelva el nombre real.
  useEffect(() => {
    if (trackParam && !song) {
      setSong({ spotify_track_id: trackParam, name: null, artist: null });
    }
  }, [trackParam, song]);

  // Sin canción y sin parámetro: la que esté sonando es la apuesta más probable.
  useEffect(() => {
    if (!trackParam && !song && current?.spotify_track_id) {
      setSong(current);
    }
  }, [trackParam, song, current]);

  // Bajar al último mensaje cuando llega uno nuevo. La llamada va con `?.`
  // porque scrollIntoView no existe en todos los entornos (jsdom, por ejemplo)
  // y desplazar la vista es un adorno: si no se puede, no pasa nada.
  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [messages, loading]);

  function cambiarCancion(nueva) {
    setSong(nueva);
    // El historial pertenece a la canción anterior: mezclarlos confundiría.
    setMessages([]);
    setError(null);
    setParams(nueva ? { track: nueva.spotify_track_id } : {}, { replace: true });
  }

  async function preguntar(texto) {
    const limpia = texto.trim();
    if (!limpia || !song || loading) return;

    setMessages((prev) => [...prev, { role: "user", text: limpia }]);
    setQuestion("");
    setLoading(true);
    setError(null);

    try {
      const data = await askAboutSong(song.spotify_track_id, limpia);

      // El backend nos devuelve el nombre real; aprovechamos para completarlo
      // si habíamos entrado solo con el id.
      if (data.song?.name && !song.name) {
        setSong((prev) => ({ ...prev, ...data.song }));
      }

      setMessages((prev) => [...prev, { role: "assistant", ...data }]);
    } catch (e) {
      setError(e.message || "No se pudo consultar.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Layout>
      <h1 className="page-title">Chat IA</h1>
      <p className="page-subtitle">
        Pregunta sobre una canción. Las respuestas salen de Wikipedia y siempre
        vienen con su fuente: si el artículo no lo dice, la IA no se lo inventa.
      </p>

      {!song ? (
        <SelectorDeCancion onPick={cambiarCancion} />
      ) : (
        <>
          <CabeceraCancion song={song} onChange={() => cambiarCancion(null)} />

          <div className="chat-log">
            {messages.length === 0 && !loading && (
              <div className="chat-empty">
                <p>¿Qué quieres saber?</p>
                <div className="chat-chips">
                  {SUGERENCIAS.map((s) => (
                    <button
                      key={s}
                      type="button"
                      className="chat-chip"
                      onClick={() => preguntar(s)}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m, i) =>
              m.role === "user" ? (
                <p key={i} className="chat-msg chat-msg--user">
                  {m.text}
                </p>
              ) : (
                <Respuesta key={i} data={m} />
              )
            )}

            {loading && (
              <p className="chat-msg chat-msg--bot chat-loading">
                Buscando en Wikipedia…
              </p>
            )}

            <div ref={endRef} />
          </div>

          {error && <p className="chat-error">{error}</p>}

          <form
            className="chat-form"
            onSubmit={(e) => {
              e.preventDefault();
              preguntar(question);
            }}
          >
            <input
              className="input"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder={`Pregunta sobre «${song.name || "esta canción"}»`}
              maxLength={500}
              disabled={loading}
            />
            <button className="btn" type="submit" disabled={loading || !question.trim()}>
              Preguntar
            </button>
          </form>
        </>
      )}
    </Layout>
  );
}

// ─── Piezas ─────────────────────────────────────────────────────────────────

function CabeceraCancion({ song, onChange }) {
  return (
    <div className="chat-song">
      {song.cover_url ? (
        <img className="chat-song__art" src={song.cover_url} alt="" />
      ) : (
        <div className="chat-song__art chat-song__art--empty" aria-hidden="true">
          ♪
        </div>
      )}
      <div className="chat-song__meta">
        <strong className="chat-song__name">{song.name || song.spotify_track_id}</strong>
        {song.artist && <span className="chat-song__artist">{song.artist}</span>}
      </div>
      <button type="button" className="btn-ghost" onClick={onChange}>
        Cambiar canción
      </button>
    </div>
  );
}

// Una respuesta del backend. Los tres modos se pintan distinto a propósito: al
// usuario le importa saber si le están respondiendo desde una fuente, si no hay
// fuente, o si la fuente existe pero el generador no está disponible.
function Respuesta({ data }) {
  if (data.mode === "no_context") {
    return (
      <div className="chat-msg chat-msg--bot chat-msg--warn">
        <p>{data.message}</p>
      </div>
    );
  }

  if (data.mode === "retrieval_only") {
    return (
      <div className="chat-msg chat-msg--bot chat-msg--warn">
        <p>{data.message}</p>
        {data.excerpt && <blockquote className="chat-excerpt">{data.excerpt}…</blockquote>}
        <Fuente source={data.source} kind={data.context_kind} />
      </div>
    );
  }

  return (
    <div className="chat-msg chat-msg--bot">
      <p className="chat-answer">{data.answer}</p>
      <Fuente source={data.source} kind={data.context_kind} />
    </div>
  );
}

// La cita. Es obligatoria en este diseño: sin ella el usuario no puede
// comprobar nada y la respuesta valdría lo mismo que una inventada.
function Fuente({ source, kind }) {
  if (!source) return null;
  return (
    <p className="chat-source">
      Fuente:{" "}
      <a href={source.url} target="_blank" rel="noreferrer">
        {source.title}
      </a>{" "}
      (Wikipedia)
      {kind === "artist" && (
        <span className="chat-source__note">
          {" "}
          — es el artículo del artista, no de la canción
        </span>
      )}
    </p>
  );
}

// Buscador para elegir canción cuando se entra por el menú sin nada sonando.
function SelectorDeCancion({ onPick }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function buscar(e) {
    e.preventDefault();
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    try {
      setResults(await searchSongs(q.trim(), 8));
    } catch (err) {
      setError(err.message || "No se pudo buscar.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chat-picker">
      <p className="chat-picker__hint">
        Elige una canción para empezar, o pon algo a sonar y vuelve.
      </p>

      <form className="search-form" onSubmit={buscar}>
        <input
          className="input"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Canción o artista"
        />
        <button className="btn" type="submit" disabled={loading}>
          {loading ? "Buscando…" : "Buscar"}
        </button>
      </form>

      {error && <p className="chat-error">{error}</p>}

      <ul className="chat-picker__list">
        {results.map((t) => (
          <li key={t.spotify_track_id}>
            <button type="button" className="chat-picker__item" onClick={() => onPick(t)}>
              {t.cover_url && <img src={t.cover_url} alt="" />}
              <span>
                <strong>{t.name}</strong>
                <em>{t.artist}</em>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
