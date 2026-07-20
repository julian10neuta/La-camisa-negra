// Test de la pantalla de Chat IA: preguntar sobre una canción.
//
// Lo que de verdad importa comprobar aquí no es que "salga texto", sino que los
// TRES modos que puede devolver el backend se muestren de forma distinta y
// honesta: respuesta con su fuente citada, "no hay información" cuando no se
// encontró nada, y el modo degradado cuando hay fuente pero no generador. Si
// esos tres se pintaran igual, el usuario no sabría cuándo puede fiarse.
import { beforeEach, it, expect, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../api");
vi.mock("../player/PlayerContext", () => ({
  usePlayer: () => ({ current: null, playTrack: vi.fn() }),
}));

import * as api from "../api";
import Chat from "./Chat";

const CANCION = { spotify_track_id: "t1", name: "La Camisa Negra", artist: "Juanes" };

beforeEach(() => {
  vi.clearAllMocks();
  api.getToken.mockReturnValue("tok");
  api.searchSongs.mockResolvedValue([CANCION]);
});

function renderAt(path = "/chat", state) {
  return render(
    <MemoryRouter initialEntries={[{ pathname: path, search: path.split("?")[1] ? `?${path.split("?")[1]}` : "", state }]}>
      <Chat />
    </MemoryRouter>
  );
}

it("sin canción muestra el selector para elegir una", () => {
  renderAt("/chat");
  expect(screen.getByText(/Elige una canción para empezar/)).toBeInTheDocument();
});

it("elegir una canción en el selector abre el chat sobre ella", async () => {
  renderAt("/chat");
  const input = screen.getByPlaceholderText("Canción o artista");
  fireEvent.change(input, { target: { value: "juanes" } });
  fireEvent.submit(input.closest("form"));

  await waitFor(() => expect(screen.getByText("La Camisa Negra")).toBeInTheDocument());
  fireEvent.click(screen.getByText("La Camisa Negra").closest("button"));

  expect(screen.getByText("¿Qué quieres saber?")).toBeInTheDocument();
});

it("llegando con la canción puesta, preguntar muestra la respuesta y CITA la fuente", async () => {
  api.askAboutSong.mockResolvedValue({
    song: CANCION,
    mode: "answer",
    answer: "Trata de un amor tóxico.",
    source: { title: "La camisa negra", url: "https://es.wikipedia.org/wiki/La_camisa_negra" },
    context_kind: "song",
  });

  renderAt("/chat?track=t1", { song: CANCION });
  const input = screen.getByPlaceholderText(/Pregunta sobre/);
  fireEvent.change(input, { target: { value: "¿De qué trata?" } });
  fireEvent.submit(input.closest("form"));

  await waitFor(() => expect(screen.getByText("Trata de un amor tóxico.")).toBeInTheDocument());
  expect(api.askAboutSong).toHaveBeenCalledWith("t1", "¿De qué trata?");

  const enlace = screen.getByRole("link", { name: "La camisa negra" });
  expect(enlace).toHaveAttribute("href", "https://es.wikipedia.org/wiki/La_camisa_negra");
});

it("avisa cuando la fuente es el artículo del ARTISTA y no el de la canción", async () => {
  api.askAboutSong.mockResolvedValue({
    song: CANCION,
    mode: "answer",
    answer: "Juanes es un cantautor colombiano.",
    source: { title: "Juanes", url: "https://es.wikipedia.org/wiki/Juanes" },
    context_kind: "artist",
  });

  renderAt("/chat?track=t1", { song: CANCION });
  fireEvent.click(screen.getByRole("button", { name: "¿De qué trata esta canción?" }));

  await waitFor(() =>
    expect(screen.getByText(/es el artículo del artista, no de la canción/)).toBeInTheDocument()
  );
});

it("sin información no inventa: muestra el aviso y ninguna fuente", async () => {
  api.askAboutSong.mockResolvedValue({
    song: CANCION,
    mode: "no_context",
    answer: null,
    source: null,
    message: "No encontré información confiable sobre «La Camisa Negra».",
  });

  renderAt("/chat?track=t1", { song: CANCION });
  fireEvent.click(screen.getByRole("button", { name: "¿De qué trata esta canción?" }));

  await waitFor(() =>
    expect(screen.getByText(/No encontré información confiable/)).toBeInTheDocument()
  );
  // Sin fuente no se cita nada. (Ojo: no vale comprobar "no hay ningún enlace",
  // porque el menú de navegación del Layout también son enlaces.)
  expect(screen.queryByText(/Fuente:/)).not.toBeInTheDocument();
});

it("sin generador muestra el extracto de la fuente en vez de fallar", async () => {
  api.askAboutSong.mockResolvedValue({
    song: CANCION,
    mode: "retrieval_only",
    answer: null,
    message: "Ahora mismo no puedo redactarte la respuesta.",
    excerpt: "«La camisa negra» es el tercer sencillo del álbum Mi sangre",
    source: { title: "La camisa negra", url: "https://es.wikipedia.org/wiki/La_camisa_negra" },
  });

  renderAt("/chat?track=t1", { song: CANCION });
  fireEvent.click(screen.getByRole("button", { name: "¿De qué trata esta canción?" }));

  await waitFor(() =>
    expect(screen.getByText(/tercer sencillo del álbum Mi sangre/)).toBeInTheDocument()
  );
  expect(screen.getByRole("link", { name: "La camisa negra" })).toBeInTheDocument();
});

it("si la petición falla lo dice y no deja el chat colgado", async () => {
  api.askAboutSong.mockRejectedValue(new Error("El servidor respondió 503"));

  renderAt("/chat?track=t1", { song: CANCION });
  fireEvent.click(screen.getByRole("button", { name: "¿De qué trata esta canción?" }));

  await waitFor(() => expect(screen.getByText("El servidor respondió 503")).toBeInTheDocument());
  expect(screen.getByPlaceholderText(/Pregunta sobre/)).not.toBeDisabled();
});
