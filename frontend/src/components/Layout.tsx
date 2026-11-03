import { useState, type FormEvent } from "react";
import {
  Link,
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
} from "react-router-dom";
import {
  Menu,
  Search,
  Plus,
  Home,
  Compass,
  PanelsTopLeft,
  History,
  ThumbsUp,
  Layers,
  ShieldCheck,
  LockKeyhole,
  LogIn,
  LogOut,
  UserRound,
  Clapperboard,
  X,
} from "lucide-react";
import { useAuth, useQuery } from "../state";
import { Avatar, ErrorBox } from "./UI";
import type { Channel } from "../types";

export default function Layout() {
  const { user, logout } = useAuth(),
    navigate = useNavigate(),
    location = useLocation();
  const [open, setOpen] = useState(false),
    [collapsed, setCollapsed] = useState(false),
    [account, setAccount] = useState(false),
    [query, setQuery] = useState(""),
    [error, setError] = useState("");
  const { data: subscriptions } = useQuery<Channel[]>(
    user ? "/subscriptions" : null,
  );
  const search = (e: FormEvent) => {
    e.preventDefault();
    navigate(`/search?q=${encodeURIComponent(query.trim())}`);
    setOpen(false);
  };
  const item = (to: string, label: string, Icon: typeof Home, end = false) => (
    <NavLink
      to={to}
      end={end}
      onClick={() => setOpen(false)}
      className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
    >
      <Icon size={21} />
      <span>{label}</span>
    </NavLink>
  );
  return (
    <>
      <a className="skip-link" href="#main">
        Перейти к содержимому
      </a>
      <header className="topbar">
        <div className="brand-area">
          <button
            className="icon-button menu-button"
            aria-label="Переключить меню"
            onClick={() => {
              if (window.matchMedia("(max-width: 600px)").matches)
                setOpen(!open);
              else setCollapsed(!collapsed);
            }}
          >
            {open ? <X /> : <Menu />}
          </button>
          <Link className="brand" to="/" aria-label="ViewTube — главная">
            <span className="brand-mark">
              <span />
            </span>
            <span>ViewTube</span>
            <sup>RU</sup>
          </Link>
        </div>
        <form className="search" onSubmit={search}>
          <input
            aria-label="Поиск видео"
            type="search"
            placeholder="Введите запрос"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button aria-label="Найти">
            <Search size={21} />
          </button>
        </form>
        <div className="header-actions">
          <Link
            className="button create-button"
            aria-label="Создать"
            to={user ? "/upload" : "/login?next=/upload"}
          >
            <Plus size={21} />
            <span>Создать</span>
          </Link>
          {user ? (
            <div className="account">
              <button
                className="avatar-button"
                aria-label="Меню аккаунта"
                aria-expanded={account}
                onClick={() => setAccount(!account)}
              >
                <Avatar name={user.display_name} />
              </button>
              {account && (
                <>
                  <button
                    className="dismiss-menu"
                    aria-label="Закрыть меню аккаунта"
                    onClick={() => setAccount(false)}
                  />
                  <div className="account-menu">
                    <strong>{user.display_name}</strong>
                    <small>{user.email}</small>
                    <Link
                      to={`/channel/${user.channel_id}`}
                      onClick={() => setAccount(false)}
                    >
                      <UserRound size={18} />
                      Мой канал
                    </Link>
                    <Link to="/studio" onClick={() => setAccount(false)}>
                      <Clapperboard size={18} />
                      Творческая студия
                    </Link>
                    <button
                      onClick={async () => {
                        try {
                          await logout();
                          setAccount(false);
                          navigate("/");
                        } catch (e) {
                          setError((e as Error).message);
                        }
                      }}
                    >
                      <LogOut size={18} />
                      Выйти
                    </button>
                  </div>
                </>
              )}
            </div>
          ) : (
            <Link
              className="button sign-in"
              to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`}
            >
              <UserRound size={19} />
              <span>Войти</span>
            </Link>
          )}
        </div>
      </header>
      {open && (
        <button
          className="sidebar-backdrop"
          onClick={() => setOpen(false)}
          aria-label="Закрыть навигацию"
        />
      )}
      <aside
        className={`sidebar ${open ? "open" : ""} ${collapsed ? "collapsed" : ""}`}
        aria-label="Основная навигация"
      >
        <div className="nav-group">
          {item("/", "Главная", Home, true)}
          {item("/explore", "В тренде", Compass)}
          {item("/subscriptions", "Подписки", PanelsTopLeft)}
        </div>
        <div className="nav-group">
          <h3>
            Вы <span>›</span>
          </h3>
          {item("/history", "История", History)}
          {item("/liked", "Понравившиеся", ThumbsUp)}
          {item("/playlists", "Плейлисты", Layers)}
          {item("/shared", "Доступные мне", LockKeyhole)}
          {item("/studio", "Ваши видео", Clapperboard)}
        </div>
        {user && (user.role === "admin" || user.role === "moderator") && (
          <div className="nav-group">
            {item("/moderation", "Модерация", ShieldCheck)}
            {user.role === "admin" && item("/admin", "Пользователи", UserRound)}
          </div>
        )}
        {subscriptions && subscriptions.length > 0 && (
          <div className="nav-group">
            <h3>Подписки</h3>
            {subscriptions.slice(0, 7).map((c) => (
              <Link
                className="nav-item channel-nav"
                key={c.id}
                to={`/channel/${c.id}`}
                onClick={() => setOpen(false)}
              >
                <Avatar name={c.name} color={c.color} />
                <span>{c.name}</span>
              </Link>
            ))}
          </div>
        )}
        {!user && (
          <div className="sidebar-login">
            <p>
              Сохраняйте любимое.
              <br />
              Находите своих авторов.
            </p>
            <Link className="button sign-in" to="/login">
              <LogIn size={17} />
              Войти
            </Link>
          </div>
        )}
        <div className="sidebar-footer">
          <p>
            Смотрите. Создавайте.
            <br />
            Делитесь интересным.
          </p>
          <span>© {new Date().getFullYear()} ViewTube</span>
        </div>
      </aside>
      <main
        id="main"
        className={`main ${collapsed ? "expanded" : ""}`}
        tabIndex={-1}
      >
        {error && <ErrorBox message={error} />}
        <Outlet />
      </main>
    </>
  );
}
