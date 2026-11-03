import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  SlidersHorizontal,
} from "lucide-react";
import { useAuth, useQuery } from "../state";
import {
  Empty,
  ErrorBox,
  LoginRequired,
  Spinner,
  VideoGrid,
} from "../components/UI";
import { categories, type Page, type Video } from "../types";

const titles: Record<string, [string, string]> = {
  public: [
    "Найдите то, что интересно",
    "Новые видео и авторы, которых стоит открыть",
  ],
  popular: ["В тренде", "Видео, к которым возвращаются"],
  subscriptions: ["Подписки", "Новое от любимых авторов"],
  history: ["История просмотра", "Вернитесь к тому, что вас заинтересовало"],
  liked: ["Понравившиеся", "Всё, что вы отметили лайком"],
  shared: ["Доступные мне", "Приватные видео, которыми с вами поделились"],
};
export default function Feed({ scope = "public" }: { scope?: string }) {
  const { user, loading: authLoading } = useAuth(),
    [params, setParams] = useSearchParams();
  const category = categories.includes(params.get("category") || "")
    ? params.get("category")!
    : "Все";
  const [page, setPage] = useState(1),
    [sort, setSort] = useState(scope === "popular" ? "popular" : "new");
  const isSearch = location.pathname === "/search",
    q = params.get("q") || "";
  useEffect(() => {
    setPage(1);
  }, [q, category, scope]);
  const needsAuth = !["public", "popular"].includes(scope);
  const path =
    needsAuth && !user
      ? null
      : `/videos?scope=${scope === "popular" ? "public" : scope}&page=${page}&sort=${sort}&q=${encodeURIComponent(q)}&category=${encodeURIComponent(category === "Все" ? "" : category)}`;
  const { data, error, loading, reload } = useQuery<Page<Video>>(path);
  if (authLoading && needsAuth) return <Spinner />;
  if (needsAuth && !user) return <LoginRequired />;
  const title = titles[scope] || titles.public;
  return (
    <section className="feed">
      <div className="chips" aria-label="Категории видео">
        {categories.map((c) => (
          <button
            key={c}
            className={`chip ${category === c ? "selected" : ""}`}
            aria-pressed={category === c}
            onClick={() => {
              setParams((previous) => {
                const next = new URLSearchParams(previous);
                if (c === "Все") next.delete("category");
                else next.set("category", c);
                return next;
              });
              setPage(1);
            }}
          >
            {c}
          </button>
        ))}
      </div>
      <div className="feed-heading">
        <div>
          <p className="eyebrow">
            {isSearch
              ? "ПОИСК ВИДЕО"
              : scope === "public"
                ? "ВАША ПОРЦИЯ ВДОХНОВЕНИЯ"
                : "ВАША ВИДЕОТЕКА"}
          </p>
          <h1>
            {isSearch
              ? q
                ? `Результаты по запросу «${q}»`
                : "Что хотите посмотреть?"
              : title[0]}
          </h1>
          <p>
            {isSearch
              ? data
                ? `Найдено видео: ${data.total}`
                : "Ищем видео по названию"
              : title[1]}
          </p>
        </div>
        <label className="sort">
          <SlidersHorizontal size={17} />
          <span className="sr-only">Сортировать</span>
          <select
            aria-label="Сортировка"
            value={sort}
            onChange={(e) => {
              setSort(e.target.value);
              setPage(1);
            }}
          >
            <option value="new">Сначала новые</option>
            <option value="popular">По популярности</option>
          </select>
        </label>
      </div>
      {loading ? (
        <div
          className="video-grid skeleton-grid"
          aria-label="Загрузка видео"
          role="status"
        >
          {Array.from({ length: 9 }, (_, i) => (
            <div key={i} className="skeleton-card">
              <div />
              <span />
              <span />
            </div>
          ))}
        </div>
      ) : error ? (
        <ErrorBox message={error} retry={reload} />
      ) : data?.items.length ? (
        <>
          <VideoGrid videos={data.items} />
          {data.total > data.limit && (
            <div className="pagination">
              <button
                className="button secondary"
                disabled={page === 1}
                onClick={() => {
                  setPage((p) => p - 1);
                  window.scrollTo(0, 0);
                }}
              >
                <ChevronLeft size={18} />
                Назад
              </button>
              <span>
                {page} / {Math.ceil(data.total / data.limit)}
              </span>
              <button
                className="button secondary"
                disabled={page * data.limit >= data.total}
                onClick={() => {
                  setPage((p) => p + 1);
                  window.scrollTo(0, 0);
                }}
              >
                Далее
                <ChevronRight size={18} />
              </button>
            </div>
          )}
        </>
      ) : (
        <Empty
          title={isSearch ? "Ничего не нашлось" : "Здесь пока нет видео"}
          description={
            isSearch
              ? "Попробуйте другое название или выберите категорию «Все»."
              : "Начните с главной страницы или поделитесь своим первым видео."
          }
        >
          <Link
            className="button secondary"
            to={scope === "public" ? "/upload" : "/"}
          >
            {scope === "public" ? "Загрузить видео" : "Открыть главную"}
            <ArrowUpRight size={17} />
          </Link>
        </Empty>
      )}
    </section>
  );
}
