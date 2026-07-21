// Tests de api.js — el cliente del backend. Se mockea `fetch` (con vi.fn) para
// comprobar QUÉ URL/parámetros/cabeceras se mandan, sin red real.
import { beforeEach, afterEach, describe, it, expect, vi } from "vitest";
import {
  getToken, getSpotifyId, authHeaders,
  searchSongs, getDashboard, getRecommendations, getStats,
  addLike, removeLike, listLikes, addDislike, removeDislike, listDislikes,
  getHistory, registerPlayback, getSpotifyToken, createPlaylist, listPlaylists,
  getPlaylistTracksById, refreshRecommendations, getLoginUrl,
} from "./api";

// Un JWT de mentira: solo importa el payload en base64 (la parte del medio).
function fakeJwt(payload) {
  return `header.${btoa(JSON.stringify(payload))}.sig`;
}

function mockFetch(body, ok = true, status = 200) {
  const res = { ok, status, json: async () => body };
  const fn = vi.fn().mockResolvedValue(res);
  vi.stubGlobal("fetch", fn);
  return fn;
}

beforeEach(() => localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

describe("token helpers", () => {
  it("getToken lee el token de localStorage", () => {
    localStorage.setItem("token", "abc");
    expect(getToken()).toBe("abc");
  });

  it("getSpotifyId saca el 'sub' del JWT", () => {
    localStorage.setItem("token", fakeJwt({ sub: "spotify-julian", id: 1 }));
    expect(getSpotifyId()).toBe("spotify-julian");
  });

  it("getSpotifyId devuelve null sin token o con JWT corrupto", () => {
    expect(getSpotifyId()).toBeNull();
    localStorage.setItem("token", "no-es-un-jwt");
    expect(getSpotifyId()).toBeNull();
  });

  it("authHeaders incluye el Bearer y el x_spotify_id cuando hay token", () => {
    localStorage.setItem("token", fakeJwt({ sub: "sp1" }));
    const h = authHeaders();
    expect(h.Authorization).toBe(`Bearer ${getToken()}`);
    expect(h.x_spotify_id).toBe("sp1");
  });
});

describe("requests", () => {
  it("searchSongs codifica la query y pasa el limit", async () => {
    const fetchMock = mockFetch([{ spotify_track_id: "t1" }]);
    const out = await searchSongs("juanes & feid", 5);
    const url = fetchMock.mock.calls[0][0];
    expect(url).toContain("/music/songs/search");
    expect(url).toContain("q=juanes%20%26%20feid");   // espacio y & codificados
    expect(url).toContain("limit=5");
    expect(out).toEqual([{ spotify_track_id: "t1" }]);
  });

  it("getDashboard arma el querystring con days/top y period/limit si se pasan", async () => {
    const fetchMock = mockFetch({ window: {} });
    await getDashboard({ days: 1, top: 5, period: "monthly", limit: 20 });
    const url = fetchMock.mock.calls[0][0];
    expect(url).toContain("days=1");
    expect(url).toContain("top=5");
    expect(url).toContain("period=monthly");
    expect(url).toContain("limit=20");
  });

  it("getRecommendations sin opciones NO manda querystring", async () => {
    const fetchMock = mockFetch({ tracks: [] });
    await getRecommendations();
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/recommendations\/list$/);
  });

  it("getRecommendations con período añade el query", async () => {
    const fetchMock = mockFetch({ tracks: [] });
    await getRecommendations({ period: "weekly", limit: 15 });
    const url = fetchMock.mock.calls[0][0];
    expect(url).toContain("period=weekly");
    expect(url).toContain("limit=15");
  });

  it("una respuesta no-2xx lanza un error legible", async () => {
    mockFetch(null, false, 500);
    await expect(getStats()).rejects.toThrow("El servidor respondió 500");
  });
});

describe("interacciones (like / dislike / playback)", () => {
  it("addLike y removeLike usan POST y DELETE sobre el track", async () => {
    const f1 = mockFetch({});
    await addLike("t1");
    expect(f1.mock.calls[0][0]).toContain("/music/interactions/likes/t1");
    expect(f1.mock.calls[0][1].method).toBe("POST");

    const f2 = mockFetch({});
    await removeLike("t1");
    expect(f2.mock.calls[0][1].method).toBe("DELETE");
  });

  it("addDislike / removeDislike apuntan a /dislikes", async () => {
    const f = mockFetch({});
    await addDislike("t1");
    expect(f.mock.calls[0][0]).toContain("/music/interactions/dislikes/t1");
    await removeDislike("t1");
  });

  it("listLikes y listDislikes devuelven el json", async () => {
    mockFetch([{ spotify_track_id: "t1" }]);
    expect(await listLikes()).toEqual([{ spotify_track_id: "t1" }]);
    mockFetch([{ spotify_track_id: "t2" }]);
    expect(await listDislikes()).toEqual([{ spotify_track_id: "t2" }]);
  });

  it("registerPlayback manda el payload como JSON", async () => {
    const f = mockFetch({});
    await registerPlayback({ spotify_track_id: "t1", seconds_played: 40 });
    const opts = f.mock.calls[0][1];
    expect(opts.method).toBe("POST");
    expect(opts.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(opts.body).seconds_played).toBe(40);
  });
});

describe("historial, playlists, recomendaciones y auth", () => {
  it("getHistory pasa el limit", async () => {
    const f = mockFetch([]);
    await getHistory(12);
    expect(f.mock.calls[0][0]).toContain("history?limit=12");
  });

  it("getSpotifyToken devuelve el access_token del cuerpo", async () => {
    mockFetch({ access_token: "spotify-real-token" });
    expect(await getSpotifyToken("u1")).toBe("spotify-real-token");
  });

  it("createPlaylist manda name/description/public en el cuerpo", async () => {
    const f = mockFetch({ id: "PL", name: "Mix" });
    const out = await createPlaylist("Mix", "desc", true);
    expect(JSON.parse(f.mock.calls[0][1].body)).toEqual({
      name: "Mix", description: "desc", public: true,
    });
    expect(out).toEqual({ id: "PL", name: "Mix" });
  });

  it("listPlaylists y getPlaylistTracksById devuelven json", async () => {
    mockFetch([{ id: "PL" }]);
    expect(await listPlaylists()).toEqual([{ id: "PL" }]);
    mockFetch([{ id: "t1" }]);
    expect(await getPlaylistTracksById("PL")).toEqual([{ id: "t1" }]);
  });

  it("refreshRecommendations usa POST y pasa el período", async () => {
    const f = mockFetch({ tracks: [] });
    await refreshRecommendations({ period: "monthly" });
    expect(f.mock.calls[0][1].method).toBe("POST");
    expect(f.mock.calls[0][0]).toContain("period=monthly");
  });

  it("getLoginUrl devuelve el json con la url", async () => {
    mockFetch({ url: "https://accounts.spotify.com/authorize?..." });
    expect((await getLoginUrl()).url).toContain("spotify.com");
  });
});
