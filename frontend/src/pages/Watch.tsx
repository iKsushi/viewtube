import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  Check,
  Flag,
  Layers,
  Share2,
  ThumbsDown,
  ThumbsUp,
  Trash2,
} from "lucide-react";
import { send } from "../api";
import { useAuth, useQuery } from "../state";
import {
  Avatar,
  CopyButton,
  Empty,
  ErrorBox,
  Modal,
  Spinner,
  VideoCard,
} from "../components/UI";
import {
  number,
  plural,
  type Channel,
  type Page,
  type Playlist,
  type Video,
} from "../types";

type Comment = {
  id: string;
  text: string;
  author: string;
  created_at: string;
  can_delete: boolean;
};
export default function Watch() {
  const { id } = useParams(),
    { user } = useAuth(),
    navigate = useNavigate();
  const video = useQuery<Video>(`/videos/${id}`),
    channel = useQuery<Channel>(
      video.data ? `/channels/${video.data.channel.id}` : null,
    );
  const [commentPage, setCommentPage] = useState(1),
    [text, setText] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [modal, setModal] = useState(""),
    [reason, setReason] = useState(""),
    [notice, setNotice] = useState(""),
    [expanded, setExpanded] = useState(false),
    [mediaError, setMediaError] = useState(false);
  const comments = useQuery<Comment[]>(
      video.data?.status === "ready" && !video.data.hidden
        ? `/videos/${id}/comments?page=${commentPage}`
        : null,
    ),
    related = useQuery<Page<Video>>("/videos?limit=9&sort=popular");
  const player = useRef<HTMLVideoElement>(null),
    lastSaved = useRef(0);
  const lists = useQuery<Playlist[]>(
    modal === "save" && user ? `/channels/${user.channel_id}/playlists` : null,
  );
  useEffect(() => {
    setCommentPage(1);
    setError("");
    setNotice("");
    setMediaError(false);
    lastSaved.current = 0;
    window.scrollTo(0, 0);
  }, [id]);
  const login = () => {
    navigate(`/login?next=/watch/${id}`);
  };
  async function action(fn: () => Promise<void>) {
    if (!user) {
      login();
      return;
    }
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function addComment(e: FormEvent) {
    e.preventDefault();
    await action(async () => {
      await send(`/videos/${id}/comments`, "POST", { text });
      setText("");
      setCommentPage(1);
      comments.reload();
      video.setData((v) =>
        v ? { ...v, comment_count: v.comment_count + 1 } : v,
      );
    });
  }
  if (video.loading) return <Spinner />;
  if (video.error)
    return (
      <Empty title="Видео недоступно" description={video.error}>
        <Link to="/" className="button secondary">
          На главную
        </Link>
      </Empty>
    );
  const v = video.data!;
  if (v.status !== "ready" || v.hidden)
    return (
      <Empty
        title={v.hidden ? "Видео скрыто модератором" : "Видео ещё не готово"}
        description={
          v.error || "Статус обработки можно проверить в творческой студии."
        }
      >
        <Link to="/studio" className="button primary">
          Открыть студию
        </Link>
      </Empty>
    );
  return (
    <div className="watch-layout">
      <section className="watch-main">
        <div className="player">
          <video
            ref={player}
            key={id}
            controls
            playsInline
            preload="metadata"
            poster={v.thumbnail || undefined}
            src={`/api/videos/${id}/stream`}
            onError={() => setMediaError(true)}
            onLoadedMetadata={() => {
              if (
                player.current &&
                v.position > 0 &&
                v.position < player.current.duration - 2
              )
                player.current.currentTime = v.position;
            }}
            onTimeUpdate={() => {
              const p = player.current;
              if (
                !p ||
                p.paused ||
                p.currentTime < 1 ||
                Date.now() - lastSaved.current < 15000
              )
                return;
              lastSaved.current = Date.now();
              send(`/videos/${id}/view`, "POST", {
                position: p.currentTime,
              }).catch(() => {});
            }}
          />
        </div>
        {mediaError && (
          <ErrorBox
            message="Не удалось воспроизвести видео. Проверьте подключение или доступ."
            retry={() => {
              setMediaError(false);
              player.current?.load();
            }}
          />
        )}
        <h1 className="watch-title">{v.title}</h1>
        <div className="watch-toolbar">
          <div className="channel-line">
            <Link to={`/channel/${v.channel.id}`}>
              <Avatar name={v.channel.name} color={v.channel.color} />
            </Link>
            <div>
              <Link className="channel-name" to={`/channel/${v.channel.id}`}>
                {v.channel.name}
              </Link>
              <small>
                {number(channel.data?.subscribers || 0)}{" "}
                {plural(
                  channel.data?.subscribers || 0,
                  "подписчик",
                  "подписчика",
                  "подписчиков",
                )}
              </small>
            </div>
            {!v.is_owner && (
              <button
                className={`button ${channel.data?.subscribed ? "secondary" : "dark"}`}
                disabled={busy}
                onClick={() =>
                  action(async () =>
                    channel.setData(
                      await send<Channel>(
                        `/channels/${v.channel.id}/subscription`,
                        channel.data?.subscribed ? "DELETE" : "PUT",
                      ),
                    ),
                  )
                }
              >
                {channel.data?.subscribed ? (
                  <>
                    <Check size={16} />
                    Вы подписаны
                  </>
                ) : (
                  "Подписаться"
                )}
              </button>
            )}
          </div>
          <div className="video-actions">
            <div className="reaction-group">
              <button
                className={v.reaction === 1 ? "chosen" : ""}
                aria-label="Нравится"
                aria-pressed={v.reaction === 1}
                disabled={busy}
                onClick={() =>
                  action(async () =>
                    video.setData(
                      await send<Video>(`/videos/${id}/reaction`, "PUT", {
                        value: v.reaction === 1 ? 0 : 1,
                      }),
                    ),
                  )
                }
              >
                <ThumbsUp size={19} />
                {number(v.likes)}
              </button>
              <button
                className={v.reaction === -1 ? "chosen" : ""}
                aria-label="Не нравится"
                aria-pressed={v.reaction === -1}
                disabled={busy}
                onClick={() =>
                  action(async () =>
                    video.setData(
                      await send<Video>(`/videos/${id}/reaction`, "PUT", {
                        value: v.reaction === -1 ? 0 : -1,
                      }),
                    ),
                  )
                }
              >
                <ThumbsDown size={19} />
              </button>
            </div>
            <button
              className="button secondary"
              onClick={() => setModal("share")}
            >
              <Share2 size={18} />
              <span>Поделиться</span>
            </button>
            <button
              className="icon-button soft"
              aria-label="Сохранить в плейлист"
              onClick={() => (user ? setModal("save") : login())}
            >
              <Layers size={19} />
            </button>
            <button
              className="icon-button soft"
              aria-label="Пожаловаться"
              onClick={() => (user ? setModal("report") : login())}
            >
              <Flag size={18} />
            </button>
          </div>
        </div>
        {error && <ErrorBox message={error} />}{" "}
        {notice && (
          <p className="success" role="status">
            <Check size={17} />
            {notice}
          </p>
        )}
        <div className="description">
          <p>
            <strong>
              {number(v.views)}{" "}
              {plural(v.views, "просмотр", "просмотра", "просмотров")}
            </strong>{" "}
            <span>{new Date(v.created_at).toLocaleDateString("ru-RU")}</span>{" "}
            <Link to={`/?category=${encodeURIComponent(v.category)}`}>
              #{v.category}
            </Link>
            {v.visibility === "private" && (
              <span className="badge">Приватное видео</span>
            )}
          </p>
          <p className={expanded ? "" : "clamp"}>
            {v.description || "Автор пока не добавил описание."}
          </p>
          {v.description.length > 180 && (
            <button
              className="text-button"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? "Свернуть" : "Ещё"}
            </button>
          )}
        </div>
        <div className="comments-heading">
          <h2>
            {number(v.comment_count)}{" "}
            {plural(
              v.comment_count,
              "комментарий",
              "комментария",
              "комментариев",
            )}
          </h2>
          <span>Сначала новые</span>
        </div>
        <form className="comment-form" onSubmit={addComment}>
          <Avatar name={user?.display_name || "?"} />
          <div>
            <label className="sr-only" htmlFor="comment">
              Комментарий
            </label>
            <textarea
              id="comment"
              placeholder={
                user
                  ? "Поделитесь впечатлениями…"
                  : "Войдите, чтобы оставить комментарий"
              }
              maxLength={2000}
              required
              value={text}
              onChange={(e) => setText(e.target.value)}
              onFocus={() => {
                if (!user) login();
              }}
            />
            <div className="form-actions">
              <span>{text.length > 0 ? `${text.length}/2000` : ""}</span>
              <button
                className="button primary"
                disabled={busy || !text.trim()}
              >
                Отправить
              </button>
            </div>
          </div>
        </form>
        {comments.loading ? (
          <Spinner />
        ) : comments.error ? (
          <ErrorBox message={comments.error} retry={comments.reload} />
        ) : (
          <div className="comments">
            {comments.data?.map((c) => (
              <article className="comment" key={c.id}>
                <Avatar name={c.author} />
                <div>
                  <p>
                    <strong>{c.author}</strong>
                    <small>
                      {new Date(c.created_at).toLocaleDateString("ru-RU")}
                    </small>
                  </p>
                  <p>{c.text}</p>
                </div>
                {c.can_delete && (
                  <button
                    className="icon-button"
                    aria-label="Удалить комментарий"
                    disabled={busy}
                    onClick={() =>
                      action(async () => {
                        await send(`/videos/${id}/comments/${c.id}`, "DELETE");
                        comments.reload();
                        video.setData((v) =>
                          v
                            ? {
                                ...v,
                                comment_count: Math.max(0, v.comment_count - 1),
                              }
                            : v,
                        );
                      })
                    }
                  >
                    <Trash2 size={16} />
                  </button>
                )}
              </article>
            ))}
            {comments.data?.length === 0 && (
              <p className="muted">
                Начните обсуждение — оставьте первый комментарий.
              </p>
            )}
          </div>
        )}
        {(commentPage > 1 || comments.data?.length === 30) && (
          <div className="pagination">
            <button
              className="button secondary"
              disabled={commentPage === 1}
              onClick={() => setCommentPage((p) => p - 1)}
            >
              Назад
            </button>
            <span>{commentPage}</span>
            <button
              className="button secondary"
              disabled={(comments.data?.length || 0) < 30}
              onClick={() => setCommentPage((p) => p + 1)}
            >
              Далее
            </button>
          </div>
        )}
      </section>
      <aside className="related">
        <h2>Ещё интересное</h2>
        {related.data?.items
          .filter((x) => x.id !== id)
          .slice(0, 8)
          .map((x) => (
            <VideoCard key={x.id} video={x} compact />
          ))}
      </aside>
      {modal === "share" && (
        <Modal title="Поделиться видео" onClose={() => setModal("")}>
          <p className="muted">
            {v.visibility === "private"
              ? "Ссылка откроется только у пользователей, которым владелец разрешил просмотр."
              : "Отправьте ссылку тем, кому это будет интересно."}
          </p>
          <input
            aria-label="Ссылка на видео"
            readOnly
            value={window.location.href}
          />
          <CopyButton value={window.location.href} />
        </Modal>
      )}
      {modal === "report" && (
        <Modal title="Пожаловаться на видео" onClose={() => setModal("")}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              action(async () => {
                await send(`/videos/${id}/reports`, "POST", { reason });
                setModal("");
                setReason("");
                setNotice("Жалоба отправлена модератору.");
              });
            }}
          >
            <p className="muted">
              Опишите нарушение. Жалобу рассмотрит модератор.
            </p>
            <label>
              Причина
              <textarea
                required
                minLength={5}
                maxLength={500}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </label>
            {error && <ErrorBox message={error} />}
            <button className="button primary" disabled={busy}>
              Отправить жалобу
            </button>
          </form>
        </Modal>
      )}
      {modal === "save" && (
        <Modal title="Сохранить в плейлист" onClose={() => setModal("")}>
          {lists.loading ? (
            <Spinner />
          ) : lists.error ? (
            <ErrorBox message={lists.error} />
          ) : lists.data?.length ? (
            <div className="list-options">
              {lists.data.map((p) => (
                <button
                  key={p.id}
                  disabled={busy}
                  onClick={() =>
                    action(async () => {
                      await send(`/playlists/${p.id}/videos/${id}`, "PUT");
                      setModal("");
                      setNotice(`Добавлено в «${p.title}»`);
                    })
                  }
                >
                  <Layers size={20} />
                  <span>
                    {p.title}
                    <small>
                      {p.visibility === "private" ? "Приватный" : "Открытый"} ·{" "}
                      {p.videos.length} видео
                    </small>
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <p>У вас пока нет плейлистов.</p>
          )}
          <Link className="button secondary" to="/playlists">
            Создать плейлист
          </Link>
          {error && <ErrorBox message={error} />}
        </Modal>
      )}
    </div>
  );
}
