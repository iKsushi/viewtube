import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Check, Edit3, Layers, Play } from "lucide-react";
import { send } from "../api";
import { useAuth, useQuery } from "../state";
import {
  Avatar,
  Empty,
  ErrorBox,
  Modal,
  Spinner,
  VideoGrid,
} from "../components/UI";
import {
  number,
  plural,
  type Channel as ChannelType,
  type Page,
  type Playlist,
  type Video,
} from "../types";

export function PlaylistCards({ lists }: { lists: Playlist[] }) {
  return (
    <div className="playlist-grid">
      {lists.map((p) => (
        <Link className="playlist-card" key={p.id} to={`/playlist/${p.id}`}>
          <div className="playlist-cover">
            {p.videos[0]?.thumbnail ? (
              <img src={p.videos[0].thumbnail} alt="" />
            ) : (
              <Layers size={46} />
            )}
            <span>
              <Layers size={17} />
              {p.videos.length} видео
            </span>
          </div>
          <h3>{p.title}</h3>
          <p>
            {p.visibility === "private"
              ? "Приватный плейлист"
              : "Открытый плейлист"}{" "}
            <Play size={12} />
          </p>
        </Link>
      ))}
    </div>
  );
}
export default function Channel() {
  const { id } = useParams(),
    { user } = useAuth(),
    channel = useQuery<ChannelType>(`/channels/${id}`),
    [tab, setTab] = useState("videos"),
    [page, setPage] = useState(1),
    [error, setError] = useState(""),
    [edit, setEdit] = useState(false),
    [name, setName] = useState(""),
    [description, setDescription] = useState(""),
    [busy, setBusy] = useState(false);
  const videos = useQuery<Page<Video>>(`/videos?channel_id=${id}&page=${page}`),
    lists = useQuery<Playlist[]>(`/channels/${id}/playlists`);
  if (channel.loading) return <Spinner />;
  if (channel.error)
    return <ErrorBox message={channel.error} retry={channel.reload} />;
  const c = channel.data!;
  return (
    <section className="channel-page">
      <div
        className="channel-banner"
        style={{ "--channel-color": c.color } as React.CSSProperties}
      >
        <span>{c.name}</span>
        <span className="banner-play" aria-hidden="true">
          ▶
        </span>
      </div>
      <div className="channel-header">
        <Avatar large name={c.name} color={c.color} />
        <div className="channel-description">
          <h1>{c.name}</h1>
          <p>
            @{c.handle} <span>·</span> {number(c.subscribers)}{" "}
            {plural(c.subscribers, "подписчик", "подписчика", "подписчиков")}{" "}
            <span>·</span> {videos.data?.total || 0} видео
          </p>
          <p className="channel-about">
            {c.description || "Добро пожаловать на канал!"}
          </p>
          <div>
            {c.is_owner ? (
              <>
                <Link className="button secondary" to="/studio">
                  Управление видео
                </Link>
                <button
                  className="button secondary"
                  onClick={() => {
                    setName(c.name);
                    setDescription(c.description);
                    setEdit(true);
                  }}
                >
                  <Edit3 size={16} />
                  Настроить канал
                </button>
              </>
            ) : user ? (
              <button
                className={`button ${c.subscribed ? "secondary" : "dark"}`}
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    channel.setData(
                      await send<ChannelType>(
                        `/channels/${id}/subscription`,
                        c.subscribed ? "DELETE" : "PUT",
                      ),
                    );
                  } catch (e) {
                    setError((e as Error).message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {c.subscribed ? (
                  <>
                    <Check size={16} />
                    Вы подписаны
                  </>
                ) : (
                  "Подписаться"
                )}
              </button>
            ) : (
              <Link className="button dark" to={`/login?next=/channel/${id}`}>
                Подписаться
              </Link>
            )}
          </div>
        </div>
      </div>
      {error && <ErrorBox message={error} />}
      <div className="tabs">
        <button
          className={tab === "videos" ? "selected" : ""}
          onClick={() => setTab("videos")}
        >
          Видео
        </button>
        <button
          className={tab === "playlists" ? "selected" : ""}
          onClick={() => setTab("playlists")}
        >
          Плейлисты
        </button>
      </div>
      {tab === "videos" ? (
        videos.loading ? (
          <Spinner />
        ) : videos.error ? (
          <ErrorBox message={videos.error} />
        ) : videos.data?.items.length ? (
          <>
            <VideoGrid videos={videos.data.items} />
            {videos.data.total > 18 && (
              <div className="pagination">
                <button
                  className="button secondary"
                  disabled={page === 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  Назад
                </button>
                <span>{page}</span>
                <button
                  className="button secondary"
                  disabled={page * 18 >= videos.data.total}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Далее
                </button>
              </div>
            )}
          </>
        ) : (
          <Empty
            title="Видео пока нет"
            description="Когда автор опубликует видео, оно появится здесь."
          />
        )
      ) : lists.loading ? (
        <Spinner />
      ) : lists.error ? (
        <ErrorBox message={lists.error} />
      ) : lists.data?.length ? (
        <PlaylistCards lists={lists.data} />
      ) : (
        <Empty
          title="Плейлисты пока не созданы"
          description="Здесь будут подборки автора."
        />
      )}
      {edit && (
        <Modal title="Настройка канала" onClose={() => setEdit(false)}>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError("");
              try {
                channel.setData(
                  await send<ChannelType>(`/channels/${id}`, "PATCH", {
                    name,
                    description,
                  }),
                );
                setEdit(false);
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <label>
              Название
              <input
                required
                minLength={2}
                maxLength={60}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label>
              Описание
              <textarea
                maxLength={2000}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </label>
            {error && <ErrorBox message={error} />}
            <button className="button primary" disabled={busy}>
              Сохранить
            </button>
          </form>
        </Modal>
      )}
    </section>
  );
}
